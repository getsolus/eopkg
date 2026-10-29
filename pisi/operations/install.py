# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

import multiprocessing
import os
import signal
import sys
import zipfile
from queue import Empty

from ordered_set import OrderedSet as set

import pisi
import pisi.context as ctx
import pisi.db
import pisi.ui
from pisi import (
    Error,
    atomicoperations,
    events,
    operations,
    pgraph,
    signalhandler,
    util,
)
from pisi import translate as _

BASELAYOUT_PKG = "baselayout"
EOPKG_PKG = "eopkg"


# Per-process global — set by worker_init after fork so each child
# has its own reference to the shared progress queue.
_worker_progress_queue = None


def _op_item_name(op_obj):
    """Progress-event item name for an operation object."""
    return getattr(op_obj, "package_name", None) or op_obj.pkginfo.name


def _op_pkg_info(op_obj):
    """Build the :class:`~pisi.events.PkgInfo` for an operation object."""
    pkg = getattr(op_obj, "pkginfo", None) or op_obj.package
    return events.PkgInfo(
        name=pkg.name,
        version=str(pkg.version),
        release=pkg.release,
        summary=pkg.summary,
    )


def _run_parallel(worker_fn, arg_list, ops, *,
                  oncompletion_cb=None,
                  apply_automatic=None,
                  op=events.Operation.INSTALL):
    """
    Handles pool creation, progress display, queue draining, error
    propagation, and cleanup.

    Callers are responsible for pre-flight checks (preflight() +
    check_configs()) before building *arg_list* — all checks run in the
    main process as one batch before anything is installed.

    Cache saving is inhibited in worker processes via worker_init;
    the main process retains cacheable=True so that @locked's
    update_caches() persists DB state normally.

    Parameters:
        worker_fn: callable accepting an element of *arg_list*.
        arg_list: iterable of arguments to pass to *worker_fn* in the pool.
        ops: list of operation objects; update_databases() is called on each
             after the pool finishes (unless *oncompletion_cb* is given).
        oncompletion_cb: Optional callback to be invoked after the pool
                   finishes. If not provided the default behaviour is to call
                   `op.update_databases()` on each op, applying
                   *apply_automatic* when set.
        apply_automatic: optional set of package names to mark as automatically
                         installed when updating databases (only used if
                         *oncompletion_cb* is not set).
        op: the :class:`~pisi.events.Operation` for the phase; drives the
            overall progress label and frontend behaviour.
    """
    signal_handler = signalhandler.SignalHandler()

    try:
        # Warm the FilesDB before extraction starts: a cold init here
        # (missing/invalid gdbm) triggers a rebuild that reads every
        # package's files.xml — which must happen before workers start
        # deleting old pkg dirs during extraction.
        filesdb = pisi.db.filesdb.FilesDB()
        if not filesdb.is_initialized():
            filesdb.init()

        # Setup progress display via the active UI frontend
        ctx.ui.info(_("Disabling keyboard interrupts for file operations."))
        signal_handler.disable_signal(signal.SIGINT)

        manager = multiprocessing.Manager()
        progress_queue = manager.Queue()

        # N.B. It's a bit wierd that we pass the entirely of options to each worker
        #      process. However, it was initially done so destdir was respected
        # N.B  We need actual processes here to overcoming limitations of the GIL
        #      to get an actual performance benefit. Revisting with a ThreadPool
        #      once the GIL is gone would be interesting and should help clean things
        #      up.
        pool = multiprocessing.Pool(
            initializer=worker_init, initargs=(progress_queue, ctx.config.options)
        )
        result = pool.map_async(worker_fn, arg_list)

        try:
            total = len(ops)
            seen = 0
            # Definitive overall unit total (files across all items) so
            # the global bar never shifts as workers register their items.
            total_units = sum(
                len(op_obj.files.list)
                for op_obj in ops
                if getattr(op_obj, "files", None) is not None
            )
            # Package metadata is resolved here rather than shipped in the
            # progress messages: workers emit progress on every tick and the
            # messages cross the process boundary, so keeping them free of
            # PkgInfo avoids re-pickling package data on every update.
            pkg_infos = {_op_item_name(op_obj): _op_pkg_info(op_obj) for op_obj in ops}

            with ctx.ui.work_phase(total, op, total_units=total_units) as phase:
                # Read until we've seen one ItemDone per package.
                # Counting done messages is race-free — we never check
                # `result.ready()` which can become True before the
                # last queue message has crossed the IPC buffer.
                while seen < total:
                    try:
                        msg = progress_queue.get(timeout=0.5)
                        if isinstance(msg, events.ItemProgress):
                            phase.add_item(
                                msg.item,
                                msg.total,
                                pkg_info=pkg_infos.get(msg.item),
                            )
                            phase.update_item(msg.item, msg.completed)
                        elif isinstance(msg, events.ItemDone):
                            phase.finish_item(msg.item)
                            seen += 1
                    except Empty:
                        # A failed worker sends no ItemDone, so counting
                        # alone would spin forever. Surface worker failures
                        # as soon as the pool reports them; if no worker
                        # failed, keep draining — the last ItemDone may
                        # still be crossing the IPC buffer.
                        if result.ready():
                            result.get()

            pool.close()
            pool.join()
            # Re-raise any worker exceptions
            result.get()
        except:
            pool.terminate()
            pool.join()
            raise

        ctx.ui.info(util.colorize(_("Updating databases..."), "yellow"))
        if oncompletion_cb is not None:
            oncompletion_cb(ops)
        else:
            for op_obj in ops:
                if (
                    apply_automatic is not None
                    and op_obj.pkginfo.name in apply_automatic
                ):
                    op_obj.automatic = True
                op_obj.update_databases()
    except Exception:  # noqa: TRY203 ensure exceptions from workers are raised to main
        raise
    finally:
        ctx.exec_usysconf()


