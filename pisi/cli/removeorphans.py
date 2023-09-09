# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

import optparse

from pisi import translate as _

import pisi.cli.command as command
import pisi.context as ctx
import pisi.api
import pisi.db


class RemoveOrphans(command.PackageOp, metaclass=command.autocommand):
    __doc__ = _(
        """Remove orphaned packages

Usage: remove-orphans

Remove any unused orphan packages from the system that were automatically
installed as a dependency of another package.

Only packages that have no reverse dependencies outside of the automatically
installed list will be removed.
"""
    )

    def __init__(self, args):
        super(RemoveOrphans, self).__init__(args)

    name = ("remove-orphans", "rmo")

    def options(self):
        group = optparse.OptionGroup(self.parser, _("remove-orphans options"))
        super(RemoveOrphans, self).options(group)
        group.add_option(
            "--purge",
            action="store_true",
            default=False,
            help=_("Removes everything including changed config files of the package"),
        )
        self.parser.add_option_group(group)

    def run(self):
        self.init()

        pisi.api.remove_orphans()
