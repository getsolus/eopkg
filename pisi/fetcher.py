# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project, 2026 Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

import os
import time
from concurrent.futures import ThreadPoolExecutor

import requests
from requests import HTTPError
from requests.adapters import HTTPAdapter
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TaskID,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

import pisi
import pisi.context as ctx
from pisi import translate as _
from pisi.uri import URI
from pisi.util import human_readable_rate

"""Maximum size in bytes of a download chunk to process at a time."""
MAX_CHUNK_SIZE = 8192


class Fetcher:
    """Handles an HTTP session for making one or more download requests.

    It supports automatic retries (http/https only), bandwidth limits,
    and network proxies. Values for these settings are read from the
    global config via the Pisi context. This may change in the future.

    Attributes:
        bandwidth_limit (int): The speed in bits per second that shall
            not be exceeded during downloads. Set to 0 for no limit.
        max_retries (int): The maximum number of times that a download
            can be retried before giving up. Default 5
        session (requests.Session): The HTTP session.
    """

    def __init__(self):
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
        url: str,
        destination: str,
        progress: Progress | None = None,
        task_id: TaskID | None = None,
    ) -> None:
        """
        Download a remote resource to a local file.

        :param str url: The URL of the resource to download.
        :param str destination: The destination file to download to.
        :param Progress progress: The rich Progress object to use.
        :param TaskID task_id: The rich TaskID to use.
        """
        with self.session.get(url.get_uri(), stream=True, timeout=15) as resp:
            resp.raise_for_status()
            start_time = time.time()

            total = int(resp.headers.get("Content-Length") or 0)

            if progress is not None and task_id is not None:
                progress.update(task_id, total=total)
                progress.start_task(task_id)
                self._download_to_file(resp, destination, start_time, progress, task_id)
            else:
                with Progress(
                    TextColumn("[bold blue]{task.description}", justify="right"),
                    BarColumn(bar_width=None),
                    "[progress.percentage]{task.percentage:>3.1f}%",
                    "•",
                    DownloadColumn(),
                    "•",
                    TransferSpeedColumn(),
                    "•",
                    TimeRemainingColumn(),
                ) as p:
                    tid = p.add_task(os.path.basename(destination), total=total)
                    self._download_to_file(resp, destination, start_time, p, tid)

    def _download_to_file(
        self,
        resp: requests.Response,
        destination: str,
        start_time: float,
        progress: Progress,
        task_id: TaskID,
    ) -> None:
        with open(destination, "wb") as f:
            for chunk in resp.iter_content(chunk_size=MAX_CHUNK_SIZE):
                if not chunk:
                    break

                size = f.write(chunk)
                progress.update(task_id, advance=size)

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

    def fetch(
        self,
        url: URI | str,
        dest_dir: str,
        filename: str | None = None,
        progress: Progress | None = None,
        task_id: TaskID | None = None,
    ) -> None:
        """
        Fetches a remote resource.

        :param url: The file to fetch.
        :type url: pisi.uri.URI | str
        :param str dest_dir: The directory to save the downloaded file to.
        :param filename: The name of the file to use.
        :type filename: str | None
        :param Progress progress: The rich Progress object to use.
        :param TaskID task_id: The rich TaskID to use.
        """
        # This is silly and I hate it.
        if type(url) is str:
            url = URI(url)

        if not url.filename():
            raise ValueError(_("URL does not end in a file name"))

        if not os.access(dest_dir, os.W_OK):
            raise IOError(_(f"Unable to access destination directory '{dest_dir}'"))

        archive_file = os.path.join(dest_dir, filename or url.filename())

        if os.path.exists(archive_file) and not os.access(archive_file, os.W_OK):
            raise IOError(_(f"Unable to access destination file '{archive_file}'"))

        try:
            self.download_file(url, archive_file, progress, task_id)
        except HTTPError:
            raise

    def fetch_multi(self, items: list) -> None:
        """
        Fetches multiple remote resources concurrently.

        :param items: A list of (url, dest_dir, filename) tuples.
        """

        # TODO(Joey): Add a seperate config value for this
        max_workers = pisi.util.parse_jobs(ctx.config.values.build.jobs)
        if max_workers == 0:
            max_workers = 8
        # Cap the number of concurrent downloads to 8 to avoid overloading
        if max_workers > 8:
            max_workers = 8

        with Progress(
            TextColumn("[bold blue]{task.description}", justify="right"),
            BarColumn(bar_width=None),
            "[progress.percentage]{task.percentage:>3.1f}%",
            "•",
            DownloadColumn(),
            "•",
            TransferSpeedColumn(),
            "•",
            TimeRemainingColumn(),
        ) as progress:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = []

                for i, item in enumerate(items):
                    url, dest_dir, *rest = item
                    filename = rest[0] if rest else None

                    # This is silly and I hate it.
                    if type(url) is str:
                        u = URI(url)
                    else:
                        u = url

                    task_id = progress.add_task(
                        filename or u.filename(), total=None, start=False
                    )

                    futures.append(
                        executor.submit(
                            self.fetch, url, dest_dir, filename, progress, task_id
                        )
                    )

                for future in futures:
                    try:
                        future.result()
                    except Exception as e:
                        ctx.ui.error(str(e))
                        raise

    def _get_bandwidth_limit(self) -> int:
        bandwidth_limit = (
            ctx.config.options.bandwidth_limit
            or ctx.config.values.general.bandwidth_limit
        )

        if bandwidth_limit and bandwidth_limit != "0":
            # The limit is in KB
            bandwidth_limit = int(bandwidth_limit) * 1000
            parts = human_readable_rate(bandwidth_limit)
            rate = f"{parts[0]} {parts[1]}"
            ctx.ui.warning(_(f"Bandwidth usage is limited to {rate}"))
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

        if ctx.config.values.general.http_proxy and self.url.scheme() == "http":
            proxies["http"] = ctx.config.values.general.http_proxy

        if ctx.config.values.general.https_proxy and self.url.scheme() == "https":
            proxies["https"] = ctx.config.values.general.https_proxy

        if ctx.config.values.general.ftp_proxy and self.url.scheme() == "ftp":
            proxies["ftp"] = ctx.config.values.general.ftp_proxy

        return proxies
