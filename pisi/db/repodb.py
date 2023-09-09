# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later


import os
from lxml import etree as xml

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
    def __init__(self):
        self.legacy_repo_used = False
        self.repos = self._get_repos()

    def add(self, repo_name: str, repo_url: str, repo_type="remote"):
        new_repo = xml.Element("Repo")

        name_elem = xml.Element("Name")
        name_elem.text = repo_name
        new_repo.append(name_elem)

        url_elem = xml.Element("Url")
        old_uri = repo_url
        repo_url = pisi.urlcheck.switch_from_legacy(repo_url)
        if old_uri != repo_url:
            self.legacy_repo_used = True
        url_elem.text = repo_url
        new_repo.append(url_elem)

        status_elem = xml.Element("Status")
        status_elem.text = "active"
        new_repo.append(status_elem)

        media_elem = xml.Element("Media")
        media_elem.text = repo_type
        new_repo.append(media_elem)

        repo_doc = self._get_doc()
        repo_doc.getroot().append(new_repo)
        self._update(repo_doc)

    def set_status(self, repo_name: str, status: str):
        # TODO: document possible values of status, or make it an enum.

        repo_doc = self._get_doc()
        for r in repo_doc.iterfind("Repo"):
            if r.findtext("Name") == repo_name:
                status_elem = r.find("Status")
                if status_elem:
                    status_elem.text = status
                else:
                    status_elem = xml.Element("Status")
                    status_elem.text = status
                    r.append(status_elem)
        self._update(repo_doc)

    def get_status(self, repo_name: str) -> str:
        repo_doc = self._get_doc()
        for r in repo_doc.iterfind("Repo"):
            if r.findtext("Name") == repo_name:
                status_elem = r.find("Status")
                if status_elem is not None:
                    if status_elem.text in ["active", "inactive"]:
                        return status_elem.text
        return "inactive"

    def get_uri(self, repo_name: str) -> str:
        repo_doc = self._get_doc()
        url = ""

        for r in repo_doc.iterfind("Repo"):
            name = r.findtext("Name")
            uri = r.findtext("Url")

            if name == repo_name:
                url = pisi.urlcheck.switch_from_legacy(uri)
                if url != uri:
                    self.legacy_repo_used = True
                break
        return url.rstrip()

    def remove(self, repo_name: str):
        repo_doc = self._get_doc()
        for r in repo_doc.iterfind("Repo"):
            if r.findtext("Name") == repo_name:
                repo_doc.getroot().remove(r)
        self._update(repo_doc)

    def get_order(self) -> list[str]:
        """Returns a list of repo names ordered by the priority of their media."""
        order = []
        # FIXME: get media order from pisi.conf
        for m in ["cd", "usb", "remote", "local"]:
            if m in self.repos:
                order.extend(self.repos[m])
        return order

    def _update(self, doc: xml._ElementTree):
        repos_file = os.path.join(ctx.config.info_dir(), ctx.const.repos)
        xml.indent(doc)
        doc.write(repos_file)
        self.repos = self._get_repos()

    def _get_doc(self) -> xml._ElementTree:
        repos_file = os.path.join(ctx.config.info_dir(), ctx.const.repos)
        if os.path.exists(repos_file):
            doc = xml.parse(repos_file)
        else:
            doc = xml.ElementTree(xml.Element("REPOS"))
        return doc

    def _get_repos(self) -> dict[str, list[str]]:
        """Returns a dictionary where keys are media types and values are lists of repo names."""
        repo_doc = self._get_doc()
        order: dict[str, list[str]] = {}

        for r in repo_doc.iterfind("Repo"):
            media = r.findtext("Media")
            name = r.findtext("Name")
            if media is None or name is None:
                continue

            # Why are these vars ignored?
            status = r.findtext("Status")
            old_url = r.findtext("Url")
            url = pisi.urlcheck.switch_from_legacy(old_url)

            order.setdefault(media, []).append(name)
        return order


class RepoDB(lazydb.LazyDB):
    def init(self):
        self.repoorder = RepoOrder()

        if len(self.repoorder.repos) == 0:
            repo = pisi.db.repodb.Repo(
                pisi.uri.URI("https://cdn.getsol.us/repo/shannon/eopkg-index.xml.xz")
            )
            ctx.ui.warning("No repository found. Automatically adding Solus stable.")
            self.add_repo("Solus", repo, ctx.get_option("at"))

    def has_repo(self, name: str) -> bool:
        return name in self.list_repos(only_active=False)

    def has_repo_url(self, url: str, only_active=True):
        return url in self.list_repo_urls(only_active)

    def get_repo_doc(self, repo_name: str) -> xml._ElementTree:
        repo = self.get_repo(repo_name)

        index_path = repo.indexuri.get_uri()

        # FIXME Local index files should also be cached.
        if File.is_compressed(index_path) or repo.indexuri.is_remote_file():
            index = os.path.basename(index_path)
            index_path = pisi.util.join_path(ctx.config.index_dir(), repo_name, index)

            if File.is_compressed(index_path):
                index_path = os.path.splitext(index_path)[0]

        if not os.path.exists(index_path):
            ctx.ui.warning(_("%s repository needs to be updated") % repo_name)
            return xml.ElementTree(xml.Element("PISI"))

        try:
            return xml.parse(index_path)
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

            for r in repo_doc.iterfind("Repo"):
                name = r.findtext("Name")
                old_url = r.findtext("Url")
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

    def remove_repo(self, name: str):
        pisi.util.clean_dir(os.path.join(ctx.config.index_dir(), name))
        self.repoorder.remove(name)

    def get_source_repos(self, only_active=True) -> list[str]:
        """Returns a list of repo names that provide source packages."""
        repos = []
        for r in self.list_repos(only_active):
            if self.get_repo_doc(r).find("SpecFile") is not None:
                repos.append(r)
        return repos

    def get_binary_repos(self, only_active=True) -> list[str]:
        """Returns a list of repo names that provide binary packages."""
        repos = []
        for r in self.list_repos(only_active):
            if self.get_repo_doc(r).find("SpecFile") is None:
                repos.append(r)
        return repos

    def list_repos(self, only_active=True) -> list[str]:
        """Returns a list of repo names."""
        return [
            x
            for x in self.repoorder.get_order()
            if (True if not only_active else self.repo_active(x))
        ]

    def list_repo_urls(self, only_active=True) -> list[str]:
        repos = []
        for r in self.list_repos(only_active):
            u = self.get_repo_url(r)
            if u is not None:
                repos.append(u)
        return repos

    def get_repo_by_url(self, url: str) -> str | None:
        if not self.has_repo_url(url):
            return None
        for r in self.list_repos(only_active=False):
            if self.get_repo_url(r) == url:
                return r
        return None

    def activate_repo(self, name: str):
        self.repoorder.set_status(name, "active")

    def deactivate_repo(self, name: str):
        self.repoorder.set_status(name, "inactive")

    def repo_active(self, name: str) -> bool:
        return self.repoorder.get_status(name) == "active"

    def get_distribution(self, name: str) -> str | None:
        doc = self.get_repo_doc(name)
        distro = doc.find("Distribution")
        if distro is None:
            return None
        return distro.findtext("SourceName") or None

    def get_distribution_release(self, name: str) -> str | None:
        doc = self.get_repo_doc(name)
        distro = doc.find("Distribution")
        if distro is None:
            return None
        return distro.findtext("Version") or None

    def check_distribution(self, name: str):
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
