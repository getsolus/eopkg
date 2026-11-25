# SPDX-FileCopyrightText: 2026 Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later
"""Typed vocabulary and messages for operation progress events leaf module."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from pisi import translate as _


@dataclass(frozen=True)
class EventInfo:
    """Static metadata for an operation type."""

    name: str  # canonical name
    label: str  # present participle, e.g. "Installing"
    done_label: str  # past tense, e.g. "Installed"


class Operation(Enum):
    """Known operation types.

    Access pattern::

        op = Operation.INSTALL
        op.value.name       # "install" (canonical name)
        op.label            # "Installing"
        op.done_label       # "Installed"
    """

    INSTALL = EventInfo(_("install"), _("Installing"), _("Installed"))
    REINSTALL = EventInfo(_("reinstall"), _("Reinstalling"), _("Reinstalled"))
    UPGRADE = EventInfo(_("upgrade"), _("Upgrading"), _("Upgraded"))
    DOWNGRADE = EventInfo(_("downgrade"), _("Downgrading"), _("Downgraded"))
    REMOVE = EventInfo(_("remove"), _("Removing"), _("Removed"))
    CONFIGURE = EventInfo(_("configure"), _("Configuring"), _("Configured"))
    DOWNLOAD = EventInfo(_("download"), _("Downloading"), _("Downloaded"))
    UPDATE_REPO = EventInfo(_("update-repo"), _("Updating repo"), _("Updated repo"))
    SYSTEM_CONF = EventInfo(_("system-conf"), _("System config"), _("System configured"))
    SNAPSHOT = EventInfo(_("snapshot"), _("Snapshotting"), _("Snapshotted"))

    @property
    def label(self) -> str:
        return self.value.label

    @property
    def done_label(self) -> str:
        return self.value.done_label


@dataclass(frozen=True)
class PkgInfo:
    """Structured package metadata carried by progress events.

    N.B. Sending the full package object over the worker queue was too
    expensive, so this is a compromise payload for now.
    """

    name: str = ""
    version: str = ""
    release: str = ""
    summary: str = ""


@dataclass(frozen=True)
class ItemProgress:
    """Per-item progress within a work phase."""

    item: str
    completed: int
    total: int


@dataclass(frozen=True)
class ItemDone:
    """Completion of a single item within a work phase."""

    item: str
