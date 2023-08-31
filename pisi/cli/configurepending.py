# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, 2017-Present Solus Developers
# SPDX-License-Identifier: GPL-2.0-or-later

import optparse

from pisi import translate as _

import pisi.api
import pisi.cli.command as command


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
        super(ConfigurePending, self).__init__(args)

    name = ("configure-pending", "cp")

    def options(self):
        group = optparse.OptionGroup(self.parser, _("configure-pending options"))
        super(ConfigurePending, self).options(group)
        self.parser.add_option_group(group)

    def run(self):
        self.init()
        pisi.api.configure_pending(self.args)
