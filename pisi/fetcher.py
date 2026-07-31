# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project, 2026 Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

from __future__ import annotations

import os
import signal
import time
from concurrent.futures import ThreadPoolExecutor

import requests
from requests import RequestException
from requests.adapters import HTTPAdapter

import pisi
import pisi.context as ctx
import pisi.ui
from pisi import translate as _
from pisi import util
from pisi.events import Operation, PkgInfo
from pisi.package import PackageResource
from pisi.uri import URI

"""Maximum size in bytes of a download chunk to process at a time."""
MAX_CHUNK_SIZE = 8192


class FetchError(pisi.Error):
    """Raised when a fetch operation fails."""


class SingleFetchHandle(pisi.ui.PhaseHandle):
    """Phase handle for single-file downloads."""

    def __init__(self, url):
        self._action = "Copied" if url.is_local_file() else "Downloaded"
        self._name = None
        self._total = 0

    def add_item(self, item_name, total, *, op=None, pkg_info=None):
        self._name = item_name
        self._total = total

    def update_item(self, item_name, completed):
        if not self._total:
            return
        pct = int(completed * 100 / self._total)
        print(
            f"\r{util.colorize(f'{pct}%', 'yellow')} {item_name}",
            end="",
            flush=True,
        )

    def finish_item(self, item_name, *, version=None):
        print(
            f"\r{util.colorize(self._action, 'green')} {item_name}",
            flush=True,
        )


