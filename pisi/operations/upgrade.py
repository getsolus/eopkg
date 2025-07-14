# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

import sys

from ordered_set import OrderedSet as set
from pisi import translate as _

import pisi
import pisi.ui as ui
import pisi.context as ctx
import pisi.pgraph as pgraph
import pisi.atomicoperations as atomicoperations
import pisi.operations as operations
import pisi.util as util
import pisi.db
import pisi.blacklist


def check_update_actions(packages):
    installdb = pisi.db.installdb.InstallDB()
    packagedb = pisi.db.packagedb.PackageDB()

    actions = {}

    for package in packages:
        if not installdb.has_package(package):
            continue

        pkg = packagedb.get_package(package)
        version, release, build = installdb.get_version(package)
        pkg_actions = pkg.get_update_actions(release)

        for action_name, action_targets in list(pkg_actions.items()):
            item = actions.setdefault(action_name, [])
            for action_target in action_targets:
                item.append((package, action_target))

    has_actions = False

    if "systemRestart" in actions:
        has_actions = True
        ctx.ui.warning(
            _(
                "You must restart your system for the updates "
                "in the following package(s) to take effect:"
            )
        )
        for package, target in actions["systemRestart"]:
            ctx.ui.info("    - %s" % package)

    return has_actions


def find_upgrades(packages, replaces):
    packagedb = pisi.db.packagedb.PackageDB()
    installdb = pisi.db.installdb.InstallDB()

    security_only = ctx.get_option("security_only")

    Ap = []
    for i_pkg in packages:
        if i_pkg in list(replaces.keys()):
            # Replaced packages will be forced for upgrade, cause replaced packages are marked as obsoleted also. So we
            # pass them.
            continue

        if i_pkg.endswith(ctx.const.package_suffix):
            ctx.ui.debug(_("Warning: package *name* ends with '.pisi'"))

        if not installdb.has_package(i_pkg):
            ctx.ui.info(_("Package %s is not installed.") % i_pkg, True)
            continue

        if not packagedb.has_package(i_pkg):
            ctx.ui.info(_("Package %s is not available in repositories.") % i_pkg, True)
            continue

        pkg = packagedb.get_package(i_pkg)
        (
            version,
            release,
            build,
            distro,
            distro_release,
        ) = installdb.get_version_and_distro_release(i_pkg)

        if security_only and not pkg.has_update_type("security", release):
            continue

        if pkg.distribution == distro and pisi.version.make_version(
            pkg.distributionRelease
        ) > pisi.version.make_version(distro_release):
            Ap.append(i_pkg)

        else:
            if int(release) < int(pkg.release):
                Ap.append(i_pkg)
            else:
                ctx.ui.info(
                    _("Package %s is already at the latest release %s.")
                    % (pkg.name, pkg.release),
                    True,
                )

    return Ap


def upgrade(packages = [], repo = None):
    """
    Re-installs packages from the repository, trying to perform
    a minimum or maximum number of upgrades according to options.

        Parameters:
            packages (list): A list of packages to upgrade.
            repo (str): A repository to use.
    """

    packagedb = pisi.db.packagedb.PackageDB()
    installdb = pisi.db.installdb.InstallDB()
    replaces = packagedb.get_replaces()

    if not packages:
        # if packages is empty, then upgrade all packages
        packages = installdb.list_installed()

    if repo:
        repo_packages = set(packagedb.list_packages(repo))
        packages = set(packages).intersection(repo_packages)

    deduped_packages = packages = set(packages)
    upgrades = find_upgrades(packages, replaces)
    packages = set(upgrades)

    # Force upgrading of installed but replaced packages or else they will be removed (they are obsoleted also).
    # This is not wanted for a replaced driver package (eg. nvidia-X).
    replaced = set(pisi.util.flatten_list(list(replaces.values())))
    packages |= replaced
    packages |= upgrade_base(packages)

    # Figure out excluded packages
    packages = pisi.blacklist.exclude_from(packages, ctx.const.blacklist)

    if ctx.get_option("exclude_from"):
        packages = pisi.blacklist.exclude_from(packages, ctx.get_option("exclude_from"))

    if ctx.get_option("exclude"):
        packages = pisi.blacklist.exclude(packages, ctx.get_option("exclude"))

    ctx.ui.debug("packages = %s" % str(packages))

    if len(packages) == 0:
        ctx.ui.info(_("No packages to upgrade."))
        return True

    ctx.ui.debug("packages = %s" % str(packages))

    if not ctx.config.get_option("ignore_dependency"):
        graph, order = plan_upgrade(packages, replaces=replaces)
    else:
        graph = None
        order = list(packages)

    componentdb = pisi.db.componentdb.ComponentDB()

    # Bug 4211
    if componentdb.has_component("system.base"):
        order = operations.helper.reorder_base_packages(order)

    # Show what packages will be upgraded/fetched
    if ctx.get_option("fetch_only"):
        ctx.ui.status(_("The following packages will be downloaded:"))
    else:
        ctx.ui.status(_("The following packages will be upgraded:"))

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

    needs_confirm = check_update_actions(order)

    # Figure out if we have additional packages to install
    # for the upgrade to be successful
    if set(order) - deduped_packages - replaced:
        ctx.ui.warning(_("There are extra packages due to dependencies."))
        needs_confirm = True

    if needs_confirm and not ctx.ui.confirm(_("Do you want to continue?")):
        return False

    ctx.ui.notify(ui.packagestogo, order=order)

    # Detect package conflicts
    conflicts = []
    if not ctx.get_option("ignore_package_conflicts"):
        conflicts = operations.helper.check_conflicts(order, packagedb)

    automatic = operations.helper.extract_automatic(packages, order)
    paths = []
    for x in order:
        ctx.ui.info(
            util.colorize(
                _("Downloading %d / %d") % (order.index(x) + 1, len(order)), "yellow"
            )
        )
        install_op = atomicoperations.Install.from_name(x)
        paths.append(install_op.package_fname)

    ctx.ui.status(_("Finished downloading package upgrades."))

    # Don't actually install if --fetch-only was set
    if ctx.get_option("fetch_only"):
        return True

    # Handle package conflicts
    if conflicts:
        operations.remove.remove_conflicting_packages(conflicts)

    operations.remove.remove_obsoleted_packages()

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
            install_op = atomicoperations.Install(path, ignore_file_conflicts=True)
            if install_op.pkginfo.name in automatic:
                install_op.automatic = True
            install_op.install(True)
    except Exception as e:
        raise e
    finally:
        ctx.exec_usysconf()

    ctx.enable_keyboard_interrupts()

    return True


