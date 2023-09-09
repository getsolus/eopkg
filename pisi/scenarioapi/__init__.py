# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

import pisi


class Error(pisi.Error):
    pass


class Exception(pisi.Exception):
    pass


import pisi.context as ctx


def error(msg):
    if ctx.config.get_option("ignore_action_errors"):
        ctx.ui.error(msg)
    else:
        raise Error(msg)
