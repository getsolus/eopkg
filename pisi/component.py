# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

import pisi.pxml.xmlfile as xmlfile
import pisi.pxml.autoxml as autoxml


class Error(object, metaclass=autoxml.autoxml):
    pass


class Obsolete(metaclass=autoxml.autoxml):
    s_Package = [autoxml.String, autoxml.MANDATORY]

    def __str__(self):
        return self.package


class Distribution(xmlfile.XmlFile, metaclass=autoxml.autoxml):
    tag = "PISI"

    t_SourceName = [autoxml.Text, autoxml.MANDATORY]  # name of distribution (source)
    t_Description = [autoxml.LocalText, autoxml.MANDATORY]
    t_Version = [autoxml.Text, autoxml.OPTIONAL]
    t_Type = [autoxml.Text, autoxml.MANDATORY]
    t_Dependencies = [[autoxml.Text], autoxml.OPTIONAL, "Dependencies/Distribution"]

    t_BinaryName = [
        autoxml.Text,
        autoxml.OPTIONAL,
    ]  # name of repository (binary distro)
    t_Architecture = [autoxml.Text, autoxml.OPTIONAL]  # architecture identifier

    t_Obsoletes = [[Obsolete], autoxml.OPTIONAL, "Obsoletes/Package"]


class Maintainer(xmlfile.XmlFile, metaclass=autoxml.autoxml):
    "representation for component responsibles"

    t_Name = [autoxml.Text, autoxml.MANDATORY]
    t_Email = [autoxml.String, autoxml.MANDATORY]

    def __str__(self):
        s = "%s <%s>" % (self.name, self.email)
        return s


class Component(xmlfile.XmlFile, metaclass=autoxml.autoxml):
    "representation for component declarations"

    t_Name = [autoxml.String, autoxml.MANDATORY]  # fully qualified name

    # component name in other languages, for instance in Turkish
    # LocalName for system.base could be sistem.taban or "Taban Sistem",
    # this could be useful for GUIs

    t_LocalName = [autoxml.LocalText, autoxml.OPTIONAL]

    # Information about the component
    t_Summary = [autoxml.LocalText, autoxml.OPTIONAL]
    t_Description = [autoxml.LocalText, autoxml.OPTIONAL]
    t_Group = [autoxml.String, autoxml.OPTIONAL]

    # Component responsible
    t_Maintainer = [Maintainer, autoxml.OPTIONAL]

    # the parts of this component.
    # to be filled by the component database, thus it is optional.
    t_Packages = [[autoxml.String], autoxml.OPTIONAL, "Parts/Package"]

    t_Sources = [[autoxml.String], autoxml.OPTIONAL, "Parts/Source"]


class Components(xmlfile.XmlFile, metaclass=autoxml.autoxml):
    "representation for component declarations"

    tag = "PISI"

    t_Components = [[Component], autoxml.OPTIONAL, "Components/Component"]


# FIXME: there will be no component.xml only components.xml
class CompatComponent(Component):
    tag = "PISI"

    t_VisibleTo = [autoxml.String, autoxml.OPTIONAL]
