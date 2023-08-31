# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, 2017-Present Solus Developers
# SPDX-License-Identifier: GPL-2.0-or-later

# python standard library

import os
from pisi import translate as _

# pisi modules
import pisi
import pisi.util as util
import pisi.context as ctx
import pisi.archive
import pisi.uri
import pisi.fetcher
import pisi.mirrors


class Error(pisi.Error):
    pass


class SourceArchives:
    """This is a wrapper for supporting multiple SourceArchive objects."""

    def __init__(self, spec):
        self.sourceArchives = [SourceArchive(a) for a in spec.source.archive]

    def fetch(self, interactive=True):
        for archive in self.sourceArchives:
            archive.fetch(interactive)

    def unpack(self, target_dir, clean_dir=True):
        self.sourceArchives[0].unpack(target_dir, clean_dir)
        for archive in self.sourceArchives[1:]:
            archive.unpack(target_dir, clean_dir=False)


class SourceArchive:
    """source archive. this is a class responsible for fetching
    and unpacking a source archive"""

    def __init__(self, archive):
        self.url = pisi.uri.URI(archive.uri)
        self.archiveFile = os.path.join(ctx.config.archives_dir(), self.url.filename())
        self.archive = archive

    def fetch(self, interactive=True):
        if not self.is_cached(interactive):
            if interactive:
                self.progress = ctx.ui.Progress
            else:
                self.progress = None

            try:
                ctx.ui.info(_("Fetching source from: %s") % self.url.uri)
                if self.url.get_uri().startswith("mirrors://"):
                    self.fetch_from_mirror()
                else:
                    pisi.fetcher.fetch_url(
                        self.url, ctx.config.archives_dir(), self.progress
                    )
            except pisi.fetcher.FetchError:
                raise

            ctx.ui.info(
                _("Source archive is stored: %s/%s")
                % (ctx.config.archives_dir(), self.url.filename())
            )

    def fetch_from_mirror(self):
        uri = self.url.get_uri()
        sep = uri[len("mirrors://") :].split("/")
        name = sep.pop(0)
        archive = "/".join(sep)

        mirrors = pisi.mirrors.Mirrors().get_mirrors(name)
        if not mirrors:
            raise Error(_("%s mirrors are not defined.") % name)

        for mirror in mirrors:
            try:
                url = os.path.join(mirror, archive)
                ctx.ui.warning(_("Fetching source from mirror: %s") % url)
                pisi.fetcher.fetch_url(url, ctx.config.archives_dir(), self.progress)
                return
            except pisi.fetcher.FetchError:
                pass

        raise pisi.fetcher.FetchError(
            _("Could not fetch source from %s mirrors.") % name
        )

    def is_cached(self, interactive=True):
        if not os.access(self.archiveFile, os.R_OK):
            return False

        # check hash
        if util.check_file_hash(self.archiveFile, self.archive.sha1sum):
            if interactive:
                ctx.ui.info(_("%s [cached]") % self.archive.name)
            return True

        return False

    def unpack(self, target_dir, clean_dir=True):
        # check archive file's integrity
        if not util.check_file_hash(self.archiveFile, self.archive.sha1sum):
            raise Error(_("unpack: check_file_hash failed"))

        try:
            archive = pisi.archive.Archive(self.archiveFile, self.archive.type)
        except pisi.archive.UnknownArchiveType:
            raise Error(
                _("Unknown archive type '%s' is given for '%s'.")
                % (self.archive.type, self.url.filename())
            )
        except pisi.archive.ArchiveHandlerNotInstalled:
            raise Error(
                _("Pisi needs %s to unpack this archive but it is not installed.")
                % self.archive.type
            )

        target_dir = os.path.join(target_dir, self.archive.target or "")
        archive.unpack(target_dir, clean_dir)
