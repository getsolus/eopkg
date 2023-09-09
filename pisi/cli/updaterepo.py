# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

import optparse

from pisi import translate as _

import pisi.cli.command as command
import pisi.context as ctx
import pisi.api


class UpdateRepo(command.Command, metaclass=command.autocommand):
    __doc__ = _(
        """Update repository databases

Usage: update-repo [<repo1> <repo2> ... <repon>]

<repoi>: repository name

Synchronizes the eopkg databases with the current repository.
If no repository is given, all repositories are updated.
"""
    )

    def __init__(self, args):
        super(UpdateRepo, self).__init__(args)

    name = ("update-repo", "ur")

    def options(self):
        group = optparse.OptionGroup(self.parser, _("update-repo options"))

        group.add_option(
            "-f",
            "--force",
            action="store_true",
            default=False,
            help=_("Update database in any case"),
        )

        self.parser.add_option_group(group)

    def run(self):
        self.init(database=True)

        if self.args:
            repos = self.args
        else:
            repos = pisi.api.list_repos()

        pisi.api.update_repos(repos, ctx.get_option("force"))
