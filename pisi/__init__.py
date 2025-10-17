# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later


import atexit
import gettext
import importlib
import locale
import logging
import logging.handlers
import os
import signal
import sys
from importlib.resources import files

import pisi.signalhandler as signalhandler


try:
    locale.setlocale(locale.LC_ALL, "")
except locale.Error as e:
    print(f"Unable to set locale: {e}")
    print("")

_localeres = files("pisi.data").joinpath("locale")
if _localeres.is_dir():
    _localedir: str | None = str(_localeres)
else:
    _localedir = None  # Use the system one.

lang_code = [locale.getlocale()[0] or "en_US"]
lang = gettext.translation(
    "pisi", localedir=_localedir, fallback=True, languages=lang_code
)

# You usually want to import this function with the "_" alias.
translate = lang.gettext
ngettext = lang.ngettext

__version__ = "4.3.3"

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
    signal_handler = signalhandler.SignalHandler()

    signal_handler.disable_signal(signal.SIGINT)
    if ctx.log:
        ctx.loghandler.flush()
        ctx.log.removeHandler(ctx.loghandler)

    filesdb = pisi.db.filesdb.FilesDB()
    if filesdb.is_initialized():
        filesdb.close()

    if ctx.build_leftover and os.path.exists(ctx.build_leftover):
        os.unlink(ctx.build_leftover)

    ctx.ui.close()
    signal_handler.enable_signal(signal.SIGINT)


# Hack for pisi to work with non-patched Python. pisi needs
# lots of work for not doing this.
importlib.reload(sys)

atexit.register(_cleanup)

ctx.config = pisi.config.Config()
init_logging()