def plan_upgrade(A, force_replaced=True, replaces=None):
    # FIXME: remove force_replaced
    # try to construct a pisi graph of packages to
    # install / reinstall

    packagedb = pisi.db.packagedb.PackageDB()

    G_f = pgraph.PGraph(packagedb)  # construct G_f

    A = set(A)

    # Force upgrading of installed but replaced packages or else they will be removed (they are obsoleted also).
    # This is not wanted for a replaced driver package (eg. nvidia-X).
    #
    # FIXME: this is also not nice. this would not be needed if replaced packages are not written as obsoleted also.
    # But if they are not written obsoleted "pisi index" indexes them
    if force_replaced:
        if replaces is None:
            replaces = packagedb.get_replaces()
        A |= set(pisi.util.flatten_list(list(replaces.values())))

    # find the "install closure" graph of G_f by package
    # set A using packagedb
    for x in A:
        G_f.add_package(x)

    installdb = pisi.db.installdb.InstallDB()

    def add_runtime_deps(pkg, Bp):
        for dep in pkg.runtimeDependencies():
            # add packages that can be upgraded
            if installdb.has_package(dep.package) and dep.satisfied_by_installed():
                continue

            if dep.satisfied_by_repo():
                if not dep.package in G_f.vertices():
                    Bp.add(str(dep.package))

                # Always add the dependency info although the dependant
                # package is already a member of this graph. Upgrade order
                # might change if the dependency info differs from the
                # previous ones.
                G_f.add_dep(pkg.name, dep)
            else:
                ctx.ui.error(
                    _("Dependency %s of %s cannot be satisfied") % (dep, pkg.name)
                )
                raise Exception(_("Upgrade is not possible."))

    def add_resolvable_conflicts(pkg, Bp):
        """Try to resolve conflicts by upgrading

        If a package B conflicts with an old version of package A and
        does not conflict with the new version of A, add A to the upgrade list.
        """
        for conflict in pkg.conflicts:
            if conflict.package in G_f.vertices():
                # Conflicting package is already in the upgrade list.
                continue

            if not pisi.conflict.installed_package_conflicts(conflict):
                # Conflicting package is not installed.
                # No need to deal with it.
                continue

            if not packagedb.has_package(conflict.package):
                # Conflicting package is not available in repo.
                # Installed package will be removed.
                continue

            new_pkg = packagedb.get_package(conflict.package)
            if conflict.satisfies_relation(new_pkg.version, new_pkg.release):
                # Package still conflicts with the repo package.
                # Installed package will be removed.
                continue

            # Upgrading the package will resolve conflict.
            # Add it to the upgrade list.
            Bp.add(conflict.package)
            G_f.add_package(conflict.package)

    def add_broken_revdeps(pkg, Bp):
        # Search reverse dependencies to see if anything
        # should be upgraded
        rev_deps = installdb.get_rev_deps(pkg.name)
        for rev_dep, depinfo in rev_deps:
            # add only installed but unsatisfied reverse dependencies
            if rev_dep in G_f.vertices() or depinfo.satisfied_by_repo():
                continue

            if is_upgradable(rev_dep):
                Bp.add(rev_dep)
                G_f.add_plain_dep(rev_dep, pkg.name)

    def add_needed_revdeps(pkg, Bp):
        # Search for reverse dependency update needs of to be upgraded packages
        # check only the installed ones.
        version, release, build = installdb.get_version(pkg.name)
        actions = pkg.get_update_actions(release)

        packages = actions.get("reverseDependencyUpdate")
        if packages:
            for target_package in packages:
                for name, dep in installdb.get_rev_deps(target_package):
                    if name in G_f.vertices() or not is_upgradable(name):
                        continue

                    Bp.add(name)
                    G_f.add_plain_dep(name, target_package)

    while A:
        Bp = set()

        for x in A:
            pkg = packagedb.get_package(x)

            add_runtime_deps(pkg, Bp)
            add_resolvable_conflicts(pkg, Bp)

            if installdb.has_package(x):
                add_broken_revdeps(pkg, Bp)
                add_needed_revdeps(pkg, Bp)

        A = Bp

    if ctx.config.get_option("debug"):
        G_f.write_graphviz(sys.stdout)

    order = G_f.topological_sort()
    order = operations.install.plan_deterministic_install_order(order)
    order.reverse()
    return G_f, order


