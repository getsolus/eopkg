# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

import optparse

from pisi import translate as _

import pisi.cli.command as command
import pisi.context as ctx


usage = _(
    """Index eopkg files in a given directory

Usage: index <directory> ...

This command searches for all eopkg files in a directory, collects eopkg
tags from them and accumulates the information in an output XML file,
named by default 'eopkg-index.xml'. In particular, it indexes both
source and binary packages.

If you give multiple directories, the command still works, but puts
everything in a single index file.
"""
)


class Index(command.Command, metaclass=command.autocommand):
    __doc__ = usage

    def __init__(self, args):
        super(Index, self).__init__(args)

    name = ("index", "ix")

    def options(self):
        group = optparse.OptionGroup(self.parser, _("index options"))

        group.add_option(
            "-a",
            "--absolute-urls",
            action="store_true",
            default=False,
            help=_("Store absolute links for indexed files."),
        )

        group.add_option(
            "-o",
            "--output",
            action="store",
            default="eopkg-index.xml",
            help=_("Index output file"),
        )

        group.add_option(
            "--compression-types",
            action="store",
            default="xz",
            help=_("Comma-separated compression types " "for index file. Valid options are \"xz\" and \"bz2\". Defaults to \"xz\"."),
        )

        group.add_option(
            "--skip-signing",
            action="store_true",
            default=False,
            help=_("Do not sign index."),
        )

        self.parser.add_option_group(group)

    def run(self):
        self.init(database=True, write=False)

        from pisi.api import index
        from pisi.file import File

        ctypes = {"bz2": File.COMPRESSION_TYPE_BZ2, "xz": File.COMPRESSION_TYPE_XZ}
        compression = 0
        for type_str in ctx.get_option("compression_types").split(","):
            compression |= ctypes.get(type_str, 0)

        index(
            self.args or ["."],
            ctx.get_option("output"),
            skip_signing=ctx.get_option("skip_signing"),
            compression=compression,
        )
