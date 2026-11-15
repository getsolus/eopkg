# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

import locale
import re
import sys
import tty
from contextlib import contextmanager

import pisi
import pisi.ui
import pisi.util
from pisi import context as ctx
from pisi import events
from pisi import translate as _


class Error(pisi.Error):
    pass


class Exception(pisi.Exception):
    pass


def printu(obj, err=False):
    if not isinstance(obj, str):
        obj = str(obj)
    if err:
        out = sys.stderr
    else:
        out = sys.stdout
    out.write(obj)
    out.flush()


class CLI(pisi.ui.UI):
    "Command Line Interface"

    def __init__(self, show_debug=False, show_verbose=False):
        super(CLI, self).__init__(show_debug, show_verbose)
        self.warnings = 0
        self.errors = 0

    def close(self):
        pisi.util.xterm_title_reset()

    def output(self, msg, err=False, verbose=False):
        if (verbose and self.show_verbose) or (not verbose):
            if isinstance(msg, bytes):
                msg = msg.decode("utf-8")
            if err:
                out = sys.stderr
            else:
                out = sys.stdout
            out.write(msg)
            out.flush()

    def formatted_output(self, msg, verbose=False, noln=False, column=":"):
        key_width = 20
        line_format = "%(key)-20s%(column)s%(rest)s"
        term_height, term_width = pisi.util.get_terminal_size()

        def find_whitespace(s, i):
            while s[i] not in (" ", "\t"):
                i -= 1
            return i

        def align(s):
            align_width = term_width - key_width - 2
            s_width = len(s)
            new_s = ""
            index = 0
            while True:
                next_index = index + align_width
                if next_index >= s_width:
                    new_s += s[index:]
                    break
                next_index = find_whitespace(s, next_index)
                new_s += s[index:next_index]
                index = next_index
                if index < s_width:
                    new_s += "\n" + " " * (key_width + 1)
            return new_s

        new_msg = ""
        for line in msg.split("\n"):
            key, _column, rest = line.partition(column)
            rest = align(rest)
            new_msg += line_format % {"key": key, "column": _column, "rest": rest}
            if not noln:
                new_msg = "%s\n" % new_msg
        msg = new_msg
        self.output(str(msg), verbose=verbose)

    def info(self, msg, verbose=False, noln=False):
        # TODO: need to look at more kinds of info messages
        # let's cheat from KDE :)
        if not noln:
            msg = "%s\n" % msg
        self.output(str(msg), verbose=verbose)

    def warning(self, msg, verbose=False):
        msg = str(msg)
        self.warnings += 1
        if ctx.log:
            ctx.log.warning(msg)
        if ctx.get_option("no_color"):
            self.output(_("Warning: ") + msg + "\n", err=True, verbose=verbose)
        else:
            self.output(
                pisi.util.colorize(msg + "\n", "brightyellow"),
                err=True,
                verbose=verbose,
            )

    def error(self, msg):
        msg = str(msg)
        self.errors += 1
        if ctx.log:
            ctx.log.error(msg)
        if ctx.get_option("no_color"):
            self.output(_("Error: ") + msg + "\n", err=True)
        else:
            self.output(pisi.util.colorize(msg + "\n", "brightred"), err=True)

    def action(self, msg, verbose=False):
        # TODO: this seems quite redundant?
        msg = str(msg)
        if ctx.log:
            ctx.log.info(msg)
        self.output(pisi.util.colorize(msg + "\n", "green"))

    def choose(self, msg, opts):
        msg = str(msg)
        prompt = msg + pisi.util.colorize(" (%s)" % "/".join(opts), "red")
        while True:
            s = input(prompt)
            for opt in opts:
                if opt.startswith(str(s)):
                    return opt

    def confirm(self, msg: str):
        if ctx.config.options and ctx.config.options.yes_all:
            return True

        yes_expr = re.compile(locale.nl_langinfo(locale.YESEXPR))
        no_expr = re.compile(locale.nl_langinfo(locale.NOEXPR))

        while True:
            tty.tcflush(sys.stdin.fileno(), 0)
            prompt = msg + pisi.util.colorize(_(" (yes/no)"), "red")
            s = input(prompt)

            if yes_expr.search(s):
                return True

            if no_expr.search(s):
                return False

    def status(self, msg=None):
        if msg:
            msg = str(msg)
            self.output(pisi.util.colorize(msg + "\n", "brightgreen"))
            pisi.util.xterm_title(msg)

    @contextmanager
    def work_phase(self, num_items, op, *, total_units=None):
        """Context manager wrapping a phase of work (parallel or sequential).

        Displays live Rich progress bars (per-item + overall)
        during install, upgrade, remove, or fetch operations.

        :param num_items: Total number of items in this phase.
        :param op: The :class:`~pisi.events.Operation` for the phase; drives
                   the overall label and frontend behaviour.
        :param total_units: Optional definitive unit total (bytes for
            downloads, files for operations) for the overall bar; when
            given, the bar never shifts as further items register.
        """
        from rich.console import Group
        from rich.live import Live
        from rich.progress import (
            BarColumn,
            DownloadColumn,
            Progress,
            ProgressColumn,
            TaskProgressColumn,
            TextColumn,
            TimeRemainingColumn,
            TransferSpeedColumn,
        )
        from rich.rule import Rule
        from rich.style import Style
        from rich.table import Column
        from rich.text import Text

        label = op.label
        is_download = op == events.Operation.DOWNLOAD

        item_columns = [
            TaskProgressColumn(
                text_format="{task.percentage:>3.0f}%",
                style=Style(color="yellow"),
            ),
            TextColumn("[bold blue]{task.description}"),
        ]
        if is_download:
            item_columns += [
                TextColumn("", table_column=Column(ratio=1)),
                DownloadColumn(),
                "\u2022",
                TransferSpeedColumn(),
                "\u2022",
                TimeRemainingColumn(),
            ]
        item_progress = Progress(*item_columns, expand=is_download)

        overall_columns = [
            TextColumn(f"[bold green]{label}", justify="right"),
            BarColumn(complete_style="green", bar_width=None),
            TaskProgressColumn(),
            "\u2022",
        ]
        if is_download:
            overall_columns += [
                DownloadColumn(),
                "\u2022",
                TransferSpeedColumn(),
                "\u2022",
                TimeRemainingColumn(),
            ]
        else:
            # The bar/percentage columns above are computed from per-item
            # units (files), but the trailing text shows the package count
            # as before — a counter tracked separately by the phase handle.
            class PackageCountColumn(ProgressColumn):
                def __init__(self, total):
                    super().__init__()
                    self.total = total
                    self.done = 0

                def mark_done(self):
                    self.done += 1

                def render(self, task):
                    return Text(f"{self.done}/{self.total} packages")

            package_count_column = PackageCountColumn(num_items)
            overall_columns += [package_count_column]
        overall_progress = Progress(*overall_columns)

        # The overall task's total is fixed when the caller knows it
        # upfront so the bar never shifts as further items register;
        # otherwise it starts from the package count (operations) or
        # indeterminate (downloads) and grows as items report their
        # unit counts.
        if total_units is not None:
            overall_total = total_units
        elif is_download:
            overall_total = None
        else:
            overall_total = num_items
        overall_task = overall_progress.add_task("Overall", total=overall_total)

        handle = RichPhaseHandle(
            item_progress,
            overall_progress,
            overall_task,
            op,
            package_count=None if is_download else package_count_column,
            total_units=total_units,
        )

        with Live(
            Group(item_progress, Rule(style="dim"), overall_progress),
            refresh_per_second=10,
        ):
            yield handle


