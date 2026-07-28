# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

import pisi.api
import pisi.context as ctx
from pisi import translate as _
from pisi.cli import command


class ListPending(command.Command, metaclass=command.autocommand):
    __doc__ = _(
        """List pending packages

Lists packages waiting to be configured.
"""
    )

    def __init__(self, args):
        super().__init__(args)

    name = ("list-pending", "lp")

    def run(self):
        self.init(database=True, write=False)

        A = pisi.api.list_pending()
        if len(A):
            for p in pisi.api.generate_pending_order(A):
                print(p)
        else:
            ctx.ui.info(_("There are no packages waiting to be configured"))
