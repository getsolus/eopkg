# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

import dbm
import hashlib
import os
import re
import shelve
import sys

import pisi
from pisi import context as ctx
from pisi import ngettext
from pisi import translate as _
from pisi.db import lazydb

# FIXME:
# We could traverse through files.xml files of the packages to find the path and
# the package - a linear search - as some well known package managers do. But the current
# file conflict mechanism of pisi prevents this and needs a fast has_file function.
# So currently filesdb is the only db and we cant still get rid of rebuild-db :/

# dbm.sqlite3 (default in py3.13+) is significantly slower for many small writes.
# We literally just use the shelve as a fast file lookup
try:
    import dbm.gnu as gdbm
except ImportError:
    gdbm = None

if gdbm:
    FILESDB_FORMAT_VERSION = 4
elif sys.version_info >= (3, 13):
    FILESDB_FORMAT_VERSION = 5
else:
    FILESDB_FORMAT_VERSION = 4


class FilesDB(lazydb.LazyDB):
    def init(self, force_rebuild=False):
        self.filesdb = {}
        self.__check_filesdb(force_rebuild)

    def has_file(self, path):
        return hashlib.md5(path.encode()).hexdigest() in self.filesdb

    def get_file(self, path):
        return self.filesdb[hashlib.md5(path.encode()).hexdigest()], path

    def search_file(self, term):
        if self.has_file(term):
            pkg, path = self.get_file(term)
            return [(pkg, [path])]

        installdb = pisi.db.installdb.InstallDB()
        found = []
        for pkg in installdb.list_installed():
            files_xml = open(
                os.path.join(installdb.package_path(pkg), ctx.const.files_xml)
            ).read()
            paths = re.compile(
                "<Path>(.*?%s.*?)</Path>" % re.escape(term), re.I
            ).findall(files_xml)
            if paths:
                found.append((pkg, paths))
        return found

    def get_pkgconfig_provider(self, pkgconfigName):
        """get_pkgconfig_provider will try known paths to find the provider
        of a given pkgconfig name"""
        pcPaths = [
            "usr/lib64/pkgconfig",
            "usr/share/pkgconfig",
        ]
        for p in pcPaths:
            fp = p + "/" + str(pkgconfigName) + ".pc"
            if self.has_file(fp):
                return self.get_file(fp)
        return None

    def get_pkgconfig32_provider(self, pkgconfigName):
        """get_pkgconfig32_provider will try known paths to find the provider
        of a given pkgconfig32 name"""
        fp = "usr/lib32/pkgconfig/" + pkgconfigName + ".pc"
        if self.has_file(fp):
            return self.get_file(fp)
        return None

    def add_files(self, pkg, files):
        self.__check_filesdb()

        for f in files.list:
            self.filesdb[hashlib.md5(f.path.encode()).hexdigest()] = pkg

    def remove_files(self, files):
        for f in files:
            if hashlib.md5(f.path.encode()).hexdigest() in self.filesdb:
                del self.filesdb[hashlib.md5(f.path.encode()).hexdigest()]

    def destroy(self):
        files_db = os.path.join(ctx.config.info_dir(), ctx.const.files_db)
        if os.path.exists(files_db):
            os.unlink(files_db)

    def close(self):
        if isinstance(self.filesdb, shelve.Shelf):
            self.filesdb.sync()
            self.filesdb.close()

    def __open_shelve(self, path, flag):
        """Helper to open shelve with preferred backend."""
        if gdbm:
            try:
                # Explicitly use gdbm if available for write performance
                return shelve.Shelf(gdbm.open(path, flag))
            except dbm.error:
                # If it's not a gdbm file (e.g. it's sqlite), fall back to default
                pass
        return shelve.open(path, flag)

    def __check_filesdb(self, force_rebuild=False):
        """Sets valid self.files_db reference and automatically rebuilds the underlying db if necessary."""

        # already initialized
        if isinstance(self.filesdb, shelve.Shelf):
            return

        files_db = os.path.join(ctx.config.info_dir(), ctx.const.files_db)
        needs_rebuild = force_rebuild

        if not force_rebuild:
            if os.path.exists(files_db):
                try:
                    # Try opening read-write first
                    try:
                        self.filesdb = self.__open_shelve(files_db, "w")
                    except dbm.error:
                        # Fallback to read-only
                        self.filesdb = self.__open_shelve(files_db, "r")
                        ctx.ui.debug(
                            # . FilesDB is a proper name and should not be translated
                            _(f"Opened FilesDB {files_db} read-only.")
                        )

                    # Check version
                    if self.filesdb.get("version") != FILESDB_FORMAT_VERSION:
                        ctx.ui.warning(
                            # . FilesDB is a proper name and should not be translated
                            _("FilesDB version mismatch or missing version.")
                        )
                        needs_rebuild = True

                except Exception as e:
                    ctx.ui.debug(
                        # . FilesDB is a proper name and should not be translated
                        _(f"Failed to open FilesDB {files_db}: {e}")
                    )
                    needs_rebuild = True
            else:
                # File missing
                needs_rebuild = True

        if needs_rebuild:
            # Check if we have write access to the directory to perform a rebuild
            if os.access(os.path.dirname(files_db) or ".", os.W_OK):
                self.__rebuild()
            else:
                self.close()
                self.filesdb = {}
                ctx.ui.warning(
                    # . FilesDB is a proper name and should not be translated
                    _("FilesDB is invalid and cannot be rebuilt (no write access).")
                )
                ctx.ui.warning(_("Falling back to slow and inaccurate XML search..."))

    def __rebuild(self):
        # This assumes that __check_filesdb() has determined a rebuild is needed
        files_db = os.path.join(ctx.config.info_dir(), ctx.const.files_db)
        ctx.ui.info(
            # . FilesDB is a proper name and should not be translated
            _("Rebuilding the FilesDB...")
        )

        self.close()
        self.destroy()
        self.filesdb = {}

        try:
            # "n" means we're opening a new shelve, overwriting the old one
            self.filesdb = self.__open_shelve(files_db, "n")
        except Exception as err:
            ctx.ui.error(
                # . FilesDB is a proper name and should not be translated
                _("FilesDB rebuild failed: %s") % err
            )
            raise err

        self.filesdb["version"] = FILESDB_FORMAT_VERSION
        # we need a list of installed files per package
        installdb = pisi.db.installdb.InstallDB()
        pkgs = 0
        verbose = ctx.config.options.verbose
        ctx.ui.info(
            # . FilesDB is a proper name and should not be translated
            _(f"Adding packages to FilesDB {files_db}:")
        )
        for pkg in installdb.list_installed():
            files = installdb.get_files(pkg)
            if verbose:
                ctx.ui.info(_("Adding '%s' ...") % pkg, noln=True)
            self.add_files(pkg, files)
            if verbose:
                ctx.ui.info(_("Okay."))
            pkgs += 1
            # Print out useful markers every so often
            if pkgs % 50 == 0:
                if verbose:
                    ctx.ui.info("-------------")
                    ctx.ui.info(_("Added so far: %s") % pkgs)
                    ctx.ui.info("-------------")
                else:
                    ctx.ui.info(".", noln=True)
        ctx.ui.info(
            ngettext(
                "\n%(num)d package added in total.",
                "\n%(num)d packages added in total.",
                pkgs,
            )
            % {"num": pkgs}
        )
        # ensure that the changes get pushed out to disk
        self.filesdb.sync()
        # This acts as a check that the version has been correctly added and synced to disk
        ctx.ui.info(
            # . FilesDB is a proper name and should not be translated
            _(f"Finished rebuilding FilesDB (version: {self.filesdb['version']})")
        )
