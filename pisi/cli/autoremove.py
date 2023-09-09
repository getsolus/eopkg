# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

import optparse

from pisi import translate as _

import pisi.cli.command as command
import pisi.context as ctx
import pisi.api
import pisi.db


class AutoRemove(command.PackageOp, metaclass=command.autocommand):
    __doc__ = _(
        """Remove eopkg packages

Usage: autoremove <package1> <package2> ... <packagen>

Remove package(s) from your system. Just give the package names to remove.

You can also specify components instead of package names, which will be
expanded to package names.

Any additional packages that were automatically installed as a result of
installing the packages being removed, will also be removed if it is
safe to do so.
"""
    )

    def __init__(self, args):
        super(AutoRemove, self).__init__(args)
        self.componentdb = pisi.db.componentdb.ComponentDB()

    name = ("autoremove", "rmf")

    def options(self):
        group = optparse.OptionGroup(self.parser, _("autoremove options"))
        super(AutoRemove, self).options(group)
        group.add_option(
            "--purge",
            action="store_true",
            default=False,
            help=_("Removes everything including changed config files of the package"),
        )
        self.parser.add_option_group(group)

    def run(self):
        self.init()

        if not self.args:
            self.help()
            return

        packages = []
        packages.extend(self.args)

        pisi.api.autoremove(packages)