def worker_init(queue, options):
    """Initialise a child process: store the progress queue reference,
    silence UI output, and re-apply config options (required when the
    multiprocessing start method is "spawn", which creates a fresh
    interpreter that re-imports modules with default config)."""
    global _worker_progress_queue
    _worker_progress_queue = queue
    pisi.api.set_userinterface(pisi.ui.UI())
    pisi.api.set_options(options)
    # Workers must not save caches — they would race writing the same
    # pickle files. The main process handles cache updates after
    # all workers finish and database operations are serialized.
    pisi.db.installdb.InstallDB().cacheable = False
    pisi.db.filesdb.FilesDB().cacheable = False


def install_pkg_worker(path):
    try:
        install_op = atomicoperations.Install(path)
        name = install_op.pkginfo.name
        # The event carries no metadata or operation type: the main process
        # resolves package info and every item shares the phase operation.
        install_op.progress_callback = lambda c, t: _worker_progress_queue.put(
            events.ItemProgress(item=name, completed=c, total=t)
        )
        install_op.extract()
        _worker_progress_queue.put(events.ItemDone(item=name))
    except Exception as e:
        raise e


def install_file_worker(path):
    try:
        install_op = atomicoperations.Install(path)
        name = install_op.pkginfo.name
        # The event carries no metadata or operation type: the main process
        # resolves package info and every item shares the phase operation.
        install_op.progress_callback = lambda c, t: _worker_progress_queue.put(
            events.ItemProgress(item=name, completed=c, total=t)
        )
        install_op.extract()
        _worker_progress_queue.put(events.ItemDone(item=name))
    except Exception as e:
        raise e


def remove_worker(args):
    """Worker for parallel removal — deletes package files.

    Receives the preloaded file list from the main process so the worker
    never touches the DBs. (TODO: reexamine the DB init issue, pisi is fucking crap)

    Sends per-file ItemProgress messages via the callback so the
    frontend can show meaningful percentages, then an ItemDone.
    """
    package_name, files = args
    try:
        remove_op = atomicoperations.Remove.for_worker(package_name, files)
        remove_op.progress_callback = lambda c, t: _worker_progress_queue.put(
            events.ItemProgress(item=package_name, completed=c, total=t)
        )
        remove_op.remove_files()
        _worker_progress_queue.put(events.ItemDone(item=package_name))
    except Exception as e:
        raise e


def plan_deterministic_install_order(order):
    """Ensure that baselayout is put at the end of any topological sort that includes it."""

    # save cycles
    if len(order) <= 1:
        return order

    # always order baselayout _last_ (since the order gets reversed)
    if BASELAYOUT_PKG in order:
        order.remove(BASELAYOUT_PKG)
        order.append(BASELAYOUT_PKG)

    return order


def install_critical_first(ops, *, apply_automatic=None):
    """Install critical packages (baselayout) sequentially, before the pool.

    Parallel workers cannot honour the install order, and every other
    package assumes baselayout's layout is already in place, so it must
    be fully installed (extracted + DB updates) in the main process
    before anything else starts extracting.

    Pre-flight (preflight() + check_configs()) must already have run for
    all ops.

    :param ops: Install operation objects to install.
    :param apply_automatic: Optional set of package names to mark automatic.
    :returns: The remaining ops (everything except the critical packages).
    """
    critical = {BASELAYOUT_PKG}
    rest = []
    for op in ops:
        if op.pkginfo.name in critical:
            ctx.ui.info(
                util.colorize(
                    _("Installing %s first...") % op.pkginfo.name, "yellow"
                )
            )
            if apply_automatic is not None and op.pkginfo.name in apply_automatic:
                op.automatic = True
            op.extract()
            op.update_databases()
        else:
            rest.append(op)
    return rest


