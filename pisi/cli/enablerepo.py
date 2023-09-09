# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

from pisi import translate as _

import pisi.cli.command as command
import pisi.api


class EnableRepo(command.Command, metaclass=command.autocommand):
    __doc__ = _(
        """Enable repository

Usage: enable-repo [<repo1> <repo2> ... <repon>]

<repoi>: repository name

Disabled repositories are not taken into account in operations
"""
    )

    def __init__(self, args):
        super(EnableRepo, self).__init__(args)
        self.repodb = pisi.db.repodb.RepoDB()

    name = ("enable-repo", "er")

    def run(self):
        self.init(database=True)

        if not self.args:
            self.help()
            return

        for repo in self.args:
            if self.repodb.has_repo(repo):
                pisi.api.set_repo_activity(repo, True)
