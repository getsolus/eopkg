# -*- coding: utf-8 -*-
#
# Copyright (C) 2005 - 2007, TUBITAK/UEKAE
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free
# Software Foundation; either version 2 of the License, or (at your option)
# any later version.
#
# Please read the COPYING file.
#

import hashlib
import os
import re
import shelve

import pisi
import pisi.context as ctx
import pisi.db.lazydb as lazydb

from pisi import translate as _

# FIXME:
# We could traverse through files.xml files of the packages to find the path and
# the package - a linear search - as some well known package managers do. But the current
# file conflict mechanism of pisi prevents this and needs a fast has_file function.
# So currently filesdb is the only db and we cant still get rid of rebuild-db :/

# The highest pickle protocol version supported in py2
FILESDB_PICKLE_PROTOCOL_VERSION = 2

# We suspect that there will be an advantage in versioning this separately
FILESDB_FORMAT_VERSION = 3

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
        return self.filesdb.has_key(hashlib.md5(path).digest())

    def get_file(self, path):
        return self.filesdb[hashlib.md5(path).digest()], path

    def search_file(self, term):
        if self.has_file(term):
            pkg, path = self.get_file(term)
            return [(pkg,[path])]

        installdb = pisi.db.installdb.InstallDB()
        found = []
        for pkg in installdb.list_installed():
            files_xml = open(os.path.join(installdb.package_path(pkg), ctx.const.files_xml)).read()
            paths = re.compile('<Path>(.*?%s.*?)</Path>' % re.escape(term), re.I).findall(files_xml)
            if paths:
                found.append((pkg, paths))
        return found

    def get_pkgconfig_provider(self, pkgconfigName):
        """ get_pkgconfig_provider will try known paths to find the provider
            of a given pkgconfig name """
        pcPaths = [
            "usr/lib64/pkgconfig",
            "usr/share/pkgconfig",
        ]
        for p in pcPaths:
            fp = p + "/" + pkgconfigName + ".pc"
            if self.has_file(fp):
                return self.get_file(fp)
        return None

    def get_pkgconfig32_provider(self, pkgconfigName):
        """ get_pkgconfig32_provider will try known paths to find the provider
            of a given pkgconfig32 name """
        fp = "usr/lib32/pkgconfig/" + pkgconfigName + ".pc"
        if self.has_file(fp):
            return self.get_file(fp)
        return None

    def add_files(self, pkg, files):

        self.__check_filesdb()

        for f in files.list:
            self.filesdb[hashlib.md5(f.path).digest()] = pkg

    def remove_files(self, files):
        for f in files:
            if self.filesdb.has_key(hashlib.md5(f.path).digest()):
                del self.filesdb[hashlib.md5(f.path).digest()]

    def destroy(self):
        files_db = os.path.join(ctx.config.info_dir(), ctx.const.files_db)
        if os.path.exists(files_db):
            os.unlink(files_db)

    def close(self):
        if isinstance(self.filesdb, DbfilenameShelf):
            self.filesdb.close()

    def __check_filesdb(self):
        """Sets valid self.files_db reference and returns whether the underlying db needs to be rebuilt."""
        # whether or not we need to rebuild the FilesDB
        needs_rebuild = False

        if isinstance(self.filesdb, DbfilenameShelf):
            # the db has already been correctly initialised
            return needs_rebuild

        # We don't know the db type by default
        db_type = "?"

        files_db = os.path.join(ctx.config.info_dir(), ctx.const.files_db)

        if os.path.exists(files_db):
            # check the kind of db
            import whichdb
            db_type = whichdb.whichdb(files_db)
            if db_type != "gdbm":
                if not os.access(files_db, os.W_OK):
                    ctx.ui.debug("Cannot write to type %s database cache %s, ignoring." % (db_type, files_db))
                    return needs_rebuild
                else:
                    ctx.ui.debug("Incompatible type %s database cache %s found, needs_rebuild = True" % (db_type, files_db))
                    needs_rebuild = True
    
        if not os.path.exists(files_db):
            flag = "n"
            ctx.ui.debug("No type %s database cache %s found, needs_rebuild = True" % (db_type, files_db))
            needs_rebuild = True
        elif os.access(files_db, os.W_OK):
            flag = "w"
        else:
            flag = "r"
            ctx.ui.debug("Type %s database cache %s is read-only." % (db_type, files_db))

        # At this point, we _should_ be able to _open_ the file.
        # The only remaining question is whether the pickle protocol version is correct
        try:
             self.filesdb = myopen(files_db, flag, protocol=FILESDB_PICKLE_PROTOCOL_VERSION)
        except:
             ctx.ui.debug("myopen(files_db=%s, flag=%s, protocol=%s) failed, needs_rebuild = True"
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

        return needs_rebuild


# Ensure we use gdbm rather than bsddb which is normally selected from anydb
# https://github.com/python/cpython/blob/v2.7.18/Lib/shelve.py#L218
class DbfilenameShelf(shelve.Shelf):
    def __init__(self, filename, flag='c', protocol=None, writeback=False):
        import gdbm
        shelve.Shelf.__init__(self, gdbm.open(filename, flag), protocol, writeback)

# Call our own DbfilenameShelf
# https://github.com/python/cpython/blob/v2.7.18/Lib/shelve.py#L230
def myopen(filename, flag='c', protocol=None, writeback=False):
    return DbfilenameShelf(filename, flag, protocol, writeback)
