# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

import optparse

from pisi import translate as _

import pisi.cli.command as command
import pisi.context as ctx
import pisi.api
import pisi.db


class Remove(command.PackageOp, metaclass=command.autocommand):
    __doc__ = _(
        """Remove eopkg packages

Usage: remove <package1> <package2> ... <packagen>

Remove package(s) from your system. Just give the package names to remove.

You can also specify components instead of package names, which will be
expanded to package names.
"""
    )

    def __init__(self, args):
        super(Remove, self).__init__(args)
        self.componentdb = pisi.db.componentdb.ComponentDB()

    name = ("remove", "rm")

    def options(self):
        group = optparse.OptionGroup(self.parser, _("remove options"))
        super(Remove, self).options(group)
        group.add_option(
            "--purge",
            action="store_true",
            default=False,
            help=_("Removes everything including changed config files of the package"),
        )
        group.add_option(
            "-c",
            "--component",
            action="append",
            default=None,
            help=_("Remove component's and recursive components' packages"),
        )
        self.parser.add_option_group(group)

    def run(self):
        self.init()

        components = ctx.get_option("component")
        if not components and not self.args:
            self.help()
            return

        packages = []
        if components:
            for name in components:
                if self.componentdb.has_component(name):
                    packages.extend(
                        self.componentdb.get_union_packages(name, walk=True)
                    )
        packages.extend(self.args)

        pisi.api.remove(packages)
