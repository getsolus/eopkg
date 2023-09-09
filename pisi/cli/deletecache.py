# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

from pisi import translate as _

import pisi
import pisi.api
import pisi.cli.command as command


class DeleteCache(command.Command, metaclass=command.autocommand):
    __doc__ = _(
        """Delete cache files

Usage: delete-cache

Sources, packages and temporary files are stored
under /var directory. Since these accumulate they can
consume a lot of disk space."""
    )

    def __init__(self, args=None):
        super(DeleteCache, self).__init__(args)

    name = ("delete-cache", "dc")

    def run(self):
        self.init(database=False, write=True)
        pisi.api.delete_cache()