def install_pkg_names(packages, reinstall=False):
    """
    Installs packages from the repository.

        Parameters:
            packages (list): List of package names
            reinstall (bool): Reinstall packages
    """

    installdb = pisi.db.installdb.InstallDB()
    packagedb = pisi.db.packagedb.PackageDB()

    packages = [
        str(package) for package in packages
    ]  # FIXME: why do we still get unicode input here? :/ -- exa

    packages = set(packages)

    # The user may have passed providers e.g. 'pkgconfig(foo)'
    # Ensure these get resolved to the underlying package name
    packages = operations.helper.resolve_provider_matches(packages)

    deduped_packages = packages

    # filter packages that are already installed
    if not reinstall:
        not_installed = set(
            [package for package in packages if not installdb.has_package(package)]
        )
        diff = packages - not_installed
        if len(diff) > 0:
            ctx.ui.warning(
                _(
                    "The following package(s) are already installed "
                    "and are not going to be installed again:"
                )
            )
            ctx.ui.info(util.format_by_columns(sorted(diff)))
            packages = not_installed

    if len(packages) == 0:
        ctx.ui.info(_("No packages to install."))
        return True

    packages |= operations.upgrade.upgrade_base(packages)

    if not ctx.config.get_option("ignore_dependency"):
        graph, order = plan_install_pkg_names(packages)
    else:
        graph = None
        order = list(packages)

    componentdb = pisi.db.componentdb.ComponentDB()

    # Bug 4211
    if componentdb.has_component("system.base"):
        order = operations.helper.reorder_base_packages(order)

    # Show what packages will be downloaded or installed if there are
    # more than one
    if len(order) > 1:
        if ctx.get_option("fetch_only"):
            ctx.ui.status(_("The following packages will be downloaded:"))
        else:
            ctx.ui.status(_("The following packages will be installed:"))

        ctx.ui.info(util.format_by_columns(sorted(order)))

    # Figure out the total download size
    total_size, cached_size = operations.helper.calculate_download_sizes(order)
    total_size, symbol = util.human_readable_size(total_size)
    ctx.ui.info(
        util.colorize(
            _("Total size of package(s): %.2f %s") % (total_size, symbol), "yellow"
        )
    )

    if ctx.get_option("dry_run"):
        return True

    # Figure out if we have additional packages to install
    # for the upgrade to be successful
    if set(order) - deduped_packages:
        ctx.ui.warning(_("There are extra packages due to dependencies."))
        needs_confirm = True

        if needs_confirm and not ctx.ui.confirm(_("Do you want to continue?")):
            return False

    # Resolve resources
    resources = operations.helper.get_download_info(order)

    # Fetch packages concurrently
    operations.helper.fetch_packages(order)

    # Verify hashes and instantiate Install objects
    install_ops = []
    for r in resources:
        if util.sha1_file(r.pkg_path) != r.expected_hash:
            raise Error(
                _("Download Error: Package %s does not match the repository package.")
                % r.name
            )
        install_ops.append(atomicoperations.Install(r.pkg_path))

    ctx.ui.status(_("Finished downloading packages."))

    # Don't actually install if --fetch-only was set
    if ctx.get_option("fetch_only"):
        return True

    # Remove conflicting packages
    if not ctx.get_option("ignore_package_conflicts"):
        conflicts = operations.helper.check_conflicts(order, packagedb)

        if conflicts:
            operations.remove.remove_conflicting_packages(conflicts)

    # Check all packages' relations before installing anything
    for install_op in install_ops:
        install_op.check_relations(set(order))

    automatic = operations.helper.extract_automatic(packages, order)

    # Batch pre-flight: all checks run in the main process before anything
    # is installed. check_configs() renames user-modified configs so workers
    # can extract without clobbering them.
    for install_op in install_ops:
        install_op.preflight(ask_reinstall=False)
        install_op.check_configs()

    # baselayout must be fully installed before the parallel pool starts:
    # workers cannot honour the install order, so install it sequentially
    # in the main process first (pre-flight already ran above).
    install_ops = install_critical_first(install_ops, apply_automatic=automatic)
    if install_ops:
        arg_list = [install_op.package_fname for install_op in install_ops]
        _run_parallel(
            install_pkg_worker, arg_list, install_ops,
            apply_automatic=automatic,
        )
    else:
        ctx.exec_usysconf()

    return True





