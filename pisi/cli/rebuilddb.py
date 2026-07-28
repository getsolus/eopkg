# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

import optparse

import pisi.api
import pisi.context as ctx
from pisi import translate as _
from pisi.cli import command


class RebuildDb(command.Command, metaclass=command.autocommand):
    __doc__ = _(
        """Rebuild Databases

Usage: rebuilddb [ <package1> <package2> ... <packagen> ]

Rebuilds the eopkg databases

If package specs are given, they should be the names of package
dirs under /var/lib/eopkg
"""
    )

    def __init__(self, args):
        super().__init__(args)

    name = ("rebuild-db", "rdb")

    def setup_options(self):
        group = optparse.OptionGroup(self.parser, _("rebuild-db options"))

        group.add_option(
            "-f",
            "--files",
            action="store_true",
            default=False,
            help=_("Rebuild files database"),
        )

        self.parser.add_option_group(group)

    def run(self):
        self.init(database=True)
        if ctx.ui.confirm(_("Rebuild eopkg databases?")):
            pisi.api.rebuild_db(ctx.get_option("files"))
