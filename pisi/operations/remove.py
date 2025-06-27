# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

import sys

from pisi import translate as _

import pisi
import pisi.context as ctx
import pisi.atomicoperations as atomicoperations
import pisi.pgraph as pgraph
import pisi.util as util
import pisi.ui as ui
import pisi.db


def remove(
    packages, ignore_dep=False, ignore_safety=False, autoremove=False, force_prompt=False
):
    """Remove a set of packages from the system.
    Parameters:
        packages (list): A list of packages to remove.
        ignore_dep (bool): Ignore packages that depend on other packages.
        ignore_safety (bool): Ignore packages that are a part of the base system.
        autoremove (bool): Automatically remove dependencies of packages.
        force_prompt (bool): Force prompt for confirmation.
    """

    componentdb = pisi.db.componentdb.ComponentDB()
    installdb = pisi.db.installdb.InstallDB()

    should_ignore_safety = (not ctx.get_option("ignore_safety")
                            and not ctx.config.values.general.ignore_safety
                            and not ignore_safety)

    packages = [str(package) for package in packages]

    # filter packages that are not installed
    filtered = packages = set(packages)

    if should_ignore_safety:
        if componentdb.has_component("system.base"):
            systembase = set(componentdb.get_union_component("system.base").packages)
            refused = packages.intersection(systembase)
            if refused:
                raise pisi.Error(
                    _("Safety switch prevents the removal of " "following packages:\n")
                    + util.format_by_columns(sorted(refused))
                )
        else:
            ctx.ui.warning(
                _("Safety switch: The component system.base cannot be found.")
            )

    installed = []
    for package in packages:
        if installdb.has_package(package):
            installed.append(package)
        else:
            ctx.ui.info(_("Package %s does not exist. Cannot remove.") % package)
    packages = set(installed)

    if len(packages) == 0:
        ctx.ui.info(_("No packages to remove."))
        return False

    if not ctx.config.get_option("ignore_dependency") and not ignore_dep:
        if autoremove:
            graph, order = plan_autoremove(packages)
            sorted_packages = set(order)

            if should_ignore_safety:
                if componentdb.has_component("system.base"):
                    systembase = set(
                        componentdb.get_union_component("system.base").packages
                    )
                    refused = sorted_packages.intersection(systembase)
                    if refused:
                        raise pisi.Error(
                            _(
                                "Safety switch prevents the removal of "
                                "following packages:\n"
                            )
                            + util.format_by_columns(sorted(refused))
                        )
                else:
                    ctx.ui.warning(
                        _("Safety switch: The component system.base cannot be found.")
                    )

        else:
            graph, order = plan_remove(packages)
    else:
        order = packages

    # Print the list of packages to remove.
    ctx.ui.info(
        _(
            """The following list of packages will be removed
in the respective order to satisfy dependencies:
"""
        )
        + util.strlist(order)
    )

    # Don't prompt if we're just doing a dry run.
    # It could confuse users thinking that it will
    # still remove packages.
    if ctx.get_option("dry_run"):
        return True

    # Determine if we should prompt the user to confirm
    # the removal of packages.
    if len(order) > len(filtered) or force_prompt:
        if not ctx.ui.confirm(_("Do you want to continue?")):
            ctx.ui.warning(_("Package removal declined"))
            return False

    ctx.ui.notify(ui.packagestogo, order=order)

    # Remove the packages.
    try:
        for package in order:
            if installdb.has_package(package):
                atomicoperations.remove_single(package)
            else:
                ctx.ui.info(_("Package %s is not installed. Cannot remove.") % package)
    except Exception as e:
        raise e
    finally:
        ctx.exec_usysconf()


def remove_orphans(ignore_dep=False, ignore_safety=False):
    pg, pkgs = plan_autoremove_all()
    return remove(pkgs, ignore_dep, ignore_safety, autoremove=False, force_prompt=True)


