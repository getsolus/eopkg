# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

import dbm
import hashlib
import os
import re
import shelve

import pisi
from pisi import context as ctx
from pisi import util
from pisi.db import lazydb

# FIXME:
# We could traverse through files.xml files of the packages to find the path and
# the package - a linear search - as some well known package managers do. But the current
# file conflict mechanism of pisi prevents this and needs a fast has_file function.
# So currently filesdb is the only db and we cant still get rid of rebuild-db :/

# This MUST match the version used in eopkg.py2 as long as that is in use.
FILESDB_PICKLE_PROTOCOL_VERSION = 2

# We suspect that there will be an advantage in versioning this separately
FILESDB_FORMAT_VERSION = 4

class FilesDB(lazydb.LazyDB):

    def init(self, is_being_rebuilt=False):
        self.filesdb = {}
        needs_rebuild = False
        # We need to break the cycle for when pisi.api.rebuild_db() is called,
        # which will itself call the present init function.
        if not is_being_rebuilt:
            needs_rebuild = self.__check_filesdb()
        # needs_rebuild is never set to True if we can't write to the files_db file
        if needs_rebuild:
            ctx.ui.info("FilesDB needs a rebuild.")
            self.close()
            self.destroy()
            # this creates a new FilesDB object (which calls add_version() below)
            pisi.api.rebuild_db(files=True)
            ctx.ui.info("Done rebuilding FilesDB (version: %s)" % (FILESDB_FORMAT_VERSION))
            self.filesdb = {}
            self.__check_filesdb()

    def add_version(self):
        # will only _ever_ get called from pisi.api.rebuild_db()
        # at a point where the underlying db is already guaranteed to be initialised.
        self.filesdb["version"] = FILESDB_FORMAT_VERSION
        self.filesdb.sync()

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
        if isinstance(self.filesdb, shelve.DbfilenameShelf):
            self.filesdb.close()

    def __check_filesdb(self):
        """Sets valid self.files_db reference and returns whether the underlying db needs to be rebuilt."""
        # whether or not we need to rebuild the FilesDB
        needs_rebuild = False

        if isinstance(self.filesdb, shelve.DbfilenameShelf):
            # the db has already been correctly initialised
            return needs_rebuild

        # We don't know the db type by default
        db_type = "?"

        files_db = os.path.join(ctx.config.info_dir(), ctx.const.files_db)

        if os.path.exists(files_db):
            # check the kind of db
            db_type = dbm.whichdb(files_db)
            if db_type != "dbm.gnu":
                if not os.access(files_db, os.W_OK):
                    ctx.ui.debug("Cannot write to type %s database cache %s, ignoring." % (db_type, files_db))
                    return needs_rebuild
                else:
                    ctx.ui.debug("Incompatible type %s database cache %s found, needs_rebuild = True" % (db_type, files_db))
                    needs_rebuild = True

        if not os.path.exists(files_db):
            flag = "n"
            ctx.ui.debug("No database cache %s found, needs_rebuild = True" % (files_db))
            needs_rebuild = True
        elif os.access(files_db, os.W_OK):
            flag = "w"
        else:
            flag = "r"
            ctx.ui.debug("Type %s database cache %s is read-only." % (db_type, files_db))

        # At this point, we _should_ be able to _open_ the file.
        # The only remaining question is whether the pickle protocol version is correct
        try:
            # NOTE: This will use gdbm format db files by default
            self.filesdb = shelve.open(files_db, flag, protocol=FILESDB_PICKLE_PROTOCOL_VERSION)
        except:
             ctx.ui.debug("shelve.open(files_db=%s, flag=%s, protocol=%s) failed, needs_rebuild = True"
                           % (files_db, flag, FILESDB_PICKLE_PROTOCOL_VERSION))
             needs_rebuild = True
             return needs_rebuild

        # Check if self.filesdb has a version key
        has_version = True
        version = 0
        try:
            version = self.filesdb["version"]
        except:
            has_version = False

        # At this point, either:
        #  has_version is True and version != 0,
        #   XOR
        #  has_version is False and version == 0

        if flag != "r":
            if not has_version or version != FILESDB_FORMAT_VERSION:
                ctx.ui.debug("Incompatible type %s database cache %s found (version: (%s, %s), expected (%s, %s)), needs_rebuild = True" % (db_type, files_db, has_version, version, True, FILESDB_FORMAT_VERSION))
                needs_rebuild = True

        # False unless the logic above caused it to be toggled to True
        return needs_rebuild

