# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

"""Files module provides access to files.xml. files.xml is generated
during the build process of a package and used in installation."""


import pisi.pxml.autoxml as autoxml


class FileInfo(metaclass=autoxml.autoxml):
    """File holds the information for a File node/tag in files.xml"""

    t_Path = [autoxml.String, autoxml.MANDATORY]
    t_Type = [autoxml.String, autoxml.MANDATORY]
    t_Size = [autoxml.Long, autoxml.OPTIONAL]
    t_Uid = [autoxml.String, autoxml.OPTIONAL]
    t_Gid = [autoxml.String, autoxml.OPTIONAL]
    t_Mode = [autoxml.String, autoxml.OPTIONAL]
    t_Hash = [autoxml.String, autoxml.OPTIONAL, "SHA1Sum"]
    t_Permanent = [autoxml.String, autoxml.OPTIONAL]

    def __str__(self):
        s = "/%s, type: %s, size: %s, sha1sum: %s" % (
            self.path,
            self.type,
            self.size,
            self.hash,
        )
        return s


class Files(autoxml.xmlfile.XmlFile, metaclass=autoxml.autoxml):
    tag = "Files"

    t_List = [[FileInfo], autoxml.OPTIONAL, "File"]

    def append(self, fileinfo):
        self.list.append(fileinfo)
