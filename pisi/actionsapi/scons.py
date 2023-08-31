# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, 2017-Present Solus Developers
# SPDX-License-Identifier: GPL-2.0-or-later


# Pisi Modules
import pisi.context as ctx

from pisi import translate as _

# ActionsAPI Modules
import pisi.actionsapi
import pisi.actionsapi.get as get
from pisi.actionsapi.shelltools import system


class MakeError(pisi.actionsapi.Error):
    def __init__(self, value=""):
        pisi.actionsapi.Error.__init__(self, value)
        self.value = value
        ctx.ui.error(value)


class InstallError(pisi.actionsapi.Error):
    def __init__(self, value=""):
        pisi.actionsapi.Error.__init__(self, value)
        self.value = value
        ctx.ui.error(value)


def make(parameters=""):
    if system("scons %s %s" % (get.makeJOBS(), parameters)):
        raise MakeError(_("Make failed."))


def install(parameters="install", prefix=get.installDIR(), argument="prefix"):
    if system("scons %s=%s %s" % (argument, prefix, parameters)):
        raise InstallError(_("Install failed."))
