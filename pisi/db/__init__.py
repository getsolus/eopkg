# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

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


def flush_caches():
    # Invalidate and flush caches to re-generate them when needed
    for db in [packagedb.PackageDB(), componentdb.ComponentDB(), groupdb.GroupDB()]:
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
