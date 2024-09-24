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

# pickle protocol version 0 is a human-readable ASCII encoded format,
# which is fine for DB use as it can then be introspected by querying the db
# directly.
# pickle protocol version 0 is the default in python2.
FILESDB_PICKLE_PROTOCOL_VERSION = 0

class FilesDB(lazydb.LazyDB):

    def init(self):
        self.filesdb = {}
        self.__check_filesdb()

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
        if isinstance(self.filesdb, DbfilenameShelf):
            return

        files_db = os.path.join(ctx.config.info_dir(), ctx.const.files_db)

        if os.path.exists(files_db):
            import whichdb
            db_type = whichdb.whichdb(files_db)
            if db_type != "gdbm":
                if not os.access(files_db, os.W_OK):
                    ctx.ui.action(_("Incompatible database cache found, run eopkg rebuild-db to regenerate."))
                    return

                ctx.ui.debug("Removing incompatible %s of type %s" % (files_db, db_type))
                os.remove(files_db)

        if not os.path.exists(files_db):
            flag = "n"
        elif os.access(files_db, os.W_OK):
            flag = "w"
        else:
            flag = "r"

        self.filesdb = myopen(files_db, flag, protocol=FILESDB_PICKLE_PROTOCOL_VERSION)

# Ensure we use gdbm rather than bsddb which normally selected from anydb
# https://github.com/python/cpython/blob/v2.7.18/Lib/shelve.py#L218
class DbfilenameShelf(shelve.Shelf):
    def __init__(self, filename, flag='c', protocol=None, writeback=False):
        import gdbm
        shelve.Shelf.__init__(self, gdbm.open(filename, flag), protocol, writeback)

# Call our own DbfilenameShelf
# https://github.com/python/cpython/blob/v2.7.18/Lib/shelve.py#L230
def myopen(filename, flag='c', protocol=None, writeback=False):
    return DbfilenameShelf(filename, flag, protocol, writeback)
