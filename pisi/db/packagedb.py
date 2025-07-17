# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later
#
# installation database
#

import re
import time
import gzip
import gettext
import datetime

import iksemel

import pisi.db
import pisi.metadata
import pisi.dependency
import pisi.db.itembyrepo
import pisi.db.lazydb as lazydb
from pisi import translate as _


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
            self.__obsoletes[repo] = self.__generate_obsoletes(doc)
            self.__replaces[repo] = self.__generate_replaces(doc)

        self.pdb = pisi.db.itembyrepo.ItemByRepo(self.__package_nodes, compressed=True)
        self.rvdb = pisi.db.itembyrepo.ItemByRepo(self.__revdeps)
        self.odb = pisi.db.itembyrepo.ItemByRepo(self.__obsoletes)
        self.rpdb = pisi.db.itembyrepo.ItemByRepo(self.__replaces)

    def __generate_replaces(self, doc):
        return [
            x.getTagData("Name")
            for x in doc.tags("Package")
            if x.getTagData("Replaces")
        ]

    def __generate_obsoletes(self, doc):
        distribution = doc.getTag("Distribution")
        obsoletes = distribution and distribution.getTag("Obsoletes")
        src_repo = doc.getTag("SpecFile") is not None

        if not obsoletes or src_repo:
            return []

        return [x.firstChild().data() for x in obsoletes.tags("Package")]

    def __generate_packages(self, doc):
        return dict(
            [
                (x.getTagData("Name"), gzip.zlib.compress(x.toString().encode()))
                for x in doc.tags("Package")
            ]
        )

    def __generate_revdeps(self, doc):
        revdeps = {}
        for node in doc.tags("Package"):
            name = node.getTagData("Name")
            deps = node.getTag("RuntimeDependencies")
            if deps:
                for dep in deps.tags("Dependency"):
                    revdeps.setdefault(dep.firstChild().data(), set()).add(
                        (name, dep.toString())
                    )
        return revdeps

    def has_package(self, name, repo=None):
        return self.pdb.has_item(name, repo)

    def get_package(self, name, repo=None):
        pkg, repo = self.get_package_repo(name, repo)
        return pkg

    def get_pkgconfig_providers(self, repo=None):
        """get_pkgconfig_providers will return a tuple of two dicts

        The first dict ([0]) contains the standard pkgconfig mapping
        to package name.
        The second dict ([1]) contains the pkgconfig32 mapping to
        package name.
        """
        repodb = pisi.db.repodb.RepoDB()

        pkgConfigs = dict()
        pkgConfigs32 = dict()

        def map_providers(doc, pkgConfigs: dict, pkgConfigs32: dict):
            for pkg in doc.tags("Package"):
                prov = pkg.getTag("Provides")
                name = pkg.getTagData("Name")
                if not prov:
                    continue
                for node in prov.tags("PkgConfig32"):
                    pkgConfigs32[node.firstChild().data()] = name
                for node in prov.tags("PkgConfig"):
                    pkgConfigs[node.firstChild().data()] = name
            return (pkgConfigs, pkgConfigs32)

        if repo is None:
            for repo in repodb.list_repos():
                doc = repodb.get_repo_doc(repo)
                pkgConfig, pkgConfigs32 = map_providers(
                        doc, pkgConfigs, pkgConfigs32)
        else:
            repodb = pisi.db.repodb.RepoDB()
            if repo not in repodb.list_repos(only_active=False):
                raise Exception(_("Repo %s not found.") % repo)
            doc = repodb.get_repo_doc(repo)
            pkgConfig, pkgConfigs32 = map_providers(
                        doc, pkgConfigs, pkgConfigs32)

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

    def __get_version(self, meta_doc):
        history = meta_doc.getTag("History")
        version = history.getTag("Update").getTagData("Version")
        release = history.getTag("Update").getAttribute("release")

        # TODO Remove None
        return version, release, None

    def __get_distro_release(self, meta_doc):
        distro = meta_doc.getTagData("Distribution")
        release = meta_doc.getTagData("DistributionRelease")

        return distro, release

    def get_version_and_distro_release(self, name, repo):
        if not self.has_package(name, repo):
            raise Exception(_("Package %s not found.") % name)
        pkg_doc = iksemel.parseString(self.pdb.get_item(name, repo).decode())
        return self.__get_version(pkg_doc) + self.__get_distro_release(pkg_doc)

    def get_version(self, name, repo):
        if not self.has_package(name, repo):
            raise Exception(_("Package %s not found.") % name)

        pkg_doc = iksemel.parseString(self.pdb.get_item(name, repo).decode())
        return self.__get_version(pkg_doc)

    def get_package_repo(self, name, repo=None):
        pkg, repo = self.pdb.get_item_repo(name, repo)
        package = pisi.metadata.Package()
        package.parse(pkg)
        return package, repo

    def which_repo(self, name):
        return self.pdb.which_repo(name)

    def get_obsoletes(self, repo=None):
        return self.odb.get_list_item(repo)

    def get_isa_packages(self, isa):
        repodb = pisi.db.repodb.RepoDB()

        packages = set()
        for repo in repodb.list_repos():
            doc = repodb.get_repo_doc(repo)
            for package in doc.tags("Package"):
                if package.getTagData("IsA"):
                    for node in package.tags("IsA"):
                        if node.firstChild().data() == isa:
                            packages.add(package.getTagData("Name"))
        return list(packages)

    def get_rev_deps(self, name, repo=None):
        try:
            rvdb = self.rvdb.get_item(name, repo)
        except (
            Exception
        ):  # FIXME: what exception could we catch here, replace with that.
            return []

        rev_deps = []
        for pkg, dep in rvdb:
            node = iksemel.parseString(dep)
            dependency = pisi.dependency.Dependency()
            dependency.package = node.firstChild().data()
            if node.attributes():
                attr = node.attributes()[0].decode()
                dependency.__dict__[attr] = node.getAttribute(attr)
            rev_deps.append((pkg, dependency))
        return rev_deps

    # replacesdb holds the info about the replaced packages (ex. gaim -> pidgin)
    def get_replaces(self, repo=None):
        pairs = {}

        for pkg_name in self.rpdb.get_list_item():
            xml = self.pdb.get_item(pkg_name, repo)
            package = iksemel.parseString(xml.decode())
            replaces_tag = package.getTag("Replaces")
            if replaces_tag:
                for node in replaces_tag.tags("Package"):
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
        historydb = pisi.db.historydb.HistoryDB()
        if since:
            since_date = datetime.datetime(*time.strptime(since, "%Y-%m-%d")[0:6])
        else:
            since_date = datetime.datetime(
                *time.strptime(historydb.get_last_repo_update(), "%Y-%m-%d")[0:6]
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