def upgrade_base(A=set()):
    installdb = pisi.db.installdb.InstallDB()
    componentdb = pisi.db.componentdb.ComponentDB()
    if not ctx.config.values.general.ignore_safety and not ctx.get_option(
        "ignore_safety"
    ):
        if componentdb.has_component("system.base"):
            systembase = set(componentdb.get_union_component("system.base").packages)
            extra_installs = [
                x for x in systembase - set(A) if not installdb.has_package(x)
            ]
            extra_installs = pisi.blacklist.exclude_from(
                extra_installs, ctx.const.blacklist
            )
            if extra_installs:
                ctx.ui.warning(
                    _("Safety switch forces the installation of " "following packages:")
                )
                ctx.ui.info(util.format_by_columns(sorted(extra_installs)))
            G_f, install_order = operations.install.plan_install_pkg_names(
                extra_installs
            )
            extra_upgrades = [
                x for x in systembase - set(install_order) if is_upgradable(x)
            ]
            upgrade_order = []

            extra_upgrades = pisi.blacklist.exclude_from(
                extra_upgrades, ctx.const.blacklist
            )

            if ctx.get_option("exclude_from"):
                extra_upgrades = pisi.blacklist.exclude_from(
                    extra_upgrades, ctx.get_option("exclude_from")
                )

            if ctx.get_option("exclude"):
                extra_upgrades = pisi.blacklist.exclude(
                    extra_upgrades, ctx.get_option("exclude")
                )

            if extra_upgrades:
                ctx.ui.warning(
                    _("Safety switch forces the upgrade of " "following packages:")
                )
                ctx.ui.info(util.format_by_columns(sorted(extra_upgrades)))
                G_f, upgrade_order = plan_upgrade(extra_upgrades, force_replaced=False)

             # return packages that must be added to any installation
            install_and_upgrade_order = set(install_order + upgrade_order)
            if len(install_and_upgrade_order) > 1 and ctx.config.get_option("debug"):
                ctx.ui.info(_("installs and upgrades (unordered): %s" % install_and_upgrade_order))
            install_and_upgrade_order = operations.install.plan_deterministic_install_order(install_and_upgrade_order)
            if len(install_and_upgrade_order) > 1 and ctx.config.get_option("debug"):
                ctx.ui.info(_("installs and upgrades (deterministic order): %s" % install_and_upgrade_order))
            return install_and_upgrade_order
        else:
            ctx.ui.warning(
                _("Safety switch: The component system.base cannot be found.")
            )
    return set()


def is_upgradable(name):
    installdb = pisi.db.installdb.InstallDB()

    if not installdb.has_package(name):
        return False

    (
        i_version,
        i_release,
        i_build,
        i_distro,
        i_distro_release,
    ) = installdb.get_version_and_distro_release(name)

    packagedb = pisi.db.packagedb.PackageDB()

    try:
        (
            version,
            release,
            build,
            distro,
            distro_release,
        ) = packagedb.get_version_and_distro_release(name, packagedb.which_repo(name))
    except KeyboardInterrupt:
        raise
    # FIXME: what exception could we catch here, replace with that.
    except Exception:
        return False

    if distro == i_distro and pisi.version.make_version(
        distro_release
    ) > pisi.version.make_version(i_distro_release):
        return True

    return int(i_release) < int(release)
