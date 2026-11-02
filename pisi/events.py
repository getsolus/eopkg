# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later
"""Typed vocabulary and messages for operation progress events leaf module."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


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

    INSTALL = EventInfo("install", "Installing", "Installed")
    REINSTALL = EventInfo("reinstall", "Reinstalling", "Reinstalled")
    UPGRADE = EventInfo("upgrade", "Upgrading", "Upgraded")
    DOWNGRADE = EventInfo("downgrade", "Downgrading", "Downgraded")
    REMOVE = EventInfo("remove", "Removing", "Removed")
    CONFIGURE = EventInfo("configure", "Configuring", "Configured")
    DOWNLOAD = EventInfo("download", "Downloading", "Downloaded")
    UPDATE_REPO = EventInfo("update-repo", "Updating repo", "Updated repo")
    SYSTEM_CONF = EventInfo("system-conf", "System config", "System configured")
    SNAPSHOT = EventInfo("snapshot", "Snapshotting", "Snapshotted")

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
