# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, 2017-Present Solus Developers
# SPDX-License-Identifier: GPL-2.0-or-later

import optparse

from pisi import translate as _

import pisi.cli.command as command
import pisi.context as ctx
import pisi.db


class ListComponents(command.Command, metaclass=command.autocommand):
    __doc__ = _(
        """List available components

Usage: list-components

Gives a brief list of eopkg components published in the
repositories.
"""
    )

    def __init__(self, args):
        super(ListComponents, self).__init__(args)
        self.componentdb = pisi.db.componentdb.ComponentDB()

    name = ("list-components", "lc")

    def options(self):
        group = optparse.OptionGroup(self.parser, _("list-components options"))
        group.add_option(
            "-l",
            "--long",
            action="store_true",
            default=False,
            help=_("Show in long format"),
        )
        group.add_option(
            "-r",
            "--repository",
            action="store",
            type="string",
            default=None,
            help=_("Name of the source or package repository"),
        )
        self.parser.add_option_group(group)

    def run(self):
        self.init(database=True, write=False)

        l = self.componentdb.list_components(ctx.get_option("repository"))
        l.sort()
        for p in l:
            component = self.componentdb.get_component(p)
            if self.options.long:
                ctx.ui.info(str(component))
            else:
                lenp = len(p)
                # if p in installed_list:
                #    p = util.colorize(p, 'cyan')
                p = p + " " * max(0, 15 - lenp)
                ctx.ui.info("%s - %s " % (component.name, str(component.summary)))