class Fetcher:
    """Handles an HTTP session for making one or more download requests.

    It supports automatic retries (http/https only), bandwidth limits,
    and network proxies. Values for these settings are read from the
    global config via the Pisi context. This may change in the future.

    Attributes:
        bandwidth_limit (int): The speed in bits per second that shall
            not be exceeded during downloads. Set to 0 for no limit.
        max_retries (int): The maximum number of times that a download
            will be retried. Defaults to 5.
        session (requests.Session): The session used for HTTP requests.
        fetch_ui: A progress helper provided by the active UI frontend.
    """

    def __init__(self):
        self.fetch_ui = None
        self.bandwidth_limit = self._get_bandwidth_limit()
        self.max_retries = self._get_max_retries()

        self.session = requests.Session()

        self.session.mount("http://", HTTPAdapter(max_retries=self.max_retries))
        self.session.mount("https://", HTTPAdapter(max_retries=self.max_retries))
        self.session.headers.update({"User-Agent": f"eopkg Fetcher/{pisi.__version__}"})

        proxies = self._get_proxies()
        self.session.proxies.update(proxies)

    def download_file(
        self,
        url: URI,
        destination: str,
        description: str | None = None,
        pkg_info: PkgInfo | None = None,
    ) -> None:
        """
        Download a remote resource to a local file.

        :param URI url: The URI of the resource to download.
        :param str destination: The destination file to download to.
        :param str description: The description for the task.
        :param PkgInfo pkg_info: Package metadata for progress events.
        """
        basename = os.path.basename(destination)
        item_name = description or basename

        fetch_ui = self.fetch_ui
        ctx.sig.catch_signal(signal.SIGINT)
        try:
            if url.is_local_file():
                source = url.path()
                rooted_path = util.join_path(ctx.config.dest_dir(), source)
                if os.path.exists(rooted_path):
                    source = rooted_path
                else:
                    raise OSError(_("Source file '%s' does not exist") % source)

                total = os.path.getsize(source)

                fetch_ui.add_item(item_name, total, op=Operation.DOWNLOAD, pkg_info=pkg_info)
                try:
                    self._copy_to_file(
                        source,
                        destination,
                        fetch_ui,
                        item_name,
                        basename,
                    )
                finally:
                    fetch_ui.finish_item(item_name)
                return

            with self.session.get(url.get_uri(), stream=True, timeout=15) as resp:
                resp.raise_for_status()
                start_time = time.time()

                total = int(resp.headers.get("Content-Length") or 0)
                fetch_ui.add_item(item_name, total, op=Operation.DOWNLOAD, pkg_info=pkg_info)
                try:
                    self._download_to_file(
                        resp,
                        destination,
                        start_time,
                        fetch_ui,
                        item_name,
                        basename,
                    )
                finally:
                    fetch_ui.finish_item(item_name)
        finally:
            ctx.sig.enable_signal(signal.SIGINT)

        ctx.sig.check_signals()

    def _copy_to_file(
        self,
        source: str,
        destination: str,
        fetch_ui,
        item_name: str,
        filename: str,
    ) -> None:
        size = os.path.getsize(source)

        # Try hardlinking first
        try:
            if os.path.exists(destination):
                os.unlink(destination)
            os.link(source, destination)
            fetch_ui.update_item(item_name, size)
            return
        except OSError:
            # Fallback to manual copy with progress
            pass

        with open(source, "rb") as src, open(destination, "wb") as dst:
            copied = 0
            while True:
                chunk = src.read(MAX_CHUNK_SIZE)
                if not chunk:
                    break
                dst.write(chunk)
                size = len(chunk)
                copied += size
                fetch_ui.update_item(item_name, copied)

    def _download_to_file(
        self,
        resp: requests.Response,
        destination: str,
        start_time: float,
        fetch_ui,
        item_name: str,
        filename: str,
    ) -> None:
        downloaded = 0

        with open(destination, "wb") as f:
            for chunk in resp.iter_content(chunk_size=MAX_CHUNK_SIZE):
                if not chunk:
                    break

                size = f.write(chunk)
                downloaded += size
                fetch_ui.update_item(item_name, downloaded)

                # Handle bandwidth limiting, if set
                if self.bandwidth_limit:
                    elapsed = time.time() - start_time
                    # Calculate the time this chunk "should" take to stay
                    # under the limit
                    expected_time = MAX_CHUNK_SIZE / self.bandwidth_limit

                    # Sleep the difference
                    if elapsed < expected_time:
                        time.sleep(expected_time - elapsed)

                    start_time = time.time()

                # Handle SIGINT in ThreadPoolExecutor context
                if ctx.sig.done_event.is_set():
                    return

    def fetch(
        self,
        url: URI | str,
        dest_dir: str,
        filename: str | None = None,
        description: str | None = None,
        pkg_info: PkgInfo | None = None,
    ) -> None:
        """
        Fetches a remote resource.

        :param url: The file to fetch.
        :type url: pisi.uri.URI | str
        :param str dest_dir: The directory to save the downloaded file to.
        :param filename: The filename to use.
        :type filename: str | None
        :param str description: The description for the task.
        :param PkgInfo pkg_info: Package metadata for progress events.
        """
        # This is silly and I hate it.
        if type(url) is str:
            url = URI(url)

        if not url.filename():
            raise ValueError(_("URL does not end in a file name"))

        if not os.access(dest_dir, os.W_OK):
            raise OSError(_("Unable to access destination directory '%s'") % dest_dir)

        archive_file = os.path.join(dest_dir, filename or url.filename())

        if os.path.exists(archive_file) and not os.access(archive_file, os.W_OK):
            raise OSError(_("Unable to access destination file '%s'") % archive_file)

        # Single-file fetch: display inline CLI progress (no Live display).
        # Multi-file fetch (fetch_multi) wraps in ctx.ui.work_phase
        # which provides the full Rich Live display.
        #
        # Only create a handle (and clean it up afterwards) when called
        # standalone: in fetch_multi, self.fetch_ui is the shared phase
        # handle for ALL concurrent downloads, so the first thread to
        # finish must not null it out from under the others.
        single = self.fetch_ui is None
        if single:
            self.fetch_ui = SingleFetchHandle(url)
        try:
            self.download_file(url, archive_file, description, pkg_info)
        except RequestException as e:
            raise FetchError(
                _("Error downloading '%s': %s") % (url.filename(), e)
            ) from e
        finally:
            if single:
                self.fetch_ui = None

    def fetch_multi(self, items: list[PackageResource]) -> None:
        """
        Fetches multiple remote resources concurrently.

        :param items: A list of PackageResource objects.
        """

        max_workers = int(
            ctx.config.options.download_workers
            or ctx.config.values.general.download_workers
        )
        # Ensure we've got something reasonable to work with
        max_workers = max(1, min(max_workers, 64))
        ctx.ui.debug(_("Setting %s concurrent download workers") % max_workers)

        # Overall byte total from index metadata (when complete) so the
        # global bar never shifts as concurrent downloads register.
        known_sizes = [item.size for item in items if item.size is not None]
        total_units = sum(known_sizes) if len(known_sizes) == len(items) else None

        with ctx.ui.work_phase(len(items), Operation.DOWNLOAD, total_units=total_units) as phase:
            self.fetch_ui = phase
            ctx.sig.catch_signal(signal.SIGINT)
            try:
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = []

                    for resource in items:
                        _name, version = util.parse_package_name(resource.pkg_path)
                        description = f"({resource.repo}) {resource.name} {version}"
                        if resource.is_delta:
                            description += " [delta]"

                        pkg_info = PkgInfo(name=resource.name)

                        futures.append(
                            executor.submit(
                                self.fetch,
                                resource.uri,
                                os.path.dirname(resource.local_path),
                                os.path.basename(resource.local_path),
                                description,
                                pkg_info,
                            )
                        )

                    any_errors = False
                    for future in futures:
                        try:
                            future.result()
                        except Exception as e:
                            ctx.ui.error(str(e))
                            any_errors = True

                    if any_errors:
                        raise pisi.Error(
                            _("One or more errors occurred during fetching")
                        )
            finally:
                ctx.sig.enable_signal(signal.SIGINT)
                self.fetch_ui = None

        ctx.sig.check_signals()

    def _get_bandwidth_limit(self) -> int:
        bandwidth_limit = (
            ctx.config.options.bandwidth_limit
            or ctx.config.values.general.bandwidth_limit
        )

        if bandwidth_limit and bandwidth_limit != "0":
            # The limit is in KB
            bandwidth_limit = int(bandwidth_limit) * 1000
            parts = util.human_readable_rate(bandwidth_limit)
            rate = f"{parts[0]} {parts[1]}"
            ctx.ui.warning(_("Bandwidth usage is limited to %s") % rate)
            return bandwidth_limit
        else:
            return 0

    def _get_max_retries(self) -> int:
        retry_attempts = (
            ctx.config.options.retry_attempts
            or ctx.config.values.general.retry_attempts
        )

        if retry_attempts and retry_attempts != "5":
            return int(retry_attempts)
        else:
            return 5

    def _get_proxies(self) -> dict:
        proxies = {}
        if ctx.config.values.general.http_proxy:
            proxies["http"] = ctx.config.values.general.http_proxy

        if ctx.config.values.general.https_proxy:
            proxies["https"] = ctx.config.values.general.https_proxy

        return proxies
