# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, 2017-Present Solus Developers
# SPDX-License-Identifier: GPL-2.0-or-later

import pisi
import pisi.group
from pisi import translate as _
from pisi.db import lazydb


class GroupNotFound(Exception):
    pass


class GroupDB(lazydb.LazyDB):
    def __init__(self):
        lazydb.LazyDB.__init__(self, cacheable=True)

    def init(self):
        group_nodes = {}
        group_components = {}

        repodb = pisi.db.repodb.RepoDB()

        for repo in repodb.list_repos():
            doc = repodb.get_repo_doc(repo)
            group_nodes[repo] = self.__generate_groups(doc)
            group_components[repo] = self.__generate_components(doc)

        self.gdb = pisi.db.itembyrepo.ItemByRepo(group_nodes)
        self.gcdb = pisi.db.itembyrepo.ItemByRepo(group_components)

    def __generate_components(self, doc):
        groups = {}
        for c in doc.tags("Component"):
            group = c.getTagData("Group")
            if not group:
                group = "unknown"
            groups.setdefault(group, []).append(c.getTagData("Name"))
        return groups

    def __generate_groups(self, doc):
        return dict([(x.getTagData("Name"), x.toString()) for x in doc.tags("Group")])

    def has_group(self, name, repo=None):
        return self.gdb.has_item(name, repo)

    def list_groups(self, repo=None):
        return self.gdb.get_item_keys(repo)

    def get_group(self, name, repo=None):
        if not self.has_group(name, repo):
            raise GroupNotFound(_("Group %s not found") % name)

        group = pisi.group.Group()
        group.parse(self.gdb.get_item(name, repo))

        return group

    def get_group_components(self, name, repo=None):
        if not self.has_group(name, repo):
            raise GroupNotFound(_("Group %s not found") % name)

        if self.gcdb.has_item(name):
            return self.gcdb.get_item(name, repo)

        return []
