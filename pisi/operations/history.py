# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

import os

from ordered_set import OrderedSet as set
from requests import HTTPError

import pisi
import pisi.context as ctx
import pisi.db
import pisi.package
import pisi.util
from pisi import translate as _
from pisi.fetcher import Fetcher


class PackageNotFound(pisi.Error):
    pass


def __pkg_already_installed(name, pkginfo):
    installdb = pisi.db.installdb.InstallDB()
    if not installdb.has_package(name):
        return False

    ver, rel = str(pkginfo).split("-")[:2]
    return (ver, rel) == installdb.get_version(name)[:-1]


def __listactions(actions):
    beinstalled = []
    beremoved = []
    configs = []

    installdb = pisi.db.installdb.InstallDB()
    for pkg in actions:
        action, pkginfo, operation = actions[pkg]
        if action == "install":
            if __pkg_already_installed(pkg, pkginfo):
                continue
            beinstalled.append("%s-%s" % (pkg, pkginfo))
            configs.append((pkg, operation))
        else:
            if installdb.has_package(pkg):
                beremoved.append("%s" % pkg)

    return beinstalled, beremoved, configs


def __get_package_resource(package_file):
    packagedb = pisi.db.packagedb.PackageDB()
    repodb = pisi.db.repodb.RepoDB()
    pkg_name, _ver = pisi.util.parse_package_name(package_file)

    reponame = None
    try:
        reponame = packagedb.which_repo(pkg_name)
    except Exception:
        # Maybe this package is obsoleted from repository
        for repo in repodb.get_binary_repos():
            if pkg_name in packagedb.get_obsoletes(repo):
                reponame = repo

    if not reponame:
        raise PackageNotFound

    repourl = repodb.get_repo_url(reponame)
    repo_base = os.path.dirname(repourl)

    # Try binman style first
    try:
        package_ = packagedb.get_package(pkg_name)
        base_package = os.path.dirname(package_.packageURI)
        url = os.path.join(repo_base, base_package, package_file)
    except Exception:
        # Fallback to simple style
        url = os.path.join(repo_base, package_file)

    ctx.ui.info(_("Package %s found in repository %s") % (pkg_name, reponame))

    uri = pisi.file.File.make_uri(url)
    dest = ctx.config.cached_packages_dir()
    filepath = os.path.join(dest, uri.filename())

    return pisi.package.PackageResource(
        name=pkg_name,
        uri=uri,
        repo=reponame,
        expected_hash=None,
        size=None,
        local_path=filepath,
    )


def fetch_remote_file(fetcher, package, errors):
    try:
        resource = __get_package_resource(package)
    except PackageNotFound:
        errors.append(package)
        ctx.ui.info(pisi.util.colorize(_("%s could not be found") % (package), "red"))
        return False

    if not os.path.exists(resource.local_path):
        try:
            fetcher.fetch(resource.uri, os.path.dirname(resource.local_path))
        except (HTTPError, IOError, ValueError):
            errors.append(package)
            ctx.ui.info(pisi.util.colorize(_(f"{package} could not be found"), "red"))
            return False
    else:
        ctx.ui.info(_("%s [cached]") % resource.uri.filename())
    return True


def get_snapshot_actions(operation):
    actions = {}
    snapshot_pkgs = set()
    installdb = pisi.db.installdb.InstallDB()

    for pkg in operation.packages:
        snapshot_pkgs.add(pkg.name)
        actions[pkg.name] = ("install", pkg.before, operation.no)

    for pkg in set(installdb.list_installed()) - snapshot_pkgs:
        actions[pkg] = ("remove", None, None)

    return actions


def get_takeback_actions(operation):
    actions = {}
    historydb = pisi.db.historydb.HistoryDB()

    for operation in historydb.get_till_operation(operation):
        if operation.type == "snapshot":
            pass

        for pkg in operation.packages:
            if pkg.operation in ["upgrade", "downgrade", "remove"]:
                actions[pkg.name] = ("install", pkg.before, operation.no)
            if pkg.operation == "install":
                actions[pkg.name] = ("remove", None, operation.no)

    return actions


def plan_takeback(operation):
    historydb = pisi.db.historydb.HistoryDB()
    op = historydb.get_operation(operation)
    if op.type == "snapshot":
        actions = get_snapshot_actions(op)
    else:
        actions = get_takeback_actions(operation)

    return __listactions(actions)


def takeback(operation):
    historydb = pisi.db.historydb.HistoryDB()
    beinstalled, beremoved, configs = plan_takeback(operation)
    fetcher = Fetcher()

    if beinstalled:
        ctx.ui.info(
            _("Following packages will be installed:\n")
            + pisi.util.strlist(beinstalled)
        )

    if beremoved:
        ctx.ui.info(
            _("Following packages will be removed:\n") + pisi.util.strlist(beremoved)
        )

    if (beremoved or beinstalled) and not ctx.ui.confirm(_("Do you want to continue?")):
        return

    errors = []
    paths = []
    fetch_items = []
    fetch_map = {}

    for pkg_name in beinstalled:
        pkg_file = pkg_name + ctx.const.package_suffix
        try:
            resource = __get_package_resource(pkg_file)
        except PackageNotFound:
            errors.append(pkg_name)
            ctx.ui.info(
                pisi.util.colorize(_("%s could not be found") % (pkg_name), "red")
            )
            continue

        if not os.path.exists(resource.local_path):
            fetch_items.append(resource)
            fetch_map[resource] = pkg_name
        else:
            ctx.ui.info(_("%s [cached]") % resource.uri.filename())
            paths.append(resource.local_path)

    if fetch_items:
        ctx.ui.status(_("Downloading historical packages..."))
        try:
            fetcher.fetch_multi(fetch_items)
        except Exception as e:
            ctx.ui.error(_("Error while fetching historical packages: %s") % str(e))

        for resource in fetch_items:
            if os.path.exists(resource.local_path):
                paths.append(resource.local_path)
            else:
                pkg_name = fetch_map.get(resource, resource.name)
                if pkg_name not in errors:
                    errors.append(pkg_name)

    if errors:
        ctx.ui.info(
            _(
                "\nFollowing packages could not be found in repositories and are not cached:\n"
            )
            + pisi.util.strlist(errors)
        )
        if not ctx.ui.confirm(_("Do you want to continue?")):
            return

    if beremoved:
        pisi.operations.remove.remove(beremoved, True, True)

    if paths:
        pisi.operations.install.install_pkg_files(paths, True)

    for pkg, operation in configs:
        historydb.load_config(operation, pkg)
