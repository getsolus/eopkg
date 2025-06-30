# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

import optparse

from pisi import translate as _

import pisi.api
import pisi.cli.command as command
import pisi.context as ctx
import pisi.util as util
import pisi.db


usage = _(
    """Verify installation

Usage: check [<package1> <package2> ... <packagen>]
       check -c <component>

<packagei>: package name

A cryptographic checksum is stored for each installed
file. Check command uses the checksums to verify a package.
Just give the names of packages.

If no packages are given, checks all installed packages.
"""
)


class Check(command.Command, metaclass=command.autocommand):
    __doc__ = usage

    def __init__(self, args):
        super(Check, self).__init__(args)
        self.installdb = pisi.db.installdb.InstallDB()
        self.componentdb = pisi.db.componentdb.ComponentDB()

    name = ("check", None)

    def options(self):
        group = optparse.OptionGroup(self.parser, _("check options"))

        group.add_option(
            "-c",
            "--component",
            action="store",
            default=None,
            help=_("Check installed packages under " "given component"),
        )

        group.add_option(
            "--config",
            action="store_true",
            default=False,
            help=_("Checks only changed config files of " "the packages"),
        )

        self.parser.add_option_group(group)

    def run(self):
        self.init(database=True, write=False)

        component = ctx.get_option("component")
        if component:
            installed = pisi.api.list_installed()
            component_pkgs = self.componentdb.get_union_packages(component, walk=True)
            pkgs = list(set(installed) & set(component_pkgs))
        elif self.args:
            pkgs = self.args
        else:
            ctx.ui.info(_("Checking all installed packages") + "\n")
            pkgs = pisi.api.list_installed()

        necessary_permissions = True

        # True if we should also check the configuration files
        check_config = ctx.get_option("config")

        # Line prefix
        prefix = _("Checking integrity of %s")

        # Determine maximum length of messages for proper formatting
        maxpkglen = max([len(_p) for _p in pkgs])

        for pkg in pkgs:
            if self.installdb.has_package(pkg):
                check_results = pisi.api.check(pkg, check_config)
                ctx.ui.info(
                    "%s    %s" % ((prefix % pkg), " " * (maxpkglen - len(pkg))),
                    noln=True,
                )

                if (
                    check_results["missing"]
                    or check_results["corrupted"]
                    or check_results["config"]
                ):
                    ctx.ui.info(util.colorize(_("Broken"), "brightred"))
                elif check_results["denied"]:
                    # We can't deduce a result when some files
                    # can't be accessed
                    necessary_permissions = False
                    ctx.ui.info(util.colorize(_("Unknown"), "yellow"))
                else:
                    ctx.ui.info(util.colorize(_("OK"), "green"))
                    continue

                # Dump per file stuff
                for fpath in check_results["missing"]:
                    ctx.ui.info(
                        util.colorize(_("Missing file: /%s") % fpath, "brightred")
                    )

                for fpath in check_results["denied"]:
                    ctx.ui.info(
                        util.colorize(_("Access denied: /%s") % fpath, "yellow")
                    )

                for fpath in check_results["corrupted"]:
                    ctx.ui.info(
                        util.colorize(_("Corrupted file: /%s") % fpath, "brightyellow")
                    )

                for fpath in check_results["config"]:
                    ctx.ui.info(
                        util.colorize(
                            _("Modified configuration file: /%s") % fpath,
                            "brightyellow",
                        )
                    )

            else:
                # Package is not installed
                ctx.ui.info(_("Package %s not installed") % pkg)

        if not necessary_permissions:
            ctx.ui.info("")
            ctx.ui.warning(
                _(
                    "Could not check the integrity of packages which contain files your user "
                    "did not have permission to read.\n"
                    "Running the check under a privileged user may help to fix this problem."
                )
            )
