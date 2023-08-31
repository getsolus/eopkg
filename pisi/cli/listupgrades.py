# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, 2017-Present Solus Developers
# SPDX-License-Identifier: GPL-2.0-or-later

import optparse

from pisi import translate as _

import pisi.cli.command as command
import pisi.blacklist
import pisi.context as ctx
import pisi.api
import pisi.db


class ListUpgrades(command.Command, metaclass=command.autocommand):
    __doc__ = _(
        """List packages to be upgraded

Usage: list-upgrades

Lists the packages that will be upgraded.
"""
    )

    def __init__(self, args):
        super(ListUpgrades, self).__init__(args)
        self.componentdb = pisi.db.componentdb.ComponentDB()
        self.installdb = pisi.db.installdb.InstallDB()

    name = ("list-upgrades", "lu")

    def options(self):
        group = optparse.OptionGroup(self.parser, _("list-upgrades options"))
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
            help=_("List upgradable packages under given component"),
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
        upgradable_pkgs = pisi.api.list_upgradable()

        component = ctx.get_option("component")
        if component:
            # FIXME: eopkg api is insufficient to do this
            component_pkgs = self.componentdb.get_union_packages(component, walk=True)
            upgradable_pkgs = list(set(upgradable_pkgs) & set(component_pkgs))

        upgradable_pkgs = pisi.blacklist.exclude_from(
            upgradable_pkgs, ctx.const.blacklist
        )

        if not upgradable_pkgs:
            ctx.ui.info(_("No packages to upgrade."))
            return

        upgradable_pkgs.sort()

        # Resize the first column according to the longest package name
        maxlen = max([len(_p) for _p in upgradable_pkgs])

        if self.options.install_info:
            ctx.ui.info(
                _(
                    "Package Name          |St|        Version|  Rel.|  Distro|             Date"
                )
            )
            print(
                "==========================================================================="
            )
        for pkg in upgradable_pkgs:
            package = self.installdb.get_package(pkg)
            inst_info = self.installdb.get_info(pkg)
            if self.options.long:
                ctx.ui.info(package)
                print(inst_info)
            elif self.options.install_info:
                ctx.ui.info("%-20s |%s " % (package.name, inst_info.one_liner()))
            else:
                package.name = package.name + " " * (maxlen - len(package.name))
                ctx.ui.info("%s - %s" % (package.name, str(package.summary)))
