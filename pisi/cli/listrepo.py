# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

from pisi import translate as _

import pisi.cli.command as command
import pisi.context as ctx
import pisi.util as util
import pisi.db


class ListRepo(command.Command, metaclass=command.autocommand):
    __doc__ = _(
        """List repositories

Usage: list-repo

Lists currently tracked repositories.
"""
    )

    def __init__(self, args):
        super(ListRepo, self).__init__(args)
        self.repodb = pisi.db.repodb.RepoDB()

    name = ("list-repo", "lr")

    def run(self):
        self.init(database=True, write=False)
        for repo in self.repodb.list_repos(only_active=False):
            active = _("active") if self.repodb.repo_active(repo) else _("inactive")
            if active == _("active"):
                ctx.ui.info(util.colorize(_("%s [%s]") % (repo, active), "green"))
            else:
                ctx.ui.info(util.colorize(_("%s [%s]") % (repo, active), "red"))
            print("  ", self.repodb.get_repo_url(repo))
