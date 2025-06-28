# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

import pisi
import pisi.pxml.xmlfile as xmlfile
import pisi.pxml.autoxml as autoxml


class Error(pisi.Error):
    pass


class Icons(xmlfile.XmlFile, metaclass=autoxml.autoxml):

    a_size = [autoxml.String, autoxml.MANDATORY]
    t_URI = [autoxml.String, autoxml.MANDATORY]


class AppstreamCatalog(xmlfile.XmlFile, metaclass=autoxml.autoxml):
    "representation for appstream declarations"

    t_Origin = [autoxml.String, autoxml.MANDATORY]
    t_URI = [autoxml.String, autoxml.MANDATORY]
    t_Icons = [[Icons], autoxml.OPTIONAL, "Icons"]


class AppstreamCatalogs(xmlfile.XmlFile, metaclass=autoxml.autoxml):
    "representation for component declarations"

    tag = "PISI"

    t_Appstreams = [[AppstreamCatalog], autoxml.MANDATORY, "AppstreamCatalogs/AppstreamCatalog"]
