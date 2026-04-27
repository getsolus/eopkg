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
from pisi import ngettext, util
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
    def __init__(self):
        # Set cacheable=False because we use LMDB now
        lazydb.LazyDB.__init__(self, cacheable=False)

    @property
    def lmdb_mappings(self):
        return [self.filesdb]

    def init(self, force_rebuild=False):
        self.filesdb = self.lmdb_store.get_mapping("files")
        meta = self.lmdb_store.get_mapping("meta")

        version = meta.get("filesdb_version")

        if force_rebuild or version != FILESDB_FORMAT_VERSION or len(self.filesdb) == 0:
            if self.lmdb_store.readonly and not self.lmdb_store.use_memory:
                # We need to rebuild but can't write to LMDB. Fallback to memory.
                from pisi.db.lmdbstore import MemoryMapping

                self.filesdb = MemoryMapping()

            self.__rebuild()

            if not self.lmdb_store.readonly:
                meta["filesdb_version"] = FILESDB_FORMAT_VERSION

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
            # Check if we have files cached in InstallDB first
            # Actually, InstallDB might not have all files cached yet.
            # Fallback to XML search as before if FilesDB doesn't have it.
            try:
                files_xml = open(
                    os.path.join(installdb.package_path(pkg), ctx.const.files_xml)
                ).read()
                paths = re.compile(
                    "<Path>(.*?%s.*?)</Path>" % re.escape(term), re.I
                ).findall(files_xml)
                if paths:
                    found.append((pkg, paths))
            except IOError:
                continue
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
        new_files = {}
        for f in files.list:
            new_files[hashlib.md5(f.path.encode()).hexdigest()] = pkg
        self.filesdb.update_bulk(new_files)

    def remove_files(self, files):
        for f in files:
            key = hashlib.md5(f.path.encode()).hexdigest()
            if key in self.filesdb:
                del self.filesdb[key]

    def destroy(self):
        # We don't destroy the LMDB file itself, just clear the mapping
        self.filesdb.clear()
        meta = self.lmdb_store.get_mapping("meta")
        if not self.lmdb_store.readonly:
            if "filesdb_version" in meta:
                del meta["filesdb_version"]

    def close(self):
        # LMDBStore handles closing
        pass

    def __rebuild(self):
        ctx.ui.info(_("Rebuilding the FilesDB..."))
        self.filesdb.clear()
        # we need a list of installed files per package
        installdb = pisi.db.installdb.InstallDB()
        pkgs = 0
        verbose = ctx.config.options.verbose
        ctx.ui.info(_("Adding packages to FilesDB:"))

        all_files = {}
        batch_size = 100

        installed_pkgs = installdb.list_installed()
        for pkg in installed_pkgs:
            files = installdb.get_files(pkg)
            if verbose:
                ctx.ui.info(_("Adding '%s' ...") % pkg, noln=True)

            for f in files.list:
                all_files[hashlib.md5(f.path.encode()).hexdigest()] = pkg

            if verbose:
                ctx.ui.info(_("Okay."))

            pkgs += 1
            if pkgs % batch_size == 0:
                self.filesdb.update_bulk(all_files)
                all_files = {}
                if not verbose:
                    ctx.ui.info(".", noln=True)
                else:
                    ctx.ui.info("-------------")
                    ctx.ui.info(_("Added so far: %s") % pkgs)
                    ctx.ui.info("-------------")
        if all_files:
            self.filesdb.update_bulk(all_files)
        ctx.ui.info(
            ngettext(
                "\n%(num)d package added in total.",
                "\n%(num)d packages added in total.",
                pkgs,
            )
            % {"num": pkgs}
        )
        ctx.ui.info(_("Done rebuilding FilesDB."))
