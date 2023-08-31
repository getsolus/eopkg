# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, 2017-Present Solus Developers
# SPDX-License-Identifier: GPL-2.0-or-later

import os
import optparse

from pisi import translate as _

import pisi.cli.command as command
import pisi.context as ctx
import pisi.api


class Fetch(command.Command, metaclass=command.autocommand):
    __doc__ = _(
        """Fetch a package

Usage: fetch [<package1> <package2> ... <packagen>]

<packagei>: package name

Downloads the given pisi packages to working directory
"""
    )

    def __init__(self, args):
        super(Fetch, self).__init__(args)

    name = ("fetch", "fc")

    def options(self):
        group = optparse.OptionGroup(self.parser, _("fetch options"))
        self.add_options(group)
        self.parser.add_option_group(group)

    def add_options(self, group):
        group.add_option(
            "-o",
            "--output-dir",
            action="store",
            default=os.path.curdir,
            help=_("Output directory for the fetched packages"),
        )

    def run(self):
        self.init(database=False, write=False)

        if not self.args:
            self.help()
            return

        pisi.api.fetch(self.args, ctx.config.options.output_dir)
