# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

# global variables here

import signal
import os

import pisi.context as ctx
import pisi.constants
import pisi.signalhandler
import pisi.ui

from pisi import translate as _

const = pisi.constants.Constants()
sig = pisi.signalhandler.SignalHandler()

config = None

log = None

# used for bug #10568
locked = False


def set_option(opt, val):
    config.set_option(opt, val)


def get_option(opt):
    return config and config.get_option(opt)


ui = pisi.ui.UI()

# stdout, stderr for eopkg API
stdout = None
stderr = None

# usysconf binary
usysconf_binary = "/usr/sbin/usysconf"
can_usysconf = True

# Bug #2879
# FIXME: Maybe we can create a simple rollback mechanism. There are other
# places which need this, too.
# this is needed in build process to clean after if something goes wrong.
build_leftover = None


def exec_usysconf():
    """Just stick this all in the one place"""
    global ui
    global usysconf_binary
    global can_usysconf

    if not can_usysconf:
        return

    # We must survive not having usysconf just in case of derp.
    if not os.path.exists(usysconf_binary):
        ui.error(_("usysconf not installed. Please upgrade!"))
        return

    # Tell UI tools the system configuration is running
    try:
        ui.notify(pisi.ui.systemconf)
    except:
        pass

    try:
        os.system("{} run".format(usysconf_binary))
    except Exception as e:
        if ctx:
            ctx.ui.error(_("Failed to configure system"))
        raise e
