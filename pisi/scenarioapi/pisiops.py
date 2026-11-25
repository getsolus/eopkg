# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

import os
import pisi.util as util
from pisi.scenarioapi.constants import *


def pisi_upgraded(*args):
    util.system("pisi", "-D", consts.pisi_db, "upgrade", *args)


def pisi_info(package):
    util.system("pisi", "-D", consts.pisi_db, "info", package)


def pisi_removed(*args):
    util.system("pisi", "-D", consts.pisi_db, "remove", *args)


def pisi_added_repo(name, url):
    util.system("pisi", "-D", consts.pisi_db, "add-repo", "-y", name, url)


def pisi_updated_repo():
    util.system("pisi", "-D", consts.pisi_db, "update-repo")


def pisi_installed(*args):
    util.system("pisi", "-D", consts.pisi_db, "install", *args)


def pisi_reinstalled(package):
    util.system("pisi", "-D", consts.pisi_db, "install", "--reinstall", package)
