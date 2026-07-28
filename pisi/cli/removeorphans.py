# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

import optparse

import pisi.api
from pisi import translate as _
from pisi.cli import command


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
        super().__init__(args)

    name = ("remove-orphans", "rmo")

    def setup_options(self):
        group = optparse.OptionGroup(self.parser, _("remove-orphans options"))
        super().options(group)
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