class RichPhaseHandle(pisi.ui.PhaseHandle):
    """Phase handle that renders live Rich progress bars.

    The overall bar aggregates per-item progress in a unit-neutral way:
    units are bytes for download phases and files for install/upgrade/
    remove phases (per-item totals from the typed events), so the global
    bar advances smoothly as items progress concurrently.
    """

    def __init__(
        self, item_progress, overall_progress, overall_task, op, *,
        package_count=None, total_units=None,
    ):
        self.item_progress = item_progress
        self.overall_progress = overall_progress
        self.overall_task = overall_task
        self.op = op
        self.label = op.label if op is not None else ""
        self.package_count = package_count
        self._fixed_total = total_units
        self.tasks = {}
        self._pkg_infos = {}
        self._item_totals = {} # e.g. n files/bytes p/item
        self._item_done = {}  # e.g. completed files/bytes p/item
        self._units_total = 0  # Sigma (Σ) per-item totals
        self._units_done = 0  # Sigma (Σ) per-item completed

    @staticmethod
    def _display_version(pkg_info):
        if pkg_info is None or not pkg_info.version:
            return ""
        if pkg_info.release:
            return f"{pkg_info.version}-{pkg_info.release}"
        return pkg_info.version

    def add_item(self, item_name, total, *, pkg_info=None):
        if item_name not in self.tasks:
            self._pkg_infos[item_name] = pkg_info
            desc = f"{self.label} {item_name}"
            version = self._display_version(pkg_info)
            if version:
                desc += f" {version}"
            self.tasks[item_name] = self.item_progress.add_task(desc, total=total)
            self._item_totals[item_name] = total
            self._units_total += total
            if self._fixed_total is None:
                self.overall_progress.update(self.overall_task, total=self._units_total)

    def update_item(self, item_name, completed):
        task_id = self.tasks.get(item_name)
        if task_id is not None:
            self.item_progress.update(task_id, completed=completed)
        # Advance the overall bar by the delta: items may report
        # concurrently, so credit each item's units as they arrive.
        delta = completed - self._item_done.get(item_name, 0)
        self._item_done[item_name] = completed
        self._units_done += delta
        self.overall_progress.update(self.overall_task, completed=self._units_done)

    def finish_item(self, item_name):
        task_id = self.tasks.pop(item_name, None)
        if task_id is not None:
            self.item_progress.remove_task(task_id)
        if self.package_count is not None:
            self.package_count.mark_done()
        # Credit any units that never went through update_item (e.g.
        # hardlinked copies or progress-less phases) so the bar reaches 100%.
        remaining = max(
            0, self._item_totals.get(item_name, 0) - self._item_done.get(item_name, 0)
        )
        self._units_done += remaining
        self.overall_progress.update(self.overall_task, completed=self._units_done)
        done_label = self.op.done_label if self.op is not None else self.label
        version = self._display_version(self._pkg_infos.pop(item_name, None))
        if version:
            line = (_("[green]%s[reset] %s %s") % (done_label, item_name, version))
        else:
            line = (_("[green]%s[reset] %s") % (done_label, item_name))
        self.overall_progress.console.print(line, highlight=False)
