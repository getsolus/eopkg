# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

import os

import iksemel

import pisi
import pisi.context as ctx
import pisi.db.lazydb as lazydb
import pisi.uri
import pisi.urlcheck
import pisi.util
from pisi import translate as _
from pisi.file import File


class RepoError(pisi.Error):
    pass


class IncompatibleRepoError(RepoError):
    pass


class Repo:
    def __init__(self, indexuri):
        self.indexuri = indexuri


medias = (cd, usb, remote, local) = list(range(4))


class RepoOrder:
    def __init__(self, lmdb_store=None):
        self._doc = None
        self.legacy_repo_used = None
        self._repos_cache = {}
        self._lmdb_store = lmdb_store
        self._mapping = None
        if self._lmdb_store:
            self._mapping = self._lmdb_store.get_mapping("repo_config")
        self.repos = self._get_repos()

    def add(self, repo_name, repo_url, repo_type="remote"):
        repo_doc = self._get_doc()

        try:
            node = [x for x in repo_doc.tags("Repo")][-1]
            repo_node = node.appendTag("Repo")
        except IndexError:
            repo_node = repo_doc.insertTag("Repo")

        name_node = repo_node.insertTag("Name")
        name_node.insertData(repo_name)

        url_node = repo_node.insertTag("Url")
        old_uri = repo_url
        repo_url = pisi.urlcheck.switch_from_legacy(repo_url)

        if old_uri != repo_url:
            self.legacy_repo_used = True

        url_node.insertData(repo_url)

        name_node = repo_node.insertTag("Status")
        name_node.insertData("active")

        media_node = repo_node.insertTag("Media")
        media_node.insertData(repo_type)

        self._update(repo_doc)

    def set_status(self, repo_name, status):
        repo_doc = self._get_doc()

        found = False
        for r in repo_doc.tags("Repo"):
            if r.getTagData("Name") == repo_name:
                status_node = r.getTag("Status")
                if status_node:
                    status_node.firstChild().hide()
                    status_node.insertData(status)
                else:
                    status_node = r.insertTag("Status")
                    status_node.insertData(status)
                found = True

        if found:
            self._update(repo_doc)

    def get_status(self, repo_name):
        return self._repos_cache.get(repo_name, {}).get("status", "inactive")

    def get_uri(self, repo_name):
        return self._repos_cache.get(repo_name, {}).get("url", "")

    def remove(self, repo_name):
        repo_doc = self._get_doc()

        for r in repo_doc.tags("Repo"):
            if r.getTagData("Name") == repo_name:
                r.hide()

        self._update(repo_doc)

    def get_order(self):
        order = []

        # FIXME: get media order from pisi.conf
        for m in ["cd", "usb", "remote", "local"]:
            if m in self.repos:
                order.extend(self.repos[m])

        return order

    def _update(self, doc):
        repos_file_path = os.path.join(ctx.config.info_dir(), ctx.const.repos)
        repo_file = open(repos_file_path, "w")
        repo_file.write("%s\n" % doc.toPrettyString())
        repo_file.close()
        self._doc = None
        self.repos = self._get_repos()

        # Invalidate LMDB cache
        if self._lmdb_store and not self._lmdb_store.readonly:
            meta = self._lmdb_store.get_mapping("meta")
            meta["mtime_repos_xml"] = 0

    def _get_doc(self):
        if self._doc is None:
            repos_file = os.path.join(ctx.config.info_dir(), ctx.const.repos)
            if os.path.exists(repos_file):
                self._doc = iksemel.parse(repos_file)
            else:
                self._doc = iksemel.newDocument("REPOS")

        return self._doc

    def _get_repos(self):
        repos_file = os.path.join(ctx.config.info_dir(), ctx.const.repos)
        mtime = os.path.getmtime(repos_file) if os.path.exists(repos_file) else 0

        if self._mapping is not None:
            meta = self._lmdb_store.get_mapping("meta")
            cached_mtime = meta.get("mtime_repos_xml")
            if cached_mtime == mtime and len(self._mapping) > 0:
                self.repos = self._mapping.get("_order", {})
                self._repos_cache = self._mapping.get("_cache", {})
                return self.repos

        repo_doc = self._get_doc()
        order = {}
        self._repos_cache = {}

        for r in repo_doc.tags("Repo"):
            media = r.getTagData("Media")
            name = r.getTagData("Name")
            status = r.getTagData("Status")
            old_url = r.getTagData("Url")

            url = pisi.urlcheck.switch_from_legacy(old_url)
            if url != old_url:
                self.legacy_repo_used = True

            order.setdefault(media, []).append(name)
            self._repos_cache[name] = {
                "media": media,
                "status": status if status in ["active", "inactive"] else "inactive",
                "url": url.rstrip(),
            }

        if self._mapping is not None and not self._lmdb_store.readonly:
            self._mapping["_order"] = order
            self._mapping["_cache"] = self._repos_cache
            meta = self._lmdb_store.get_mapping("meta")
            meta["mtime_repos_xml"] = mtime

        return order


