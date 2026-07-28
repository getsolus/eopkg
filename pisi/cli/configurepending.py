# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

import optparse

import pisi.api
from pisi import translate as _
from pisi.cli import command


class ConfigurePending(command.PackageOp, metaclass=command.autocommand):
    __doc__ = _(
        """Configure pending packages

If COMAR configuration of some packages were not
done at installation time, they are added to a list
of packages waiting to be configured. This command
configures those packages.
"""
    )

    def __init__(self, args):
        super().__init__(args)

    name = ("configure-pending", "cp")

    def setup_options(self):
        group = optparse.OptionGroup(self.parser, _("configure-pending options"))
        super().options(group)
        self.parser.add_option_group(group)

    def run(self):
        self.init()
        pisi.api.configure_pending(self.args)
