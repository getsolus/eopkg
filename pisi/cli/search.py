# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

import optparse
import re

from pisi import translate as _

import pisi.cli.command as command
import pisi.context as ctx
import pisi.db


class Search(command.Command, metaclass=command.autocommand):
    __doc__ = _(
        """Search packages

Usage: search <term1> <term2> ... <termn>

Finds a package containing specified search terms
in summary, description, and package name fields.
Default search is done in package database. Use
options to search in install database or source
database.
"""
    )

    def __init__(self, args):
        super(Search, self).__init__(args)

    name = ("search", "sr")

    def options(self):
        group = optparse.OptionGroup(self.parser, _("search options"))
        group.add_option(
            "-l",
            "--language",
            action="store",
            type="string",
            default=None,
            help=_("Summary and description language"),
        )
        group.add_option(
            "-r",
            "--repository",
            action="store",
            type="string",
            default=None,
            help=_("Name of the source or package repository"),
        )
        group.add_option(
            "-i",
            "--installdb",
            action="store_true",
            default=False,
            help=_("Search in installdb"),
        )
        group.add_option(
            "--name",
            action="store_true",
            default=False,
            help=_("Search in the package name"),
        )
        group.add_option(
            "--summary",
            action="store_true",
            default=False,
            help=_("Search in the package summary"),
        )
        group.add_option(
            "--description",
            action="store_true",
            default=False,
            help=_("Search in the package description"),
        )
        self.parser.add_option_group(group)

    def run(self):
        self.init(database=True, write=False)

        if not self.args:
            self.help()
            return

        if not pisi.api.has_active_repositories():
            ctx.ui.error(_("No active repositories found"))
            return

        replace = re.compile("(%s)" % "|".join(self.args), re.I)
        lang = ctx.get_option("language")
        repo = ctx.get_option("repository")
        name = ctx.get_option("name")
        summary = ctx.get_option("summary")
        desc = ctx.get_option("description")
        fields = None
        if name or summary or desc:
            fields = {"name": name, "summary": summary, "desc": desc}

        if ctx.get_option("installdb"):
            db = pisi.db.installdb.InstallDB()
            pkgs = db.search_package(self.args, lang, fields)
            get_info = db.get_package
            get_name_sum = lambda pkg: (pkg.name, pkg.summary)
        else:
            db = pisi.db.packagedb.PackageDB()
            pkgs = db.search_package(self.args, lang, repo, fields)
            get_info = db.get_package
            get_name_sum = lambda pkg: (pkg.name, pkg.summary)

        if pkgs:
            maxlen = max([len(_pkg) for _pkg in pkgs])

        for pkg in pkgs:
            pkg_info = get_info(pkg)

            name, summary = get_name_sum(pkg_info)
            lenp = len(name)

            name = replace.sub(pisi.util.colorize(r"\1", "brightred"), name)
            if lang and lang in summary:
                summary = replace.sub(
                    pisi.util.colorize(r"\1", "brightred"), str(summary[lang])
                )
            else:
                summary = replace.sub(
                    pisi.util.colorize(r"\1", "brightred"), str(summary)
                )

            name += " " * max(0, maxlen - lenp)

            ctx.ui.info("%s - %s" % (name, summary))
