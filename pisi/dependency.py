# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, 2017-Present Solus Developers
# SPDX-License-Identifier: GPL-2.0-or-later

"""dependency analyzer"""

from pisi import translate as _

import pisi.relation
import pisi.db
import pisi.pxml.autoxml as autoxml


class Dependency(pisi.relation.Relation):
    a_type = [autoxml.String, autoxml.OPTIONAL]

    def __str__(self):
        s = self.package
        if self.versionFrom:
            s += _(" version >= ") + self.versionFrom
        if self.versionTo:
            s += _(" version <= ") + self.versionTo
        if self.version:
            s += _(" version ") + self.version
        if self.releaseFrom:
            s += _(" release >= ") + self.releaseFrom
        if self.releaseTo:
            s += _(" release <= ") + self.releaseTo
        if self.release:
            s += _(" release ") + self.release
        if self.type:
            s += " (" + self.type + ")"
        return s

    def name(self):
        return self.package

    def satisfied_by_dict_repo(self, dict_repo):
        if self.package not in dict_repo:
            return False
        else:
            pkg = dict_repo[self.package]
            return self.satisfies_relation(pkg.version, pkg.release)

    def satisfied_by_installed(self):
        return pisi.relation.installed_package_satisfies(self)

    def satisfied_by_repo(self):
        packagedb = pisi.db.packagedb.PackageDB()
        pkgconfig32 = False
        if self.type == "pkgconfig":
            pkg = packagedb.get_package_by_pkgconfig(self.package)
            if pkg:
                return self.satisfies_relation(pkg.version, pkg.release)
            else:
                return False
        elif self.type == "pkgconfig32":
            pkg = packagedb.get_package_by_pkgconfig32(self.package)
            if pkg:
                return self.satisfies_relation(pkg.version, pkg.release)
            else:
                return False
        if not packagedb.has_package(self.package):
            return False
        else:
            pkg = packagedb.get_package(self.package)
            return self.satisfies_relation(pkg.version, pkg.release)

    # Added for AnyDependency, single Dependency always returns False
    def satisfied_by_any_installed_other_than(self, package):
        return False
