# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later
# generic user interface

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager

from pisi.events import Operation

(
    installed,
    upgraded,
    removed,
    installing,
    removing,
    configuring,
    configured,
    extracting,
    downloading,
    packagestogo,
    updatingrepo,
    upgrading,
    cached,
    desktopfile,
    systemconf,
) = list(range(15))


class PhaseHandle:
    """Handle for a phase of work.

    Frontends override `UI.work_phase()` to return a subclass
    that renders progress appropriately (Rich bars for the CLI,
    `status`/`item_progress` calls for PackageKit).

    All events are typed: the operation is the phase's
    `pisi.events.Operation`, and `pkg_info` is a `pisi.events.PkgInfo`.
    """

    def add_item(self, item_name: str, total: int, *, pkg_info=None):
        """A new item has started in this phase.

        :param item_name: Name of the item (e.g. package name, filename).
        :param total: Total units of work for this item (files, bytes, …).
        :param pkg_info: Optional :class:`~pisi.events.PkgInfo` with package metadata.
        """
        pass

    def update_item(self, item_name: str, completed: int):
        """Progress update for an item.

        :param item_name: Name of the item.
        :param completed: Units completed so far.
        """
        pass

    def finish_item(self, item_name: str):
        """An item has completed.

        :param item_name: Name of the item.
        """
        pass


class _NullPhaseHandle(PhaseHandle):
    """No-op handle — default when no frontend overrides `work_phase`."""
    pass


class UI:
    "Abstract class for UI operations, derive from this."

    class Progress:
        def __init__(self, totalsize, existsize=0):
            self.totalsize = totalsize
            try:
                self.percent = (existsize * 100) / totalsize
            except ArithmeticError:
                self.percent = 0

        def update(self, size):
            if not self.totalsize:
                return 100
            try:
                self.percent = (size * 100) / self.totalsize
            except ArithmeticError:
                self.percent = 0
            return self.percent

    def __init__(self, debuggy=False, verbose=False):
        self.show_debug = debuggy
        self.show_verbose = verbose
        self.errors = 0
        self.warnings = 0

    def close(self):
        "cleanup stuff here"
        pass

    def set_verbose(self, flag):
        self.show_verbose = flag

    def set_debug(self, flag):
        self.show_debug = flag

    def info(self, msg, verbose=False, noln=False):
        "give an informative message"
        pass

    def ack(self, msg):
        "inform the user of an important event and wait for acknowledgement"
        pass

    def debug(self, msg):
        "show debugging info"
        if self.show_debug:
            self.info("DEBUG: " + msg)

    def warning(self, msg):
        "warn the user"
        pass

    def error(self, msg):
        "inform a (possibly fatal) error"
        pass

    # FIXME: merge this with info, this just means "important message"
    def action(self, msg):
        "uh?"
        pass

    def choose(self, msg, list):
        "ask the user to choose from a list of alternatives"
        pass

    def confirm(self, msg):
        "ask a yes/no question"
        # default ui confirms everything
        return True

    def status(self, msg=None):
        "set status, if not given clear it"
        pass

    def display_progress(self, **ka):
        "display progress"
        pass

    def notify(self, event, **keywords):
        "notify UI of a significant event"
        pass

    def run_usysconf(self, command: str) -> None:
        """Run the system configuration binary (usysconf).

        Frontends override this to control how the binary's output is
        handled: the CLI lets it stream to the terminal, while
        PackageKit suppresses it (its stdout is parsed by packagekitd).

        :param command: Full shell command line for usysconf.
        """
        os.system(command)

    @contextmanager
    def work_phase(
        self, num_items: int, op: Operation, *, total_units: int | None = None
    ) -> Iterator[PhaseHandle]:
        """Context manager wrapping a phase of work (parallel or sequential).

        Frontends override this to display progress (e.g. Rich progress
        bars for the CLI, or `status`/`item_progress` callbacks for
        PackageKit).

        The yielded :class:`PhaseHandle` receives:
          - `add_item(name, total, *, pkg_info=None)`
          - `update_item(name, completed)`
          - `finish_item(name)`

        :param num_items: Total number of items in this phase.
        :param op: The :class:`~pisi.events.Operation` for the phase;
                   drives the overall label and frontend behaviour.
        :param total_units: Optional definitive aggregate unit count for
            the overall progress (bytes for downloads, files for
            operations). When None, frontends accumulate per-item totals
            as items are added, so the overall fraction may shift as new
            items register.
        """
        yield _NullPhaseHandle()
