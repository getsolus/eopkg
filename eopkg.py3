#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

import sys
import errno
import traceback
import signal

import pisi
import pisi.context as ctx
import pisi.cli.pisicli as pisicli

from pisi import translate as _


def sig_handler(sig, frame):
    if sig == signal.SIGTERM:
        exit()


def exit():
    sys.exit(1)


def handle_exception(exception, value, tb):
    signal.signal(signal.SIGINT, signal.SIG_IGN)  # disable further interrupts
    ui = pisi.cli.CLI()  # make a temporary UI
    show_traceback = False

    if exception == KeyboardInterrupt:
        ui.error(_("Keyboard Interrupt: Exiting..."))
        exit()
    elif isinstance(value, pisi.Error):
        ui.error(_("Program terminated."))
        show_traceback = ctx.get_option("debug")
    elif isinstance(value, pisi.Exception):
        show_traceback = True
        ui.error(
            _(
                "Unhandled internal exception.\n"
                "Please file a bug report to <https://github.com/getsolus/package-management/>."
            )
        )
    elif isinstance(value, IOError) and value.errno == errno.EPIPE:
        # Ignore broken pipe errors
        sys.exit(0)
    else:
        # For any other exception (possibly Python exceptions) show
        # the traceback!
        show_traceback = ctx.get_option("debug")
        ui.error(_("System error. Program terminated."))

    if show_traceback:
        ui.error("%s: %s" % (exception, str(value)))
    else:
        msg = str(value)
        if msg:
            ui.error(msg)

    ui.info(_("Please use 'eopkg help' for general help."))

    if show_traceback:
        ui.info(_("\nTraceback:"))
        traceback.print_tb(tb)
    elif not isinstance(value, pisi.Error):
        ui.info(_("Use --debug to see a traceback."))

    exit()


def main():
    sys.excepthook = handle_exception

    signal.signal(signal.SIGTERM, sig_handler)

    cli = pisicli.PisiCLI()
    cli.run_command()


if __name__ == "__main__":
    main()
