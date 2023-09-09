# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

import datetime
import re
import time
from lxml import etree as xml
import zlib
from typing import Iterator
from pisi import db

import pisi.db
import pisi.dependency
import pisi.metadata
from pisi import translate as _
from pisi.db import historydb, itembyrepo, lazydb, repodb


class PackageDB(lazydb.LazyDB):
    def __init__(self):
        lazydb.LazyDB.__init__(self, cacheable=True)

    def init(self):
        self.__package_nodes = {}  # Packages
        self.__revdeps = {}  # Reverse dependencies
        self.__obsoletes = {}  # Obsoletes
        self.__replaces = {}  # Replaces

        repodb = pisi.db.repodb.RepoDB()

        for repo in repodb.list_repos():
            doc = repodb.get_repo_doc(repo)
            self.__package_nodes[repo] = self.__generate_packages(doc)
            self.__revdeps[repo] = self.__generate_revdeps(doc)
            self.__obsoletes[repo] = list(self.__generate_obsoletes(doc))
            self.__replaces[repo] = list(self.__generate_replaces(doc))

        self.pdb = itembyrepo.ItemByRepo(self.__package_nodes, compressed=True)
        self.rvdb = itembyrepo.ItemByRepo(self.__revdeps)
        self.odb = itembyrepo.ItemByRepo(self.__obsoletes)
        self.rpdb = itembyrepo.ItemByRepo(self.__replaces)

    def __generate_replaces(self, doc: xml._ElementTree) -> Iterator[str]:
        for pkg in doc.iterfind("Package"):
            if not pkg.findtext("Replaces"):
                continue
            name = pkg.findtext("Name")
            if name is not None:
                yield name

    def __generate_obsoletes(self, doc: xml._ElementTree) -> Iterator[str]:
        distribution = doc.find("Distribution")
        if distribution is not None:
            obsoletes = distribution.find("Obsoletes")
        else:
            obsoletes = distribution
        src_repo = doc.find("SpecFile") is not None

        if obsoletes is None or src_repo:
            return iter(())
        return (x.text for x in obsoletes.iterfind("Package") if x.text is not None)

    def __generate_packages(self, doc: xml._ElementTree) -> dict[str, bytes]:
        def source():
            for pkg in doc.iterfind("Package"):
                name = pkg.findtext("Name")
                if not name:
                    continue
                xml.indent(pkg)
                yield (name, zlib.compress(xml.tostring(pkg)))

        return dict(source())

    def __generate_revdeps(
        self, doc: xml._ElementTree
    ) -> dict[str, set[tuple[str, bytes]]]:
        revdeps: dict[str, set[tuple[str, bytes]]] = {}
        for pkg in doc.iterfind("Package"):
            name = pkg.findtext("Name")
            if not name:
                continue
            deps = pkg.find("RuntimeDependencies")
            if deps is None:
                continue
            for dep in deps.iterfind("Dependency"):
                if not dep.text:
                    continue
                xml.indent(dep)
                revdeps.setdefault(dep.text, set()).add((name, xml.tostring(pkg)))
        return revdeps

    def has_package(self, name: str, repo=None):
        return self.pdb.has_item(name, repo)

    def get_package(self, name: str, repo=None):
        pkg, repo = self.get_package_repo(name, repo)
        return pkg

    def get_pkgconfig_providers(self, repo=None):
        """get_pkgconfig_providers will return a tuple of two dicts

        The first dict ([0]) contains the standard pkgconfig mapping
        to package name.
        The second dict ([1]) contains the pkgconfig32 mapping to
        package name.
        """
        db = repodb.RepoDB()

        pkgConfigs = dict()
        pkgConfigs32 = dict()

        for repo in db.list_repos(repo):
            doc = db.get_repo_doc(repo)
            for pkg in doc.iterfind("Package"):
                prov = pkg.find("Provides")
                name = pkg.findtext("Name")
                if not prov or not name:
                    continue
                for node in prov.iterfind("PkgConfig32"):
                    pkgConfigs32[node.text] = name
                for node in prov.iterfind("PkgConfig"):
                    pkgConfigs[node.text] = name
        return (pkgConfigs, pkgConfigs32)

    def get_package_by_pkgconfig(self, pkgconfig):
        """This method is deprecated. Use get_pkgconfig_providers instead"""
        provs = self.get_pkgconfig_providers()[0]
        if pkgconfig in provs:
            return self.get_package(provs[pkgconfig])
        return None

    def get_package_by_pkgconfig32(self, pkgconfig):
        """This method is deprecated. Use get_pkgconfig_providers instead"""
        provs = self.get_pkgconfig_providers()[1]
        if pkgconfig in provs:
            return self.get_package(provs[pkgconfig])
        return None

    def search_in_packages(self, packages, terms, lang=None):
        resum = "<Summary xml:lang=.(%s|en).>.*?%s.*?</Summary>"
        redesc = "<Description xml:lang=.(%s|en).>.*?%s.*?</Description>"
        if not lang:
            lang = pisi.pxml.autoxml.LocalText.get_lang()
        found = []
        for name in packages:
            xml = self.pdb.get_item(name)
            if terms == [
                term
                for term in terms
                if re.compile(term, re.I).search(name)
                or re.compile(resum % (lang, term), re.I).search(xml.decode())
                or re.compile(redesc % (lang, term), re.I).search(xml.decode())
            ]:
                found.append(name)
        return found

    def search_package(self, terms, lang=None, repo=None, fields=None):
        """
        fields (dict) : looks for terms in the fields which are marked as True
        If the fields is equal to None the method will search on all fields

        example :
        if fields is equal to : {'name': True, 'summary': True, 'desc': False}
        This method will return only package that contents terms in the package
        name or summary
        """
        resum = "<Summary xml:lang=.(%s|en).>.*?%s.*?</Summary>"
        redesc = "<Description xml:lang=.(%s|en).>.*?%s.*?</Description>"
        if not lang:
            lang = pisi.pxml.autoxml.LocalText.get_lang()
        if not fields:
            fields = {"name": True, "summary": True, "desc": True}
        found = []
        for name, xml in self.pdb.get_items_iter(repo):
            if terms == [
                term
                for term in terms
                if (fields["name"] and re.compile(term, re.I).search(name))
                or (
                    fields["summary"]
                    and re.compile(resum % (lang, term), re.I).search(xml.decode())
                )
                or (
                    fields["desc"]
                    and re.compile(redesc % (lang, term), re.I).search(xml.decode())
                )
            ]:
                found.append(name)
        return found

    def get_version_and_distro_release(
        self, name: str, repo
    ) -> tuple[str, str, None, str, str] | None:
        if not self.has_package(name, repo):
            raise Exception(_("Package %s not found.") % name)

        pkg_doc = xml.ElementTree(xml.fromstring(self.pdb.get_item(name, repo)))
        version = db._get_version(pkg_doc)
        release = db._get_distro_release(pkg_doc)
        if not version or not release:
            return None
        return version + release

    def get_version(self, name, repo):
        if not self.has_package(name, repo):
            raise Exception(_("Package %s not found.") % name)

        pkg_doc = xml.ElementTree(xml.fromstring(self.pdb.get_item(name, repo)))
        return db._get_version(pkg_doc)

    def get_package_repo(self, name, repo=None):
        pkg, repo = self.pdb.get_item_repo(name, repo)
        package = pisi.metadata.Package()
        package.parse(pkg)
        return package, repo

    def which_repo(self, name):
        return self.pdb.which_repo(name)

    def get_obsoletes(self, repo=None):
        return self.odb.get_list_item(repo)

    def get_isa_packages(self, isa: str) -> set[str]:
        db = repodb.RepoDB()
        packages = set()
        for repo in db.list_repos():
            doc = db.get_repo_doc(repo)
            for package in doc.iterfind("Package"):
                if not package.findtext("IsA"):
                    continue
                for node in package.iterfind("IsA"):
                    if node.text != isa:
                        continue
                    name = package.findtext("Name")
                    if not name:
                        continue
                    packages.add(name)
        return packages

    def get_rev_deps(self, name: str, repo=None):
        try:
            rvdb = self.rvdb.get_item(name, repo)
        except Exception:
            # FIXME: what exception could we catch here, replace with that.
            return []

        rev_deps = []
        for pkg, dep in rvdb:
            node = xml.fromstring(dep)
            dependency = pisi.dependency.Dependency()
            dependency.package = node.text

            attr = next(iter(node.attrib.items()), None)
            if attr:
                dependency.__dict__[attr[0]] = attr[1]
            rev_deps.append((pkg, dependency))
        return rev_deps

    # replacesdb holds the info about the replaced packages (ex. gaim -> pidgin)
    def get_replaces(self, repo=None):
        pairs = {}

        for pkg_name in self.rpdb.get_list_item():
            xml_content = self.pdb.get_item(pkg_name, repo)
            package = xml.ElementTree(xml.fromstring(xml_content))
            replaces_tag = package.find("Replaces")
            if replaces_tag is not None:
                for node in replaces_tag.iterfind("Package"):
                    r = pisi.relation.Relation()
                    # XXX Is there a better way to do this?
                    r.decode(node, [])
                    if pisi.replace.installed_package_replaced(r):
                        pairs.setdefault(r.package, []).append(pkg_name)

        return pairs

    def list_packages(self, repo):
        return self.pdb.get_item_keys(repo)

    def list_newest(self, repo, since=None):
        packages = []
        db = historydb.HistoryDB()
        if since:
            since_date = datetime.datetime(*time.strptime(since, "%Y-%m-%d")[0:6])
        else:
            since_date = datetime.datetime(
                *time.strptime(db.get_last_repo_update(), "%Y-%m-%d")[0:6]
            )

        for pkg in self.list_packages(repo):
            failed = False
            try:
                enter_date = datetime.datetime(
                    *time.strptime(self.get_package(pkg).history[-1].date, "%m-%d-%Y")[
                        0:6
                    ]
                )
            except:
                failed = True
            if failed:
                try:
                    enter_date = datetime.datetime(
                        *time.strptime(
                            self.get_package(pkg).history[-1].date, "%Y-%m-%d"
                        )[0:6]
                    )
                except:
                    enter_date = datetime.datetime(
                        *time.strptime(
                            self.get_package(pkg).history[-1].date, "%Y-%d-%m"
                        )[0:6]
                    )

            if enter_date >= since_date:
                packages.append(pkg)
        return packages
