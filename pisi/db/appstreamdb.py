# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

import pisi
import pisi.db
import pisi.appstream
import pisi.db.itembyrepo
from pisi import translate as _
from pisi.db import lazydb


class AppstreamNotFound(Exception):
    pass


class AppstreamDB(lazydb.LazyDB):
    def __init__(self):
        lazydb.LazyDB.__init__(self, cacheable=False)

    def init(self):
        catalog_nodes = {}
        catalog_components = {}

        repodb = pisi.db.repodb.RepoDB()

        for repo in repodb.list_repos():
            doc = repodb.get_repo_doc(repo)
            catalog_nodes[repo] = self.__generate_catalogs(doc)
            catalog_components[repo] = self.__generate_catalog(doc)

        self.adb = pisi.db.itembyrepo.ItemByRepo(catalog_nodes)
        self.acdb = pisi.db.itembyrepo.ItemByRepo(catalog_components)

    def __generate_catalog(self, doc):
        catalogs = {}
        for c in doc.tags("AppstreamCatalog"):
            catalog = c.getTagData("Origin") or "unknown"
            catalog_info = {
                "uri": c.getTagData("URI"),
                "icons_sizes": [x.getAttribute("size") for x in c.tags("Icons")],
                "icon_urls": [x.getTagData("URI") for x in c.tags("Icons")],
            }
            catalogs.setdefault(catalog, []).append(catalog_info)
        return catalogs

    def __generate_catalogs(self, doc):
        return dict([(x.getTagData("Origin"), x.toString()) for x in doc.tags("AppstreamCatalog")])

    def has_catalog(self, name, repo=None):
        return self.adb.has_item(name, repo)

    def list_catalogs(self, repo=None):
        return self.adb.get_item_keys(repo)

    def get_catalog(self, name, repo=None):
        if not self.has_catalog(name, repo):
            raise AppstreamNotFound(_("Appstream catalog %s not found") % name)

        catalog = pisi.appstream.AppstreamCatalog()
        catalog.parse(self.adb.get_item(name, repo))

        return catalog

    def get_catalog_components(self, name, repo=None):
        if not self.has_catalog(name, repo):
            raise AppstreamNotFound(_("Appstream catalog %s not found") % name)

        if self.acdb.has_item(name):
            return self.acdb.get_item(name, repo)

        return []
