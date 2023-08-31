# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, 2017-Present Solus Developers
# SPDX-License-Identifier: GPL-2.0-or-later

from pisi import translate as _

import pisi.cli.command as command


class Clean(command.Command, metaclass=command.autocommand):
    __doc__ = _(
        """Clean stale locks

Usage: clean

eopkg uses filesystem locks for managing database access.
This command deletes unused locks from the database directory."""
    )

    def __init__(self, args=None):
        super(Clean, self).__init__(args)

    name = ("clean", None)

    def run(self):
        self.init()
