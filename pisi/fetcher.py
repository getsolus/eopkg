# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project, 2026 Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

import os
import signal
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import requests
from requests import HTTPError
from requests.adapters import HTTPAdapter
from rich.console import Group
from rich.live import Live
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TaskID,
    TaskProgressColumn,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from rich.rule import Rule
from rich.style import Style
from rich.table import Column

import pisi
import pisi.context as ctx
import pisi.ui
from pisi import translate as _
from pisi.package import PackageResource
from pisi.uri import URI
from pisi.util import human_readable_rate, parse_package_name

"""Maximum size in bytes of a download chunk to process at a time."""
MAX_CHUNK_SIZE = 8192

"""Minimum interval in seconds between UI progress callbacks."""
PROGRESS_UPDATE_INTERVAL = 0.1


class FetchError(pisi.Error):
    """Raised when a fetch operation fails."""

    pass


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

        self.progress = Progress(
            TaskProgressColumn(
                text_format="{task.percentage:>3.0f}%",
                style=Style(color="yellow"),
            ),
            TextColumn("[bold blue]{task.description}"),
            TextColumn(
                "", table_column=Column(ratio=1)
            ),  # spacer, requires expand = True
            DownloadColumn(),
            "•",
            TransferSpeedColumn(),
            "•",
            TimeRemainingColumn(),
            expand=True,
        )

        self.overall_progress = Progress(
            TextColumn("[bold green]Downloading", justify="right"),
            BarColumn(
                complete_style="green",
                bar_width=None,
            ),
            TaskProgressColumn(),
            "•",
            DownloadColumn(),
            "•",
            TransferSpeedColumn(),
            "•",
            TimeRemainingColumn(),
        )
        self.overall_task = None

        # Overall progress tracking for fetching_overall callbacks
        self._overall_lock = threading.Lock()
        self._overall_completed = 0
        self._overall_total = 0
        self._last_overall_report = 0.0

        self.live = Live(
            Group(
                self.progress,
                Rule(style="dim"),
                self.overall_progress,
            ),
            refresh_per_second=10,
        )

    def download_file(
        self,
        url: URI,
        destination: str,
        description: str | None = None,
    ) -> None:
        """
        Download a remote resource to a local file.

        :param URI url: The URI of the resource to download.
        :param str destination: The destination file to download to.
        :param str description: The description for the task.
        """
        basename = os.path.basename(destination)
        ctx.sig.catch_signal(signal.SIGINT)
        try:
            if url.is_local_file():
                source = url.path()
                rooted_path = pisi.util.join_path(ctx.config.dest_dir(), source)
                if os.path.exists(rooted_path):
                    source = rooted_path
                else:
                    raise IOError(_(f"Source file '{source}' does not exist"))

                total = os.path.getsize(source)

                task_id = self.progress.add_task(
                    description or basename,
                    total=total,
                )
                try:
                    self._copy_to_file(
                        source,
                        destination,
                        task_id,
                        basename,
                    )
                finally:
                    self.progress.remove_task(task_id)
                    self.progress.console.print(
                        _(f"[green]Copied[reset] {basename}"),
                        highlight=False,
                    )
                return

            with self.session.get(url.get_uri(), stream=True, timeout=15) as resp:
                resp.raise_for_status()
                start_time = time.time()

                total = int(resp.headers.get("Content-Length") or 0)
                task_id = self.progress.add_task(
                    description or basename,
                    total=total,
                )
                try:
                    self._download_to_file(
                        resp,
                        destination,
                        start_time,
                        task_id,
                        basename,
                    )
                finally:
                    self.progress.remove_task(task_id)
                    self.progress.console.print(
                        _(f"[green]Downloaded[reset] {basename}"),
                        highlight=False,
                    )
        finally:
            ctx.sig.enable_signal(signal.SIGINT)

        ctx.sig.check_signals()

    def _report_progress(
        self,
        filename: str,
        downloaded: int,
        total: int,
        last_report_time: list[float],
    ) -> float:
        """Report download progress to the UI callback system.

        Calls ctx.ui.display_progress with progress info, throttled
        to at most one call per PROGRESS_UPDATE_INTERVAL seconds.

        :param filename: The name of the file being downloaded.
        :param downloaded: Bytes downloaded so far.
        :param total: Total bytes to download.
        :param last_report_time: Mutable single-element list holding
            the timestamp of the last report ([time]).
        :returns: The current timestamp.
        """
        now = time.time()
        if now - last_report_time[0] < PROGRESS_UPDATE_INTERVAL and downloaded < total:
            return now

        last_report_time[0] = now

        percent = (downloaded * 100.0 / total) if total else 0.0
        ctx.ui.display_progress(
            operation="fetching",
            percent=percent,
            filename=filename,
            total_size=total,
            downloaded_size=downloaded,
        )
        return now

    def _report_overall_progress(self) -> None:
        """Report overall download progress to the UI callback system.

        Emits display_progress(operation="fetching_overall", …) based on
        the total bytes completed across all concurrent downloads. Throttled
        to at most one call per PROGRESS_UPDATE_INTERVAL seconds.
        """
        now = time.time()
        if now - self._last_overall_report < PROGRESS_UPDATE_INTERVAL:
            return
        self._last_overall_report = now

        with self._overall_lock:
            percent = (
                (self._overall_completed * 100.0 / self._overall_total)
                if self._overall_total
                else 0.0
            )

        ctx.ui.display_progress(
            operation="fetching_overall",
            percent=percent,
            total_size=self._overall_total,
            downloaded_size=self._overall_completed,
        )

    def _copy_to_file(
        self,
        source: str,
        destination: str,
        task_id: TaskID,
        filename: str,
    ) -> None:
        last_report = [0.0]

        # Try hardlinking first
        try:
            if os.path.exists(destination):
                os.unlink(destination)
            os.link(source, destination)
            size = os.path.getsize(source)
            self.progress.update(task_id, completed=size)
            if self.overall_task is not None:
                self.overall_progress.update(self.overall_task, advance=size)
                with self._overall_lock:
                    self._overall_completed += size
                self._report_overall_progress()

            self._report_progress(filename, size, size, last_report)
            return
        except OSError:
            # Fallback to manual copy with progress
            pass

        with open(source, "rb") as src:
            with open(destination, "wb") as dst:
                copied = 0
                while True:
                    chunk = src.read(MAX_CHUNK_SIZE)
                    if not chunk:
                        break
                    dst.write(chunk)
                    size = len(chunk)
                    copied += size
                    self.progress.update(task_id, advance=size)
                    if self.overall_task is not None:
                        self.overall_progress.update(self.overall_task, advance=size)
                        with self._overall_lock:
                            self._overall_completed += size
                        self._report_overall_progress()

                    self._report_progress(
                        filename, copied, os.path.getsize(source), last_report
                    )

    def _download_to_file(
        self,
        resp: requests.Response,
        destination: str,
        start_time: float,
        task_id: TaskID,
        filename: str,
    ) -> None:
        last_report = [0.0]
        total = int(resp.headers.get("Content-Length") or 0)
        downloaded = 0

        with open(destination, "wb") as f:
            for chunk in resp.iter_content(chunk_size=MAX_CHUNK_SIZE):
                if not chunk:
                    break

                size = f.write(chunk)
                downloaded += size
                self.progress.update(task_id, advance=size)
                if self.overall_task is not None:
                    self.overall_progress.update(self.overall_task, advance=size)
                    with self._overall_lock:
                        self._overall_completed += size
                    self._report_overall_progress()

                self._report_progress(filename, downloaded, total, last_report)

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

        # Final progress report at 100%
        self._report_progress(filename, downloaded, total, last_report)

    def fetch(
        self,
        url: URI | str,
        dest_dir: str,
        filename: str | None = None,
        description: str | None = None,
    ) -> None:
        """
        Fetches a remote resource.

        :param url: The file to fetch.
        :type url: pisi.uri.URI | str
        :param str dest_dir: The directory to save the downloaded file to.
        :param filename: The name of the file to use.
        :type filename: str | None
        :param str description: The description for the task.
        """
        # This is silly and I hate it.
        if type(url) is str:
            url = URI(url)

        if not url.filename():
            raise ValueError(_("URL does not end in a file name"))

        if not os.access(dest_dir, os.W_OK):
            raise IOError(_(f"Unable to access destination directory '{dest_dir}'"))

        archive_file = os.path.join(dest_dir, filename or url.filename())

        # Initalize the progress bar if fetch() is called rather than fetch_multi()
        # TODO: is there a cleaner way to handle this?
        single_caller = not self.live._started

        if os.path.exists(archive_file) and not os.access(archive_file, os.W_OK):
            raise IOError(_(f"Unable to access destination file '{archive_file}'"))
        try:
            if single_caller:
                self.progress.start()
            self.download_file(
                url,
                archive_file,
                description,
            )
        except HTTPError as e:
            raise FetchError(_(f"Error downloading '{url.filename()}': {e}")) from e
        finally:
            if single_caller:
                self.progress.stop()

    def fetch_multi(self, items: list["PackageResource"]) -> None:
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
        ctx.ui.debug(_(f"Setting {max_workers} concurrent download workers"))

        total_size = sum(item.size for item in items)

        self.overall_task = self.overall_progress.add_task("Overall", total=total_size)
        with self._overall_lock:
            self._overall_completed = 0
            self._overall_total = total_size
        self._last_overall_report = 0.0

        ctx.sig.catch_signal(signal.SIGINT)
        try:
            with self.live:
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = []

                    for resource in items:
                        _name, version = parse_package_name(resource.pkg_path)
                        description = f"({resource.repo}) {resource.name} {version}"
                        if resource.is_delta:
                            description += " [delta]"

                        ctx.ui.notify(
                            pisi.ui.downloading,
                            packageresource=resource,
                        )

                        futures.append(
                            executor.submit(
                                self.fetch,
                                resource.uri,
                                os.path.dirname(resource.local_path),
                                os.path.basename(resource.local_path),
                                description,
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

                    # Update live display with a dummy group clean things up visually
                    self.live.update(Group())

        finally:
            ctx.sig.enable_signal(signal.SIGINT)

        ctx.sig.check_signals()

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
