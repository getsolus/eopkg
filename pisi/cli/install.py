# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

import optparse

from pisi import translate as _

import pisi.cli.command as command
import pisi.context as ctx
import pisi.api
import pisi.db


class Install(command.PackageOp, metaclass=command.autocommand):
    __doc__ = _(
        """Install eopkg packages

Usage: install <package1> <package2> ... <packagen>

You may use filenames, URI's or package names for packages. If you have
specified a package name, it should exist in a specified repository.

You can also specify components instead of package names, which will be
expanded to package names.
"""
    )

    def __init__(self, args):
        super(Install, self).__init__(args)
        self.componentdb = pisi.db.componentdb.ComponentDB()

    name = "install", "it"

    def options(self):
        group = optparse.OptionGroup(self.parser, _("install options"))

        super(Install, self).options(group)

        group.add_option(
            "--reinstall",
            action="store_true",
            default=False,
            help=_("Reinstall already installed packages"),
        )
        group.add_option(
            "--ignore-check",
            action="store_true",
            default=False,
            help=_("Skip distribution release and architecture check"),
        )
        group.add_option(
            "--ignore-file-conflicts",
            action="store_true",
            default=False,
            help=_("Ignore file conflicts"),
        )
        group.add_option(
            "--ignore-package-conflicts",
            action="store_true",
            default=False,
            help=_("Ignore package conflicts"),
        )
        group.add_option(
            "--ignore-revdeps-of-deps-check",
            action="store_true",
            default=False,
            help=_(
                "Don't check for updates in reverse dependencies of runtime dependencies when updates are available"
            ),
        )
        group.add_option(
            "-c",
            "--component",
            action="append",
            default=None,
            help=_("Install component's and recursive components' packages"),
        )
        group.add_option(
            "-r",
            "--repository",
            action="store",
            type="string",
            default=None,
            help=_("Name of the component's repository"),
        )
        group.add_option(
            "-f",
            "--fetch-only",
            action="store_true",
            default=False,
            help=_("Fetch upgrades but do not install."),
        )
        group.add_option(
            "-x",
            "--exclude",
            action="append",
            default=None,
            help=_(
                "When installing packages, ignore packages and components whose basenames match pattern."
            ),
        )
        group.add_option(
            "--exclude-from",
            action="store",
            default=None,
            help=_(
                "When installing packages, ignore packages "
                "and components whose basenames match "
                "any pattern contained in file."
            ),
        )
        self.parser.add_option_group(group)

    def run(self):
        if self.options.fetch_only:
            self.init(database=True, write=False)
        else:
            self.init()

        components = ctx.get_option("component")
        if not components and not self.args:
            self.help()
            return

        packages = []
        if components:
            for name in components:
                if self.componentdb.has_component(name):
                    repository = ctx.get_option("repository")
                    if repository:
                        packages.extend(
                            self.componentdb.get_packages(
                                name, walk=True, repo=repository
                            )
                        )
                    else:
                        packages.extend(
                            self.componentdb.get_union_packages(name, walk=True)
                        )
                else:
                    ctx.ui.info(_("There is no component named %s") % name)

        packages.extend(self.args)

        if ctx.get_option("exclude_from"):
            packages = pisi.blacklist.exclude_from(
                packages, ctx.get_option("exclude_from")
            )

        if ctx.get_option("exclude"):
            packages = pisi.blacklist.exclude(packages, ctx.get_option("exclude"))

        # See operations.install.plan_install_pkgs
        if len(pisi.api.list_upgradable()) != 0 and not ctx.get_option(
            "ignore_revdeps_of_deps_check"
        ):
            ctx.ui.warning(
                _(
                    "Updates available, checking reverse dependencies "
                    "of runtime dependencies for safety."
                )
            )

        reinstall = bool(packages) and packages[0].endswith(ctx.const.package_suffix)
        pisi.api.install(packages, ctx.get_option("reinstall") or reinstall)
