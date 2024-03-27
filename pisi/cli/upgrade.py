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
import os
import subprocess

from pisi import translate as _

import pisi.cli.command as command
import pisi.context as ctx
import pisi.util as util
import pisi.api
import pisi.db

class Upgrade(command.PackageOp):
    __doc__ = _("""Upgrade eopkg packages

Usage: Upgrade [<package1> <package2> ... <packagen>]

<packagei>: package name

Upgrades the entire system if no package names are given

You may use only package names to specify packages because
the package upgrade operation is defined only with respect
to repositories. If you have specified a package name, it
should exist in the package repositories. If you just want to
reinstall a package from a eopkg file, use the install command.

You can also specify components instead of package names, which will be
expanded to package names.
""")
    __metaclass__ = command.autocommand

    def __init__(self, args):
        super(Upgrade, self).__init__(args)

    name = ("upgrade", "up")

    def options(self):
        group = optparse.OptionGroup(self.parser, _("upgrade options"))

        super(Upgrade, self).options(group)
        group.add_option("--security-only", action="store_true",
                     default=False, help=_("Security related package upgrades only"))
        group.add_option("-b", "--bypass-update-repo", action="store_true",
                     default=False, help=_("Do not update repositories"))
        group.add_option("--ignore-file-conflicts", action="store_true",
                     default=False, help=_("Ignore file conflicts"))
        group.add_option("--ignore-package-conflicts", action="store_true",
                     default=False, help=_("Ignore package conflicts"))
        group.add_option("-c", "--component", action="append",
                               default=None, help=_("Upgrade component's and recursive components' packages"))
        group.add_option("-r", "--repository", action="store",
                               type="string", default=None, help=_('Name of the to be upgraded packages\' repository'))
        group.add_option("-f", "--fetch-only", action="store_true",
                     default=False, help=_("Fetch upgrades but do not install."))
        group.add_option("--offline", action="store_true", default=False, help=_("Perform upgrades offline"))
        group.add_option("-x", "--exclude", action="append",
                     default=None, help=_("When upgrading system, ignore packages and components whose basenames match pattern."))
        group.add_option("--exclude-from", action="store",
                     default=None,
                     help=_("When upgrading system, ignore packages "
                            "and components whose basenames match "
                            "any pattern contained in file."))

        self.parser.add_option_group(group)

    def run(self):

        if self.options.fetch_only or self.options.offline:
            self.init(database=True, write=False)
        else:
            self.init()

        if pisi.api.is_offline_upgrade_prepared() is True:
            ctx.ui.warning(_('An offline update is already prepared'))
            if ctx.ui.confirm(_('Do you wish to clear the previously prepared offline update?')):
                if pisi.api.clear_prepared_offline_upgrade() is False:
                    return
            else:
                return

        if not ctx.get_option('bypass_update_repo'):
            ctx.ui.info(_('Updating repositories'))
            repos = pisi.api.list_repos()
            pisi.api.update_repos(repos)
        else:
            ctx.ui.info(_('Will not update repositories'))

        repository = ctx.get_option('repository')
        components = ctx.get_option('component')
        packages = []
        if components:
            componentdb = pisi.db.componentdb.ComponentDB()
            for name in components:
                if componentdb.has_component(name):
                    if repository:
                        packages.extend(componentdb.get_packages(name, walk=True, repo=repository))
                    else:
                        packages.extend(componentdb.get_union_packages(name, walk=True))
        packages.extend(self.args)

        pisi.api.upgrade(packages, repository)

        if self.options.offline:
            offline_file = os.path.join(ctx.config.history_dir(), 'prepared-offline-update')
            if os.path.exists(offline_file):
                if ctx.ui.confirm(_('The updates will be applied on next reboot. Do you wish to reboot now?')):
                    subprocess.Popen(["systemctl", "soft-reboot"])
