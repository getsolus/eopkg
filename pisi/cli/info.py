# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

import optparse

from pisi import translate as _

import pisi.cli.command as command
import pisi.context as ctx
import pisi.util as util
import pisi.api
import pisi.db


class Info(command.Command, metaclass=command.autocommand):
    __doc__ = _(
        """Display package information

Usage: info <package1> <package2> ... <packagen>

<packagei> is either a package name or a .pisi file,
"""
    )

    def __init__(self, args):
        super(Info, self).__init__(args)
        self.installdb = pisi.db.installdb.InstallDB()
        self.componentdb = pisi.db.componentdb.ComponentDB()
        self.packagedb = pisi.db.packagedb.PackageDB()

    name = ("info", None)

    def options(self):
        group = optparse.OptionGroup(self.parser, _("info options"))
        self.add_options(group)
        self.parser.add_option_group(group)

    def add_options(self, group):
        group.add_option(
            "-f",
            "--files",
            action="store_true",
            default=False,
            help=_("Show a list of package files."),
        )
        group.add_option(
            "-c",
            "--component",
            action="append",
            default=None,
            help=_("Info about the given component"),
        )
        group.add_option(
            "-F",
            "--files-path",
            action="store_true",
            default=False,
            help=_("Show only paths."),
        )
        group.add_option(
            "-s",
            "--short",
            action="store_true",
            default=False,
            help=_("Do not show details"),
        )
        group.add_option(
            "--xml", action="store_true", default=False, help=_("Output in xml format")
        )

    def run(self):
        self.init(database=True, write=False)

        if not pisi.api.has_active_repositories():
            ctx.ui.error(_("No active repositories found"))
            return

        components = ctx.get_option("component")
        if not components and not self.args:
            self.help()
            return

        index = pisi.index.Index()
        index.distribution = None

        # info of components
        if components:
            for name in components:
                if self.componentdb.has_component(name):
                    component = self.componentdb.get_union_component(name)
                    if self.options.xml:
                        index.add_component(component)
                    else:
                        if not self.options.short:
                            ctx.ui.info(str(component))
                        else:
                            ctx.ui.info("%s - %s" % (component.name, component.summary))

        # info of packages
        for arg in self.args:
            if self.options.xml:
                index.packages.append(pisi.api.info(arg)[0].package)
            else:
                self.info_package(arg)

        if self.options.xml:
            import sys

            errs = []
            index.newDocument()
            index.encode(index.rootNode(), errs)
            index.writexmlfile(sys.stdout)
            sys.stdout.write("\n")

    def info_package(self, arg):
        if arg.endswith(ctx.const.package_suffix):
            self.pisifile_info(arg)
            return

        self.installdb_info(arg)
        self.packagedb_info(arg)

    def print_files(self, files):
        files.list.sort(key=lambda x: x.path)
        for fileinfo in files.list:
            if self.options.files:
                print(fileinfo)
            else:
                print("/" + fileinfo.path)

    def print_metadata(self, metadata, packagedb=None):
        if ctx.get_option("short"):
            pkg = metadata.package
            ctx.ui.formatted_output(" - ".join((pkg.name, str(pkg.summary))))
        else:
            ctx.ui.formatted_output(str(metadata.package))
            if packagedb:
                revdeps = [
                    name for name, dep in packagedb.get_rev_deps(metadata.package.name)
                ]
                ctx.ui.formatted_output(
                    " ".join((_("Reverse Dependencies:"), util.strlist(revdeps)))
                )
                print()

    def print_specdata(self, spec):
        src = spec.source
        if ctx.get_option("short"):
            ctx.ui.formatted_output(" - ".join((src.name, str(src.summary))))
        else:
            ctx.ui.formatted_output(str(spec))

    def pisifile_info(self, package):
        metadata, files = pisi.api.info_file(package)
        ctx.ui.formatted_output(_("Package file: %s") % package)

        self.print_metadata(metadata)
        if self.options.files or self.options.files_path:
            self.print_files(files)

    def installdb_info(self, package):
        if self.installdb.has_package(package):
            metadata, files, repo = pisi.api.info_name(package, True)

            if self.options.files or self.options.files_path:
                self.print_files(files)
                return

            if self.options.short:
                ctx.ui.formatted_output(_("[inst] "), noln=True, column=" ")
            else:
                ctx.ui.info(_("Installed package:"))

            self.print_metadata(metadata, self.installdb)
        else:
            ctx.ui.info(_("%s package is not installed") % package)

    def packagedb_info(self, package):
        if self.packagedb.has_package(package):
            metadata, files, repo = pisi.api.info_name(package, False)
            if self.options.short:
                ctx.ui.formatted_output(_("[binary] "), noln=True, column=" ")
            else:
                ctx.ui.info(_("Package found in %s repository:") % repo)
            self.print_metadata(metadata, self.packagedb)
        else:
            ctx.ui.info(_("%s package is not found in binary repositories") % package)
