# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

import os

from ordered_set import OrderedSet as set

from requests import HTTPError

import pisi
import pisi.context as ctx
import pisi.util
import pisi.db
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


def __getpackageurl_binman(package):
    packagedb = pisi.db.packagedb.PackageDB()
    repodb = pisi.db.repodb.RepoDB()
    pkg, ver = pisi.util.parse_package_name(package)

    reponame = None
    try:
        reponame = packagedb.which_repo(pkg)
    except Exception:
        # Maybe this package is obsoluted from repository
        for repo in repodb.get_binary_repos():
            if pkg in packagedb.get_obsoletes(repo):
                reponame = repo

    if not reponame:
        raise PackageNotFound

    package_ = packagedb.get_package(pkg)
    repourl = repodb.get_repo_url(reponame)
    base_package = os.path.dirname(package_.packageURI)
    repo_base = os.path.dirname(repourl)
    possible_url = os.path.join(repo_base, base_package, package)
    ctx.ui.info(_("Package %s found in repository %s") % (pkg, reponame))

    # return _possible_ url for this package
    return possible_url


def __getpackageurl(package):
    packagedb = pisi.db.packagedb.PackageDB()
    repodb = pisi.db.repodb.RepoDB()
    pkg, ver = pisi.util.parse_package_name(package)

    reponame = None
    try:
        reponame = packagedb.which_repo(pkg)
    except Exception:
        # Maybe this package is obsoluted from repository
        for repo in repodb.get_binary_repos():
            if pkg in packagedb.get_obsoletes(repo):
                reponame = repo

    if not reponame:
        raise PackageNotFound

    repourl = repodb.get_repo_url(reponame)
    # return _possible_ url for this package
    return os.path.join(os.path.dirname(repourl), package)


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

    for pkg_name in beinstalled:
        pkg_file = pkg_name + ctx.const.package_suffix
        try:
            uri = pisi.file.File.make_uri(__getpackageurl_binman(pkg_file))
        except PackageNotFound:
            try:
                uri = pisi.file.File.make_uri(__getpackageurl(pkg_file))
            except PackageNotFound:
                errors.append(pkg_name)
                ctx.ui.info(
                    pisi.util.colorize(_("%s could not be found") % (pkg_name), "red")
                )
                continue

        dest = ctx.config.cached_packages_dir()
        filepath = os.path.join(dest, uri.filename())

        if not os.path.exists(filepath):
            fetch_items.append((uri, dest, uri.filename()))
        else:
            ctx.ui.info(_("%s [cached]") % uri.filename())
            paths.append(filepath)

    if fetch_items:
        ctx.ui.status(_("Downloading historical packages..."))
        try:
            fetcher.fetch_multi(fetch_items)
            for item in fetch_items:
                paths.append(os.path.join(item[1], item[2]))
        except Exception as e:
            ctx.ui.error(_("Error while fetching historical packages: %s") % str(e))
            # We might still have some packages, but maybe it's safer to stop or ask.

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