class RepoDB(lazydb.LazyDB):
    def __init__(self):
        lazydb.LazyDB.__init__(self, cacheable=False)

    @property
    def lmdb_mappings(self):
        return [self.repo_docs_db]

    def init(self):
        self.repo_docs_db = self.lmdb_store.get_mapping("repo_docs_db")
        self.repoorder = RepoOrder(self.lmdb_store)
        meta = self.lmdb_store.get_mapping("meta")

        if len(self.repoorder.repos) == 0:
            repo = pisi.db.repodb.Repo(
                pisi.uri.URI("https://cdn.getsol.us/repo/polaris/eopkg-index.xml.xz")
            )
            ctx.ui.warning("No repository found. Automatically adding Solus stable.")
            self.add_repo("Solus", repo, ctx.get_option("at"))

        for repo in self.list_repos(only_active=False):
            index_path = self.get_index_path(repo)
            if not os.path.exists(index_path):
                continue

            mtime = os.path.getmtime(index_path)
            cached_mtime = meta.get(f"mtime_rdb_{repo}")

            if cached_mtime != mtime or repo not in self.repo_docs_db:
                if self.lmdb_store.readonly and not self.lmdb_store.use_memory:
                    from pisi.db.lmdbstore import MemoryMapping

                    if not isinstance(self.repo_docs_db, MemoryMapping):
                        # Switch the whole mapping to memory for this session if it's stale
                        # but we can't write to LMDB.
                        new_mapping = MemoryMapping()
                        # Copy existing items if any
                        for k in self.repo_docs_db:
                            try:
                                new_mapping[k] = self.repo_docs_db[k]
                            except KeyError:
                                pass
                        self.repo_docs_db = new_mapping

                # Cache the XML document
                import gzip

                with open(index_path, "rb") as f:
                    self.repo_docs_db[repo] = gzip.zlib.compress(f.read())
                if not self.lmdb_store.readonly:
                    meta[f"mtime_rdb_{repo}"] = mtime

    def has_repo(self, name):
        return name in self.list_repos(only_active=False)

    def has_repo_url(self, url, only_active=True):
        return url in self.list_repo_urls(only_active)

    def get_index_path(self, repo_name):
        repo = self.get_repo(repo_name)

        index_path = repo.indexuri.get_uri()

        if File.is_compressed(index_path) or repo.indexuri.is_remote_file():
            index = os.path.basename(index_path)
            index_path = pisi.util.join_path(ctx.config.index_dir(), repo_name, index)

            if File.is_compressed(index_path):
                index_path = os.path.splitext(index_path)[0]

        return index_path

    def get_repo_doc(self, repo_name):
        xml = self.repo_docs_db.get(repo_name)
        if xml:
            import gzip

            return iksemel.parseString(gzip.zlib.decompress(xml).decode())

        index_path = self.get_index_path(repo_name)

        if not os.path.exists(index_path):
            ctx.ui.warning(_("%s repository needs to be updated") % repo_name)
            return iksemel.newDocument("PISI")

        try:
            doc = iksemel.parse(index_path)
            if not self.lmdb_store.readonly:
                import gzip

                with open(index_path, "rb") as f:
                    self.repo_docs_db[repo_name] = gzip.zlib.compress(f.read())
            return doc
        except Exception as e:
            raise RepoError(
                _(
                    "Error parsing repository index information. Index file does not exist or is malformed."
                )
            )

    def get_repo(self, repo):
        return Repo(pisi.uri.URI(self.get_repo_url(repo)))

    def get_repo_url(self, repo):
        url = self.repoorder.get_uri(repo)

        if self.repoorder.legacy_repo_used:
            repo_doc = self.repoorder._get_doc()

            for r in repo_doc.tags("Repo"):
                name = r.getTagData("Name")
                old_url = r.getTagData("Url")
                url = pisi.urlcheck.switch_from_legacy(old_url)

                if old_url != url:
                    self.remove_repo(name)
                    repo = pisi.db.repodb.Repo(pisi.uri.URI(url))
                    self.add_repo(name, repo, ctx.get_option("at"))

        return url

    def add_repo(self, name, repo_info, at=None):
        repo_path = pisi.util.join_path(ctx.config.index_dir(), name)

        try:
            os.makedirs(repo_path)
        except Exception as e:
            pass

        urifile_path = pisi.util.join_path(ctx.config.index_dir(), name, "uri")
        open(urifile_path, "w").write(repo_info.indexuri.get_uri())
        self.repoorder.add(name, repo_info.indexuri.get_uri())

    def remove_repo(self, name):
        pisi.util.clean_dir(os.path.join(ctx.config.index_dir(), name))
        self.repoorder.remove(name)

    def get_source_repos(self, only_active=True):
        repos = []
        for r in self.list_repos(only_active):
            if self.get_repo_doc(r).getTag("SpecFile"):
                repos.append(r)
        return repos

    def get_binary_repos(self, only_active=True):
        repos = []
        for r in self.list_repos(only_active):
            if not self.get_repo_doc(r).getTag("SpecFile"):
                repos.append(r)
        return repos

    def list_repos(self, only_active=True):
        return [
            x
            for x in self.repoorder.get_order()
            if (True if not only_active else self.repo_active(x))
        ]

    def list_repo_urls(self, only_active=True):
        repos = []
        for r in self.list_repos(only_active):
            repos.append(self.get_repo_url(r))
        return repos

    def get_repo_by_url(self, url):
        if not self.has_repo_url(url, only_active=False):
            return None

        for r in self.list_repos(only_active=False):
            if self.get_repo_url(r) == url:
                return r

    def activate_repo(self, name):
        self.repoorder.set_status(name, "active")

    def deactivate_repo(self, name):
        self.repoorder.set_status(name, "inactive")

    def repo_active(self, name):
        return self.repoorder.get_status(name) == "active"

    def get_distribution(self, name):
        doc = self.get_repo_doc(name)
        distro = doc.getTag("Distribution")
        return distro and distro.getTagData("SourceName")

    def get_distribution_release(self, name):
        doc = self.get_repo_doc(name)
        distro = doc.getTag("Distribution")
        return distro and distro.getTagData("Version")

    def check_distribution(self, name):
        if ctx.get_option("ignore_check"):
            return

        dist_name = self.get_distribution(name)
        if dist_name is None:
            return

        compatible = dist_name == ctx.config.values.general.distribution

        dist_release = self.get_distribution_release(name)
        if dist_release is not None:
            compatible &= dist_release == ctx.config.values.general.distribution_release

        if not compatible:
            self.deactivate_repo(name)
            raise IncompatibleRepoError(
                _(
                    "Repository '%s' is not compatible with your "
                    "distribution. Repository is disabled."
                )
                % name
            )
