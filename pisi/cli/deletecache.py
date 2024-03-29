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

from pisi import translate as _

import pisi
import pisi.api
import pisi.cli.command as command

class DeleteCache(command.Command):
    __doc__ = _("""Delete cache files

Usage: delete-cache

Sources, packages and temporary files are stored
under /var directory. Since these accumulate they can
consume a lot of disk space.""")

    __metaclass__ = command.autocommand

    def __init__(self, args=None):
        super(DeleteCache, self).__init__(args)

    name = ("delete-cache", "dc")

    def run(self):
        self.init(database=False, write=True)
        pisi.api.delete_cache()
