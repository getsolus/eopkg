# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

from pisi import translate as _

import pisi.cli
import pisi.cli.command as command
import pisi.context as ctx

# Import all the commands that are alphabetically after help
# We need to force-import all of these or help is truncated due to how pisi.command.autocommand is written.
# TODO: Modernize the entire CLI and remove this nonsense.
from pisi.cli.history import History
from pisi.cli.index import Index
from pisi.cli.info import Info
from pisi.cli.install import Install
from pisi.cli.listavailable import ListAvailable
from pisi.cli.listcomponents import ListComponents
from pisi.cli.listinstalled import ListInstalled
from pisi.cli.listnewest import ListNewest
from pisi.cli.listpending import ListPending
from pisi.cli.listrepo import ListRepo
from pisi.cli.listupgrades import ListUpgrades
from pisi.cli.rebuilddb import RebuildDb
from pisi.cli.remove import Remove
from pisi.cli.removeorphans import RemoveOrphans
from pisi.cli.removerepo import RemoveRepo
from pisi.cli.repopriority import RepoPriority
from pisi.cli.search import Search
from pisi.cli.searchfile import SearchFile
from pisi.cli.updaterepo import UpdateRepo
from pisi.cli.upgrade import Upgrade


class Help(command.Command, metaclass=command.autocommand):
    __doc__ = _(
        """Prints help for given commands

Usage: help [ <command1> <command2> ... <commandn> ]

If run without parameters, it prints the general help."""
    )

    def __init__(self, args=None):
        super(Help, self).__init__(args)

    name = ("help", "?")

    def run(self):
        if not self.args:
            self.parser.set_usage(usage_text)
            pisi.cli.printu(self.parser.format_help())
            return

        self.init(database=False, write=False)

        for arg in self.args:
            obj = command.Command.get_command(arg, True)
            obj.help()
            ctx.ui.info("")


usage_text1 = _(
    """%prog [options] <command> [arguments]

where <command> is one of:

"""
)

usage_text2 = _(
    """
Use \"%prog help <command>\" for help on a specific command.
"""
)

usage_text = usage_text1 + command.Command.commands_string() + usage_text2
