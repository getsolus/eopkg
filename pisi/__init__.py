# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later


import atexit
import gettext
import importlib
import locale
import logging
import logging.handlers
import os
import sys
from importlib.resources import files


locale.setlocale(locale.LC_ALL, "")

try:
    _localeres = files("pisi.data").joinpath("locale")
    if _localeres.is_dir():
        _localedir: str | None = str(_localeres)
    else:
        _localedir = None  # Use the system one.

    # You usually want to import this function with the "_" alias.
    lang = gettext.translation(
        "pisi", localedir=_localedir, languages=[locale.getlocale()[0]]
    )

    translate = lang.gettext
    ngettext = lang.ngettext
except:
    # No .mo files found. Just return plain English.
    def translate(msg):
        return msg

    def ngettext(singular, plural, n):
        if (n == 1):
            return singular
        else
            return plural

__version__ = "4.1.6"

__all__ = ["api", "configfile", "db"]


# FIXME: Exception shadows builtin Exception. This is no good.
class Exception(Exception):
    """Class of exceptions that must be caught and handled within eopkg"""

    def __str__(self):
        s = ""
        for x in self.args:
            if s != "":
                s += "\n"
            s += str(x)
        return s


class Error(Exception):
    """Class of exceptions that lead to program termination"""

    pass


# Keep these imports here, not on top of the file!
# It's a circular dependency otherwise.
import pisi.api
import pisi.config
from pisi import context as ctx


def init_logging():
    log_dir = os.path.join(ctx.config.dest_dir(), ctx.config.log_dir())
    if os.access(log_dir, os.W_OK) and "distutils.core" not in sys.modules:
        handler = logging.handlers.RotatingFileHandler("%s/eopkg.log" % log_dir)
        formatter = logging.Formatter("%(asctime)-12s: %(levelname)-8s %(message)s")
        handler.setFormatter(formatter)
        ctx.log = logging.getLogger("pisi")
        ctx.log.addHandler(handler)
        ctx.loghandler = handler
        ctx.log.setLevel(logging.DEBUG)


def _cleanup():
    """Close the database cleanly and do other cleanup."""
    ctx.disable_keyboard_interrupts()
    if ctx.log:
        ctx.loghandler.flush()
        ctx.log.removeHandler(ctx.loghandler)

    filesdb = pisi.db.filesdb.FilesDB()
    if filesdb.is_initialized():
        filesdb.close()

    if ctx.build_leftover and os.path.exists(ctx.build_leftover):
        os.unlink(ctx.build_leftover)

    ctx.ui.close()
    ctx.enable_keyboard_interrupts()


# Hack for pisi to work with non-patched Python. pisi needs
# lots of work for not doing this.
importlib.reload(sys)

atexit.register(_cleanup)

ctx.config = pisi.config.Config()
init_logging()