def install_pkg_files(package_URIs, reinstall=False):
    """install a number of pisi package files"""

    installdb = pisi.db.installdb.InstallDB()
    ctx.ui.debug("A = %s" % str(package_URIs))

    for x in package_URIs:
        if not x.endswith(ctx.const.package_suffix):
            raise Error(_("Mixing file names and package names not supported yet."))

    # filter packages that are already installed
    tobe_installed, already_installed = [], set()
    if not reinstall:
        for x in package_URIs:
            if not x.endswith(ctx.const.delta_package_suffix) and x.endswith(
                ctx.const.package_suffix
            ):
                pkg_name, pkg_version = pisi.util.parse_package_name(
                    os.path.basename(x)
                )
                if installdb.has_package(pkg_name):
                    already_installed.add(pkg_name)
                else:
                    tobe_installed.append(x)
        if already_installed:
            ctx.ui.warning(
                _(
                    "The following package(s) are already installed "
                    "and are not going to be installed again:"
                )
            )
            ctx.ui.info(util.format_by_columns(sorted(already_installed)))
        package_URIs = tobe_installed

    # Download remote files first
    local_URIs = []
    for x in package_URIs:
        url = pisi.uri.URI(x)
        if url.is_remote_file():
            dest = ctx.config.cached_packages_dir()
            filepath = os.path.join(dest, url.filename())
            local_URIs.append(filepath)
            if not os.path.exists(filepath):
                pisi.file.File.download(url, dest)
        else:
            local_URIs.append(x)

    package_URIs = local_URIs

    if ctx.config.get_option("ignore_dependency"):
        # Simple code path: install each file directly, skipping dependency
        # resolution and ordering. Still runs through the parallel extraction
        # and serial DB updates handled by _run_parallel.
        file_install_ops = [
            atomicoperations.Install(x) for x in package_URIs
        ]
        # Batch pre-flight: all checks run in the main process before
        # anything is installed.
        for install_op in file_install_ops:
            install_op.preflight(ask_reinstall=not reinstall)
            install_op.check_configs()
        arg_list = [install_op.package_fname for install_op in file_install_ops]
        _run_parallel(
            install_file_worker, arg_list, file_install_ops,
        )
        return True

    # read the package information into memory first
    # regardless of which distribution they come from
    d_t = {}
    dfn = {}
    for x in package_URIs:
        try:
            package = pisi.package.Package(x)
            package.read()
        except zipfile.BadZipfile:
            # YALI needed to get which file is broken
            raise zipfile.BadZipfile(x)
        name = str(package.metadata.package.name)
        d_t[name] = package.metadata.package
        dfn[name] = x

    # check packages' DistributionReleases and Architecture
    if not ctx.get_option("ignore_check"):
        for x in list(d_t.keys()):
            pkg = d_t[x]
            if (
                pkg.distributionRelease
                != ctx.config.values.general.distribution_release
            ):
                raise Error(
                    _(
                        "Package %s is not compatible with your distribution release %s %s."
                    )
                    % (
                        x,
                        ctx.config.values.general.distribution,
                        ctx.config.values.general.distribution_release,
                    )
                )
            if pkg.architecture != ctx.config.values.general.architecture:
                raise Error(
                    _("Package %s (%s) is not compatible with your %s architecture.")
                    % (x, pkg.architecture, ctx.config.values.general.architecture)
                )

    def satisfiesDep(dep):
        # is dependency satisfied among available packages
        # or packages to be installed?
        return dep.satisfied_by_installed() or dep.satisfied_by_dict_repo(d_t)

    # for this case, we have to determine the dependencies
    # that aren't already satisfied and try to install them
    # from the repository
    dep_unsatis = []
    for name in list(d_t.keys()):
        pkg = d_t[name]
        deps = pkg.runtimeDependencies()
        for dep in deps:
            if not satisfiesDep(dep) and dep.package not in [
                x.package for x in dep_unsatis
            ]:
                dep_unsatis.append(dep)

    # now determine if these unsatisfied dependencies could
    # be satisfied by installing packages from the repo
    for dep in dep_unsatis:
        if not dep.satisfied_by_repo():
            raise Error(_("External dependencies not satisfied: %s") % dep)

    # if so, then invoke install_pkg_names
    extra_packages = [x.package for x in dep_unsatis]
    if extra_packages:
        ctx.ui.warning(
            _(
                "The following packages will be installed "
                "in order to satisfy dependencies:"
            )
        )
        ctx.ui.info(util.format_by_columns(sorted(extra_packages)))
        if not ctx.ui.confirm(_("Do you want to continue?")):
            raise Error(_("External dependencies not satisfied"))
        install_pkg_names(extra_packages, reinstall=True)

    class PackageDB:
        def get_package(self, key, repo=None):
            return d_t[str(key)]

    packagedb = PackageDB()

    A = list(d_t.keys())

    if len(A) == 0:
        ctx.ui.info(_("No packages to install."))
        return

    # try to construct a pisi graph of packages to
    # install / reinstall

    G_f = pgraph.PGraph(packagedb)  # construct G_f

    # find the "install closure" graph of G_f by package
    # set A using packagedb
    for x in A:
        G_f.add_package(x)
    B = A
    while len(B) > 0:
        Bp = set()
        for x in B:
            pkg = packagedb.get_package(x)
            for dep in pkg.runtimeDependencies():
                if dep.satisfied_by_dict_repo(d_t):
                    if not dep.package in G_f.vertices():
                        Bp.add(str(dep.package))
                    G_f.add_dep(x, dep)
        B = Bp
    if ctx.config.get_option("debug"):
        G_f.write_graphviz(sys.stdout)
    order = G_f.topological_sort()
    if not ctx.get_option("ignore_package_conflicts"):
        conflicts = operations.helper.check_conflicts(order, packagedb)
        if conflicts:
            operations.remove.remove_conflicting_packages(conflicts)
    order = plan_deterministic_install_order(order)
    order.reverse()
    ctx.ui.info(_("Installation order: ") + util.strlist(order))

    if ctx.get_option("dry_run"):
        return True

    # Pre-instantiate Install objects for pre-flight checks
    file_install_ops = []
    for x in order:
        file_install_ops.append(atomicoperations.Install(dfn[x]))

    # Check all packages' relations before installing anything
    for install_op in file_install_ops:
        install_op.check_relations(set(order))

    # Batch pre-flight: all checks run in the main process before anything
    # is installed.
    for install_op in file_install_ops:
        install_op.preflight(ask_reinstall=not reinstall)
        install_op.check_configs()

    file_install_ops = install_critical_first(file_install_ops)
    if file_install_ops:
        arg_list = [install_op.package_fname for install_op in file_install_ops]
        _run_parallel(
            install_file_worker, arg_list, file_install_ops,
        )
    else:
        ctx.exec_usysconf()

    return True


