# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, 2017-Present Solus Developers
# SPDX-License-Identifier: GPL-2.0-or-later

from pisi import translate as _

import pisi.cli.command as command
import pisi.api


class RemoveRepo(command.Command, metaclass=command.autocommand):
    __doc__ = _(
        """Remove repositories

Usage: remove-repo <repo1> <repo2> ... <repon>

Remove all repository information from the system.
"""
    )

    def __init__(self, args):
        super(RemoveRepo, self).__init__(args)

    name = ("remove-repo", "rr")

    def run(self):
        if len(self.args) >= 1:
            self.init()
            for repo in self.args:
                pisi.api.remove_repo(repo)
        else:
            self.help()
            return
