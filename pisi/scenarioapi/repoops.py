# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

import os

from pisi.scenarioapi.package import Package
from pisi.scenarioapi.withops import *
from pisi.scenarioapi.constants import *

from pisi import translate as _

repodb = {}


def repo_added_package(package, *args):
    if package in repodb:
        raise Exception(_("Repo already has package named %s.") % package)

    version = "1.0"
    partOf = "None"
    dependencies = []
    conflicts = []

    for _with in args:
        if _with.types == CONFLICT and _with.action == INIT:
            conflicts = _with.data

        if _with.types == DEPENDENCY and _with.action == INIT:
            dependencies = _with.data

        if _with.types == VERSION and _with.action == INIT:
            version = _with.data

        if _with.types == PARTOF and _with.action == INIT:
            partOf = _with.data

    repodb[package] = Package(
        package, dependencies, conflicts, ver=version, partOf=partOf
    )


def repo_removed_package(package):
    if package not in repodb:
        raise Exception(_("Repo does not have package named %s.") % package)

    os.unlink(os.path.join(consts.repo_path, repodb[package].get_file_name()))
    del repodb[package]


def repo_version_bumped(package, *args):
    if package not in repodb:
        raise Exception(_("Repo does not have package named %s.") % package)

    old_file = repodb[package].get_file_name()
    repodb[package].version_bump(*args)
    os.unlink(os.path.join(consts.repo_path, old_file))


def repo_updated_index():
    cur = os.getcwd()
    path = os.path.join(cur, consts.repo_path)
    os.chdir(consts.repo_path)
    os.system("pisi index --skip-signing %s >/dev/null 2>&1" % path)
    os.chdir(cur)


def repo_get_url():
    return "."