def plan_install_pkg_names(A):
    # try to construct a pisi graph of packages to
    # install / reinstall

    packagedb = pisi.db.packagedb.PackageDB()
    installdb = pisi.db.installdb.InstallDB()

    # Check if updates are available to opt into the slow path
    available_updates = []
    if not ctx.get_option("ignore_revdeps_of_deps_check"):
        available_updates = pisi.api.list_upgradable()

    G_f = pgraph.PGraph(packagedb)  # construct G_f

    # find the "install closure" graph of G_f by package
    # set A using packagedb
    for x in A:
        G_f.add_package(x)
    B = A

    while len(B) > 0:
        Bp = set()
        checked = list()
        for x in B:
            pkg = packagedb.get_package(x)
            for dep in pkg.runtimeDependencies():
                ctx.ui.debug("checking %s" % str(dep))
                # we don't deal with already *satisfied* dependencies
                if not dep.satisfied_by_installed():
                    if not dep.satisfied_by_repo():
                        raise Error(
                            _("%s dependency of package %s is not satisfied")
                            % (dep, pkg.name)
                        )
                    if not dep.package in G_f.vertices():
                        Bp.add(str(dep.package))
                    G_f.add_dep(x, dep)
                # Check for updates in the revdeps of the deps of the pkg(s) we're installing to avoid breakage.
                if dep.package in available_updates and not dep.package in checked:
                    for name, revdep in packagedb.get_rev_deps(dep.package):
                        if (
                            installdb.has_package(name)
                            and not revdep.satisfied_by_installed()
                        ):
                            checked.append(dep.package)
                            if not name in G_f.vertices():
                                Bp.add(name)
                            G_f.add_dep(name, revdep)
        B = Bp
    if ctx.config.get_option("debug"):
        G_f.write_graphviz(sys.stdout)
    order = G_f.topological_sort()
    if len(order) > 1 and ctx.config.get_option("debug"):
        ctx.ui.info(_("topological_sort() order: %s" % order))
    order = plan_deterministic_install_order(order)
    if len(order) > 1 and ctx.config.get_option("debug"):
        ctx.ui.info(_("deterministic order: %s" % order))
    order.reverse()
    if len(order) > 1 and ctx.config.get_option("debug"):
        ctx.ui.info(_("final order.reverse(): %s" % order))
    return G_f, order