def plan_remove(A):
    # try to construct a pisi graph of packages to
    # install / reinstall

    installdb = pisi.db.installdb.InstallDB()

    G_f = pgraph.PGraph(installdb)  # construct G_f

    # find the (install closure) graph of G_f by package
    # set A using packagedb
    for x in A:
        G_f.add_package(x)
    B = A
    while len(B) > 0:
        Bp = set()
        for x in B:
            rev_deps = installdb.get_rev_deps(x)
            for rev_dep, depinfo in rev_deps:
                # we don't deal with uninstalled rev deps
                # and unsatisfied dependencies (this is important, too)
                # satisfied_by_any_installed_other_than is for AnyDependency
                if (
                    installdb.has_package(rev_dep)
                    and depinfo.satisfied_by_installed()
                    and not depinfo.satisfied_by_any_installed_other_than(x)
                ):
                    if not rev_dep in G_f.vertices():
                        Bp.add(rev_dep)
                        G_f.add_plain_dep(rev_dep, x)
        B = Bp
    if ctx.config.get_option("debug"):
        G_f.write_graphviz(sys.stdout)
    order = G_f.topological_sort()
    return G_f, order


revdep_owner = None


def revdep_from_hell(idb, orphans, order, pkgname):
    """
    Evil in a box.
    """

    global revdep_owner

    revdeps = idb.get_rev_deps(pkgname)
    for name, rdep in revdeps:
        if name not in orphans and name not in order:
            revdep_owner = name
            return False
        if not revdep_from_hell(idb, orphans, order, name):
            return False
    return True


def plan_autoremove(name):
    """
    Attempt to plan the automatic removal of a package and associated
    automatically installed dependencies.

    This function will take special care to not remove auto-installed packages
    that are still in use by other packages not in this list.
    """
    idb = pisi.db.installdb.InstallDB()
    orphans = idb.list_auto_installed()
    pg, pkgs = plan_remove(name)
    order = pg.topological_sort()

    murderficate = set()

    # Build a first-leaf set of orphaned removals
    for pkgID in pkgs:
        pkg = idb.get_package(pkgID)
        for runtimeDep in pkg.runtimeDependencies():
            depName = runtimeDep.name()
            if depName not in orphans:
                continue
            if not revdep_from_hell(idb, orphans, order, depName):
                continue
            murderficate.add(depName)

    # Ensure our removal plan is consistent here
    murderficate.update(set(order))
    pg, pkgs = plan_remove(murderficate)

    newSet = set(pkgs)

    # Now for everyone we're removing, did that introduce through dependencies
    # a now-orphaned package?
    def depMangler(item):
        pkg = idb.get_package(item)
        for dep in pkg.runtimeDependencies():
            nom = dep.name()
            if nom in orphans and nom not in newSet:
                if revdep_from_hell(idb, orphans, pkgs, nom):
                    newSet.add(nom)
                    depMangler(nom)

    # Blast the whole pending list through the mangler
    for item in pkgs:
        depMangler(item)

    # Return the consistently ordered graph
    return plan_remove(newSet)


def plan_autoremove_all():
    """
    Attempt to automatically remove all ORPHANED automatically installed
    packages.

    This will not remove any package with a dependency outside the orphan
    set.
    """
    idb = pisi.db.installdb.InstallDB()
    orphans = idb.list_auto_installed()

    murderficate = set()
    for pkgID in orphans:
        if not idb.has_package(pkgID):
            continue
        if not revdep_from_hell(idb, orphans, murderficate, pkgID):
            continue
        murderficate.add(pkgID)

    return plan_remove(murderficate)


def list_orphans():
    """
    Helper function to return a list of potential orphans and parents
    """
    idb = pisi.db.installdb.InstallDB()
    orphans = idb.list_auto_installed()
    global revdep_owner

    ret = dict()
    for pkgID in orphans:
        if not idb.has_package(pkgID):
            continue
        if not revdep_from_hell(idb, orphans, list(ret.keys()), pkgID):
            ret[pkgID] = revdep_owner
            continue
        ret[pkgID] = None
    return ret


def remove_conflicting_packages(conflicts):
    if remove(conflicts, ignore_dep=True, ignore_safety=True):
        raise Exception(_("Conflicts remain"))


def remove_obsoleted_packages():
    installdb = pisi.db.installdb.InstallDB()
    packagedb = pisi.db.packagedb.PackageDB()
    obsoletes = list(filter(installdb.has_package, packagedb.get_obsoletes()))
    if obsoletes:
        if remove(obsoletes, ignore_dep=True, ignore_safety=True):
            raise Exception(_("Obsoleted packages remaining"))


def remove_replaced_packages(replaced):
    if remove(replaced, ignore_dep=True, ignore_safety=True):
        raise Exception(_("Replaced package remains"))
