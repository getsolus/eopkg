# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, 2017-Present Solus Developers
# SPDX-License-Identifier: GPL-2.0-or-later

import zlib
from pisi import translate as _

import pisi.db


class ItemByRepo:
    def __init__(self, dbobj, compressed=False):
        self.dbobj = dbobj
        self.compressed = compressed

    def has_repo(self, repo):
        return repo in self.dbobj

    def has_item(self, item, repo=None):
        for r in self.item_repos(repo):
            if r in self.dbobj and item in self.dbobj[r]:
                return True

        return False

    def which_repo(self, item):
        for r in pisi.db.repodb.RepoDB().list_repos():
            if r in self.dbobj and item in self.dbobj[r]:
                return r

        raise Exception(_("%s not found in any repository.") % str(item))

    def get_item_repo(self, item, repo=None):
        for r in self.item_repos(repo):
            if r in self.dbobj and item in self.dbobj[r]:
                if self.compressed:
                    return zlib.decompress(self.dbobj[r][item]), r
                else:
                    return self.dbobj[r][item], r

        raise Exception(_("Repo item %s not found") % str(item))

    def get_item(self, item, repo=None):
        item, repo = self.get_item_repo(item, repo)
        return item

    def get_item_keys(self, repo=None):
        items = []
        for r in self.item_repos(repo):
            if not self.has_repo(r):
                raise Exception(_("Repository %s does not exist.") % repo)

            if r in self.dbobj:
                items.extend(list(self.dbobj[r].keys()))

        return list(set(items))

    def get_list_item(self, repo=None):
        items = []
        for r in self.item_repos(repo):
            if not self.has_repo(r):
                raise Exception(_("Repository %s does not exist.") % repo)

            if r in self.dbobj:
                items.extend(self.dbobj[r])

        return list(set(items))

    def get_items_iter(self, repo=None):
        for r in self.item_repos(repo):
            if not self.has_repo(r):
                raise Exception(_("Repository %s does not exist.") % repo)

            for item, data in self.dbobj[r].items():
                yield item, zlib.decompress(data) if self.compressed else data

    def item_repos(self, repo=None):
        repos = pisi.db.repodb.RepoDB().list_repos()
        if repo:
            repos = [repo]
        return repos
