# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

import os

from pisi.scenarioapi.repoops import *
from pisi.scenarioapi.pisiops import *
from pisi.scenarioapi.constants import *


def let_repo_had(package, *args):
    repo_added_package(package, *args)
    repo_updated_index()


def let_pisi_had(*args):
    url = os.path.join(os.getcwd(), consts.repo_url)
    pisi_added_repo(consts.repo_name, url)
    packages = util.strlist(args).rstrip()
    os.system("pisi -D%s install --ignore-dependency %s" % (consts.pisi_db, packages))
