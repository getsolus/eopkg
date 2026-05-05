# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

import os

from ordered_set import OrderedSet as set
from pisi import translate as _
from pisi import Error

import pisi
import pisi.context as ctx
import pisi.util as util
import pisi.ui as ui
import pisi.conflict
import pisi.db


def reorder_base_packages_old(order):
    componentdb = pisi.db.componentdb.ComponentDB()

    """system.base packages must be first in order"""
    systembase = componentdb.get_union_component("system.base").packages

    systembase_order = []
    nonbase_order = []
    for pkg in order:
        if pkg in systembase:
            systembase_order.append(pkg)
        else:
            nonbase_order.append(pkg)

    install_order = systembase_order + nonbase_order
    ctx.ui.warning(_("Reordering install order so system.base packages come first."))
    if len(install_order) > 1 and ctx.config.get_option("debug"):
        ctx.ui.info(_("install_order: %s" % install_order))
    return install_order

def reorder_base_packages(order):
    """Dummy function that doesn't actually re-order system.base in front.

       We now use OrderedSets, which keep the original topological sort,
       so this shouldn't actually be necessary now.

       This also implies that the only function of system.base is for the
       packages in it to be un-removable.
    """
    if len(order) > 1 and ctx.config.get_option("debug"):
        ctx.ui.info(_("order: %s" % order))
    return order

def check_conflicts(order, packagedb):
    """check if upgrading to the latest versions will cause havoc
    done in a simple minded way without regard for dependencies of
    conflicts, etc."""

    (C, D, pkg_conflicts) = pisi.conflict.calculate_conflicts(order, packagedb)

    if D:
        raise Error(
            _("Selected packages [%s] are in conflict with each other.")
            % util.strlist(list(D))
        )

    if pkg_conflicts:
        conflicts = ""
        for pkg in list(pkg_conflicts.keys()):
            conflicts += _("[%s conflicts with: %s]\n") % (
                pkg,
                util.strlist(pkg_conflicts[pkg]),
            )

        ctx.ui.info(_("The following packages have conflicts:\n%s") % conflicts)

        if not ctx.ui.confirm(_("Remove the following conflicting packages?")):
            raise Error(_("Conflicting packages should be removed to continue"))

    return list(C)


def expand_src_components(A):
    componentdb = pisi.db.componentdb.ComponentDB()
    Ap = set()
    for x in A:
        if componentdb.has_component(x):
            Ap = Ap.union(componentdb.get_union_component(x).sources)
        else:
            Ap.add(x)
    return Ap


def extract_automatic(A, total):
    """
    Determine all automatic dependencies in the graph.

    This is only applicable to packages coming from the repo
    """

    ret = set()
    installdb = pisi.db.installdb.InstallDB()
    packagedb = pisi.db.packagedb.PackageDB()

    for i in total:
        if i in A:
            continue
        repoVariant = packagedb.get_package(i)
        # system.base candidate is never "automatic" ...
        if repoVariant.partOf == "system.base":
            continue
        if installdb.has_package(i):
            continue
        ret.add(i)

    return ret


def calculate_download_sizes(order):
    download_info = get_download_info(order)
    total_size = sum(info["size"] for info in download_info)
    cached_size = sum(info["cached_size"] for info in download_info)

    ctx.ui.notify(ui.cached, total=total_size, cached=cached_size)
    return total_size, cached_size


def get_download_info(order):
    """
    Returns a list of dicts containing download info for each package in order.
    """
    download_info = []
    installdb = pisi.db.installdb.InstallDB()
    packagedb = pisi.db.packagedb.PackageDB()
    repodb = pisi.db.repodb.RepoDB()

    try:
        cached_packages_dir = ctx.config.cached_packages_dir()
    except OSError:
        # happens when cached_packages_dir tried to be created by an unpriviledged user
        cached_packages_dir = None

    for name in order:
        repo_name = packagedb.which_repo(name)
        if not repo_name:
            raise Error(_("Package %s not found in any active repository.") % name)

        repo = repodb.get_repo(repo_name)
        pkg = packagedb.get_package(name)
        delta = None

        if installdb.has_package(pkg.name):
            (
                version,
                release,
                build,
                distro,
                distro_release,
            ) = installdb.get_version_and_distro_release(pkg.name)
            if distro_release == pkg.distributionRelease:
                delta = pkg.get_delta(release)

        ignore_delta = ctx.config.values.general.ignore_delta

        if delta and not ignore_delta:
            pkg_uri_str = delta.packageURI
            pkg_hash = delta.packageHash
            pkg_size = delta.packageSize
        else:
            pkg_uri_str = pkg.packageURI
            pkg_hash = pkg.packageHash
            pkg_size = pkg.packageSize

        uri = pisi.uri.URI(pkg_uri_str)
        if not uri.is_absolute_path():
            pkg_uri_str = os.path.join(
                os.path.dirname(repo.indexuri.get_uri()), str(uri.path())
            )

        uri = pisi.uri.URI(pkg_uri_str)

        info = {
            "name": name,
            "uri": uri,
            "hash": pkg_hash,
            "size": pkg_size,
        }

        if cached_packages_dir and uri.is_remote_file():
            path = util.join_path(cached_packages_dir, uri.filename())
            # check the file and sha1sum to be sure it _is_ the cached package
            if os.path.exists(path) and util.sha1_file(path) == pkg_hash:
                info["cached"] = True
                info["cached_size"] = pkg_size
            else:
                info["cached"] = False
                part_path = "%s.part" % path
                if os.path.exists(part_path):
                    info["cached_size"] = os.stat(part_path).st_size
                else:
                    info["cached_size"] = 0
        else:
            info["cached"] = not uri.is_remote_file()
            info["cached_size"] = pkg_size if info["cached"] else 0

        download_info.append(info)

    return download_info


def fetch_packages(order):
    """
    Fetches all packages in order concurrently if they are not already cached.
    """
    download_info = get_download_info(order)
    items_to_fetch = []
    cached_packages_dir = ctx.config.cached_packages_dir()

    for info in download_info:
        if not info["cached"] and info["uri"].is_remote_file():
            items_to_fetch.append(
                (info["uri"], cached_packages_dir, info["uri"].filename())
            )

    if items_to_fetch:
        fetcher = Fetcher()
        fetcher.fetch_multi(items_to_fetch)
