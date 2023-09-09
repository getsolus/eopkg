# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

import optparse

from pisi import translate as _

import pisi.cli.command as command
import pisi.context as ctx
import pisi.db


class Blame(command.Command, metaclass=command.autocommand):
    __doc__ = _(
        """Information about the package owner and release

Usage: blame <package> ... <package>

"""
    )

    def __init__(self, args=None):
        super(Blame, self).__init__(args)
        self.installdb = pisi.db.installdb.InstallDB()

    name = ("blame", "bl")

    def options(self):
        group = optparse.OptionGroup(self.parser, _("blame options"))
        group.add_option(
            "-r",
            "--release",
            action="store",
            type="int",
            help=_("Blame for the given release"),
        )
        group.add_option(
            "-a",
            "--all",
            action="store_true",
            default=False,
            help=_("Blame for all of the releases"),
        )
        self.parser.add_option_group(group)

    def run(self):
        self.init(database=False, write=False)

        if not self.args:
            self.help()
            return

        for package in self.args:
            if self.installdb.has_package(package):
                pkg = self.installdb.get_package(package)
                release = ctx.get_option("release")
                if not release and not ctx.get_option("all"):
                    self.print_package_info(pkg)
                elif ctx.get_option("all"):
                    for hno, update in enumerate(pkg.history):
                        self.print_package_info(pkg, hno)
                else:
                    for hno, update in enumerate(pkg.history):
                        if int(update.release) == release:
                            self.print_package_info(pkg, hno)
                            return

    def print_package_info(self, package, hno=0):
        s = _("Name: %s, version: %s, release: %s\n") % (
            package.name,
            package.history[hno].version,
            package.history[hno].release,
        )
        s += _("Package Maintainer: %s <%s>\n") % (
            str(package.source.packager.name),
            package.source.packager.email,
        )
        s += _("Release Updater: %s <%s>\n") % (
            package.history[hno].name,
            package.history[hno].email,
        )
        s += _("Update Date: %s\n") % package.history[hno].date
        s += "\n%s\n" % package.history[hno].comment
        ctx.ui.info(s)
