# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

import os

import pisi
import pisi.group
from pisi import context as ctx
from pisi import translate as _
from pisi.db import lazydb


class GroupNotFound(Exception):
    pass


class GroupDB(lazydb.LazyDB):
    def __init__(self):
        # Set cacheable=False because we use LMDB now
        lazydb.LazyDB.__init__(self, cacheable=False)

    @property
    def lmdb_mappings(self):
        mappings = []
        for repo in self.__group_nodes:
            mappings.append(self.__group_nodes[repo])
            mappings.append(self.__group_components[repo])
        return mappings

    def init(self):
        repodb = pisi.db.repodb.RepoDB()
        repos = repodb.list_repos()

        self.__group_nodes = {
            repo: self.lmdb_store.get_mapping(f"gdb_{repo}") for repo in repos
        }
        self.__group_components = {
            repo: self.lmdb_store.get_mapping(f"gcdb_{repo}") for repo in repos
        }

        meta = self.lmdb_store.get_mapping("meta")

        for repo in repos:
            index_path = repodb.get_index_path(repo)
            if not os.path.exists(index_path):
                continue

            mtime = os.path.getmtime(index_path)
            cached_mtime = meta.get(f"mtime_gdb_{repo}")

            if len(self.__group_nodes[repo]) == 0 or cached_mtime != mtime:
                if self.lmdb_store.readonly and not self.lmdb_store.use_memory:
                    from pisi.db.lmdbstore import MemoryMapping

                    self.__group_nodes[repo] = MemoryMapping()
                    self.__group_components[repo] = MemoryMapping()

                doc = repodb.get_repo_doc(repo)
                self.__group_nodes[repo].clear()
                self.__group_components[repo].clear()

                self.__group_nodes[repo].update_bulk(self.__generate_groups(doc))
                self.__group_components[repo].update_bulk(
                    self.__generate_components(doc)
                )
                if not self.lmdb_store.readonly:
                    meta[f"mtime_gdb_{repo}"] = mtime

        self.gdb = pisi.db.itembyrepo.ItemByRepo(self.__group_nodes)
        self.gcdb = pisi.db.itembyrepo.ItemByRepo(self.__group_components)

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
