# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

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


class FilesDB(lazydb.LazyDB):
    def init(self):
        self.filesdb = {}
        self.__check_filesdb()

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
        if isinstance(self.filesdb, shelve.DbfilenameShelf):
            return

        files_db = os.path.join(ctx.config.info_dir(), ctx.const.files_db)

        if not os.path.exists(files_db):
            if not os.access(files_db, os.W_OK):
                return
            flag = "n"
        elif os.access(files_db, os.W_OK):
            flag = "w"
        else:
            flag = "r"

        self.filesdb = shelve.open(
            util.join_path(ctx.config.info_dir(), ctx.const.files_db), flag
        )
