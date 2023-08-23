# -*- coding:utf-8 -*-
#
# Copyright (C) 2005-2010, TUBITAK/UEKAE
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free
# Software Foundation; either version 2 of the License, or (at your option)
# any later version.
#
# Please read the COPYING file.
#

import optparse

from pisi import translate as _

import pisi.cli.command as command
import pisi.context as ctx
import pisi.db
from pisi.operations.remove import list_orphans
import pisi.util as util


class ListInstalled(command.Command, metaclass=command.autocommand):
    __doc__ = _(
        """Print the list of all installed packages

Usage: list-installed
"""
    )

    def __init__(self, args):
        super(ListInstalled, self).__init__(args)
        self.installdb = pisi.db.installdb.InstallDB()
        self.componentdb = pisi.db.componentdb.ComponentDB()

    name = ("list-installed", "li")

    def options(self):
        group = optparse.OptionGroup(self.parser, _("list-installed options"))
        group.add_option(
            "-a",
            "--automatic",
            action="store_true",
            default=False,
            help=_("Show automatically installed packages and the parent dependency"),
        )
        group.add_option(
            "-b",
            "--with-build-host",
            action="store",
            default=None,
            help=_("Only list the installed packages built " "by the given host"),
        )
        group.add_option(
            "-l",
            "--long",
            action="store_true",
            default=False,
            help=_("Show in long format"),
        )
        group.add_option(
            "-c",
            "--component",
            action="store",
            default=None,
            help=_("List installed packages under given component"),
        )
        group.add_option(
            "-i",
            "--install-info",
            action="store_true",
            default=False,
            help=_("Show detailed install info"),
        )

        self.parser.add_option_group(group)

    def run(self):
        self.init(database=True, write=False)

        if self.options.automatic:
            return self.run_automatic_only()

        build_host = ctx.get_option("with_build_host")
        if build_host is None:
            installed = self.installdb.list_installed()
        else:
            installed = self.installdb.list_installed_with_build_host(build_host)

        component = ctx.get_option("component")
        if component:
            # FIXME: pisi api is insufficient to do this
            component_pkgs = self.componentdb.get_union_packages(component, walk=True)
            installed = list(set(installed) & set(component_pkgs))

        installed.sort()

        # Resize the first column according to the longest package name
        if installed:
            maxlen = max([len(_p) for _p in installed])

        if self.options.install_info:
            ctx.ui.info(
                _(
                    "Package Name          |St|        Version|  Rel.|  Distro|             Date"
                )
            )
            print(
                "==========================================================================="
            )
        for pkg in installed:
            package = self.installdb.get_package(pkg)
            inst_info = self.installdb.get_info(pkg)
            if self.options.long:
                ctx.ui.info(str(package))
                ctx.ui.info(str(inst_info))
            elif self.options.install_info:
                ctx.ui.info("%-20s  |%s" % (package.name, inst_info.one_liner()))
            else:
                package.name = package.name + " " * (maxlen - len(package.name))
                ctx.ui.info("%s - %s" % (package.name, str(package.summary)))

    def run_automatic_only(self):
        """
        Only list the automatically installed packages
        """
        orphans = list_orphans()
        keys = list(orphans.keys())
        keys.sort()
        if keys and len(keys) > 0:
            maxlen = max([len(x) for x in keys])

        for orphan in keys:
            owner = orphans[orphan]
            orphan_print = orphan
            if owner:
                orphan_print = util.colorize(orphan_print, "green")
            else:
                orphan_print = util.colorize(orphan_print, "brightwhite")

            if not owner:
                owner = _("Orphaned package")
            orphan_print += " " * max(0, maxlen - len(orphan))
            ctx.ui.info("%s - %s " % (orphan_print, str(owner)))
