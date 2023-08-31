# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, 2017-Present Solus Developers
# SPDX-License-Identifier: GPL-2.0-or-later

import pisi
import pisi.pxml.xmlfile as xmlfile
import pisi.pxml.autoxml as autoxml


class Error(pisi.Error):
    pass


class Group(xmlfile.XmlFile, metaclass=autoxml.autoxml):
    "representation for group declarations"

    t_Name = [autoxml.String, autoxml.MANDATORY]
    t_LocalName = [autoxml.LocalText, autoxml.MANDATORY]
    t_Icon = [autoxml.String, autoxml.OPTIONAL]


class Groups(xmlfile.XmlFile, metaclass=autoxml.autoxml):
    "representation for component declarations"

    tag = "PISI"

    t_Groups = [[Group], autoxml.OPTIONAL, "Groups/Group"]
