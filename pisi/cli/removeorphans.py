# -*- coding:utf-8 -*-
#
# Copyright (C) 2005 - 2007, TUBITAK/UEKAE
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free
# Software Foundation; either version 2 of the License, or (at your option)
# any later version.
#
# Please read the COPYING file.
#

import optparse

from pisi import translate as _

import pisi.cli.command as command
import pisi.context as ctx
import pisi.api
import pisi.db

class RemoveOrphans(command.PackageOp, metaclass=command.autocommand):
    __doc__ = _("""Remove orphaned packages

Usage: remove-orphans

Remove any unused orphan packages from the system that were automatically
installed as a dependency of another package.

Only packages that have no reverse dependencies outside of the automatically
installed list will be removed.
""")

    def __init__(self, args):
        super(RemoveOrphans, self).__init__(args)

    name = ("remove-orphans", "rmo")

    def options(self):
        group = optparse.OptionGroup(self.parser, _("remove-orphans options"))
        super(RemoveOrphans, self).options(group)
        group.add_option("--purge", action="store_true",
                     default=False, help=_("Removes everything including changed config files of the package"))
        self.parser.add_option_group(group)

    def run(self):
        self.init()

        pisi.api.remove_orphans()
