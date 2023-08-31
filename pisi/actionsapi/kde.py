# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, 2017-Present Solus Developers
# SPDX-License-Identifier: GPL-2.0-or-later

# standard python modules
import os

from pisi import translate as _

# Pisi Modules
import pisi.context as ctx

# ActionsAPI Modules
import pisi.actionsapi
import pisi.actionsapi.get as get
from pisi.actionsapi.shelltools import system
from pisi.actionsapi.shelltools import can_access_file


class ConfigureError(pisi.actionsapi.Error):
    def __init__(self, value=""):
        pisi.actionsapi.Error.__init__(self, value)
        self.value = value
        ctx.ui.error(value)
        if can_access_file("config.log"):
            ctx.ui.error(
                _(
                    "\n!!! Please attach the config.log to your bug report:\n%s/config.log"
                )
                % os.getcwd()
            )


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


def configure(parameters=""):
    """parameters = '--with-nls --with-libusb --with-something-usefull"""
    if can_access_file("configure"):
        args = (
            "./configure \
                --prefix=%s \
                --build=%s \
                --with-x \
                --enable-mitshm \
                --with-xinerama \
                --with-qt-dir=%s \
                --enable-mt \
                --with-qt-libraries=%s/lib \
                --disable-dependency-tracking \
                --disable-debug \
                %s"
            % (get.kdeDIR(), get.HOST(), get.qtDIR(), get.qtDIR(), parameters)
        )

        if system(args):
            raise ConfigureError(_("Configure failed."))
    else:
        raise ConfigureError(_("No configure script found."))


def make(parameters=""):
    """make source with given parameters = "all" || "doc" etc."""
    if system("make %s %s" % (get.makeJOBS(), parameters)):
        raise MakeError(_("Make failed."))


def install(parameters="install"):
    if can_access_file("Makefile"):
        args = "make DESTDIR=%s destdir=%s %s" % (
            get.installDIR(),
            get.installDIR(),
            parameters,
        )

        if system(args):
            raise InstallError(_("Install failed."))
    else:
        raise InstallError(_("No Makefile found."))
