# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

import os
import sys
import optparse

from pisi import translate as _

import pisi
import pisi.api
import pisi.db
import pisi.context as ctx
import pisi.cli.command as command

# Operation names for translation
opttrans = {
    "upgrade": _("upgrade"),
    "remove": _("remove"),
    "emerge": _("emerge"),
    "install": _("install"),
    "snapshot": _("snapshot"),
    "takeback": _("takeback"),
    "repoupdate": _("repository update"),
}


class History(command.PackageOp, metaclass=command.autocommand):
    __doc__ = _(
        """History of pisi operations

Usage: history

Lists previous operations."""
    )

    def __init__(self, args=None):
        super(History, self).__init__(args)
        self.historydb = pisi.db.historydb.HistoryDB()

    name = ("history", "hs")

    def options(self):
        group = optparse.OptionGroup(self.parser, _("history options"))
        self.add_options(group)
        self.parser.add_option_group(group)

    def add_options(self, group):
        group.add_option(
            "-l",
            "--last",
            action="store",
            type="int",
            default=0,
            help=_("Output only the last n operations"),
        )
        group.add_option(
            "-s",
            "--snapshot",
            action="store_true",
            default=False,
            help=_("Take snapshot of the current system"),
        )
        group.add_option(
            "-t",
            "--takeback",
            action="store",
            type="int",
            default=-1,
            help=_("Takeback to the state after the given operation finished"),
        )

    def take_snapshot(self):
        pisi.api.snapshot()

    def takeback(self, operation):
        pisi.api.takeback(operation)

    def print_history(self):
        for operation in self.historydb.get_last(ctx.get_option("last")):
            print(_("Operation #%d: %s") % (operation.no, opttrans[operation.type]))
            print(_("Date: %s %s") % (operation.date, operation.time))
            print()

            if operation.type == "snapshot":
                print(
                    _("    * There are %d packages in this snapshot.")
                    % len(operation.packages)
                )
            elif operation.type == "repoupdate":
                for repo in operation.repos:
                    print("    *", repo)
            else:
                for pkg in operation.packages:
                    print("    *", pkg)
            print()

    def redirect_output(self, func):
        if os.isatty(sys.stdout.fileno()):

            class LessException(Exception):
                pass

            class LessPipe:
                def __init__(self):
                    import subprocess

                    self.less = subprocess.Popen(
                        ["less", "-K", "-"], stdin=subprocess.PIPE
                    )

                def __del__(self):
                    if self.less.poll() is None:
                        self.less.stdin.close()
                    self.less.wait()

                def flush(self):
                    self.less.stdin.flush()

                def write(self, s):
                    try:
                        self.less.stdin.write(s.encode())
                    except IOError:
                        raise LessException

            stdout, stderr = sys.stdout, sys.stderr
            sys.stdout = sys.stderr = LessPipe()
            try:
                func()
            except LessException:
                pass
            finally:
                sys.stdout, sys.stderr = stdout, stderr

        else:
            func()

    def run(self):
        self.init(database=False, write=False)
        if ctx.get_option("snapshot"):
            self.take_snapshot()
            return
        elif ctx.get_option("takeback"):
            opno = ctx.get_option("takeback")
            if opno != -1:
                self.takeback(opno)
                return

        ctx.disable_keyboard_interrupts(should_hold=False)
        self.redirect_output(self.print_history)
        ctx.enable_keyboard_interrupts()
