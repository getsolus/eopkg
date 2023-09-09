# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

import optparse

from pisi import translate as _

import pisi
import pisi.context as ctx
import pisi.cli.command as command


class SearchFile(command.Command, metaclass=command.autocommand):
    __doc__ = _(
        """Search for a file

Usage: search-file <path1> <path2> ... <pathn>

Finds the installed package which contains the specified file.
"""
    )

    def __init__(self, args):
        super(SearchFile, self).__init__(args)

    name = ("search-file", "sf")

    def options(self):
        group = optparse.OptionGroup(self.parser, _("search-file options"))
        group.add_option(
            "-l",
            "--long",
            action="store_true",
            default=False,
            help=_("Show in long format"),
        )
        group.add_option(
            "-q",
            "--quiet",
            action="store_true",
            default=False,
            help=_("Show only package name"),
        )
        self.parser.add_option_group(group)

    def search_file(self, path):
        found = pisi.api.search_file(path)
        for pkg, files in found:
            for pkg_file in files:
                ctx.ui.info(_("Package %s has file /%s") % (pkg, pkg_file))

        if not found:
            ctx.ui.error(_("Path '%s' does not belong to an installed package") % path)

    def run(self):
        self.init(database=True, write=False)

        if not self.args:
            self.help()
            return

        # search among existing files
        for path in self.args:
            if not ctx.config.options.quiet:
                ctx.ui.info(_("Searching for %s") % path)
            self.search_file(path)
