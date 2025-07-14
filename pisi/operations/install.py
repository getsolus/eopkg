# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

import os
import sys
import zipfile

from ordered_set import OrderedSet as set
from pisi import translate as _

import pisi
import pisi.context as ctx
import pisi.util as util
import pisi.atomicoperations as atomicoperations
import pisi.operations as operations
import pisi.pgraph as pgraph
import pisi.ui as ui
import pisi.db

BASELAYOUT_PKG = 'baselayout'
EOPKG_PKG = 'eopkg'

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

def install_pkg_names(packages, reinstall=False):
    """
    Installs packages from the repository.

        Parameters:
            packages (list): List of package names
            reinstall (bool): Reinstall packages
    """

    installdb = pisi.db.installdb.InstallDB()
    packagedb = pisi.db.packagedb.PackageDB()

    packages = [str(package) for package in packages]  # FIXME: why do we still get unicode input here? :/ -- exa

    deduped_packages = packages = set(packages)

    # filter packages that are already installed
    if not reinstall:
        not_installed = set([package for package in packages if not installdb.has_package(package)])
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

    ctx.ui.notify(ui.packagestogo, order=order)

    automatic = operations.helper.extract_automatic(packages, order)
    paths = []
    for package in order:
        ctx.ui.info(
            util.colorize(
                _("Downloading %d / %d") % (order.index(package) + 1, len(order)), "yellow"
            )
        )
        install_op = atomicoperations.Install.from_name(package)
        paths.append(install_op.package_fname)

    ctx.ui.status(_("Finished downloading package upgrades."))

    # Don't actually install if --fetch-only was set
    if ctx.get_option("fetch_only"):
        return True

    # Remove conflicting packages
    if not ctx.get_option("ignore_package_conflicts"):
        conflicts = operations.helper.check_conflicts(order, packagedb)

        if conflicts:
            operations.remove.remove_conflicting_packages(conflicts)

    # Install all the packages
    ctx.disable_keyboard_interrupts()

    try:
        for path in paths:
            ctx.ui.info(
                util.colorize(
                    _("Installing %d / %d") % (paths.index(path) + 1, len(paths)),
                    "yellow",
                )
            )
            install_op = atomicoperations.Install(path)
            if install_op.pkginfo.name in automatic:
                install_op.automatic = True
            install_op.install(False)
    except Exception as e:
        raise e
    finally:
        ctx.exec_usysconf()

    ctx.enable_keyboard_interrupts()

    return True


def install_pkg_files(package_URIs, reinstall=False):
    """install a number of pisi package files"""

    installdb = pisi.db.installdb.InstallDB()
    ctx.ui.debug("A = %s" % str(package_URIs))

    for x in package_URIs:
        if not x.endswith(ctx.const.package_suffix):
            raise Exception(_("Mixing file names and package names not supported yet."))

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

    if ctx.config.get_option("ignore_dependency"):
        # simple code path then
        for x in package_URIs:
            atomicoperations.install_single_file(x, reinstall)
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
                raise Exception(
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
                raise Exception(
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
            raise Exception(_("External dependencies not satisfied: %s") % dep)

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
            raise Exception(_("External dependencies not satisfied"))
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

    ctx.ui.notify(ui.packagestogo, order=order)

    try:
        for x in order:
            atomicoperations.install_single_file(dfn[x], reinstall)
    except Exception as e:
        raise e
        return False
    finally:
        ctx.exec_usysconf()

    return True


def plan_install_pkg_names(A):
    # try to construct a pisi graph of packages to
    # install / reinstall

    packagedb = pisi.db.packagedb.PackageDB()
    installdb = pisi.db.installdb.InstallDB()

    # Check if updates are available to opt into the slow path
    available_updates = list()
    if len(pisi.api.list_upgradable()) != 0 and not ctx.get_option(
        "ignore_revdeps_of_deps_check"
    ):
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
                        raise Exception(
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
