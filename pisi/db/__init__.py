# Copyright (C) 2005 - 2009, TUBITAK/UEKAE
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free
# Software Foundation; either version 2 of the License, or (at your option)
# any later version.
#
# Please read the COPYING file.
#

import xml.etree.ElementTree as xml

from pisi.db import componentdb, groupdb, historydb, installdb, packagedb, repodb


def invalidate_caches():
    # Invalidates pisi caches in use and forces to re-fill caches from disk when needed
    for db in [
        packagedb.PackageDB(),
        componentdb.ComponentDB(),
        installdb.InstallDB(),
        historydb.HistoryDB(),
        groupdb.GroupDB(),
        repodb.RepoDB(),
    ]:
        db.invalidate()


def flush_caches(only_invalid=False):
    """
    Invalidates and flush caches to re-generate them when needed.
    Set only_invalid to True to only flush invalid caches.
    """
    for db in [
        packagedb.PackageDB(),
        installdb.InstallDB(),
        componentdb.ComponentDB(),
        groupdb.GroupDB(),
    ]:
        if only_invalid:
            if db.cache_valid():
                continue
        db.invalidate()
        db.cache_flush()


def update_caches():
    # Updates ondisk caches
    for db in [
        packagedb.PackageDB(),
        componentdb.ComponentDB(),
        installdb.InstallDB(),
        groupdb.GroupDB(),
    ]:
        if db.is_initialized():
            db.cache_save()


def regenerate_caches():
    flush_caches()
    # Force cache regeneration
    for db in [packagedb.PackageDB(), componentdb.ComponentDB(), groupdb.GroupDB()]:
        db.cache_regenerate()


def _get_version(meta_doc: xml.ElementTree) -> tuple[str, str, None] | None:
    history = meta_doc.find("Package/History")
    if history is None:
        return None
    update = history.find("Update")
    if update is None:
        return None
    return (
        update.findtext("Version") or "",
        update.attrib.get("release") or "",
        None,  # TODO Remove None
    )


def _get_distro_release(meta_doc: xml.ElementTree) -> tuple[str, str] | None:
    distro = meta_doc.findtext("Package/Distribution")
    release = meta_doc.findtext("Package/DistributionRelease")
    if not distro or not release:
        return None
    return distro, release
