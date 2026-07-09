# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

import os

import pisi
from pisi import context as ctx
from pisi import util


class Singleton(object):
    _the_instances = {}

    def __new__(type):
        if not type.__name__ in Singleton._the_instances:
            Singleton._the_instances[type.__name__] = object.__new__(type)
        return Singleton._the_instances[type.__name__]

    @property
    def _instance(self):
        return self._the_instances[type(self).__name__]

    @_instance.setter
    def _instance(self, value):
        self._the_instances[type(self).__name__] = value

    def _delete(self):
        # FIXME: After invalidate, previously initialized db object becomes stale
        del self._the_instances[type(self).__name__]


class LazyDB(Singleton):
    def __init__(self):
        if "initialized" not in self.__dict__:
            self.initialized = False

    @property
    def lmdb_store(self):
        from pisi.db.lmdbstore import LMDBStore

        path = util.join_path(ctx.config.cache_root_dir(), "eopkg_db")
        # We determine readonly based on directory access
        readonly = not os.access(ctx.config.cache_root_dir(), os.W_OK)
        return LMDBStore.get_instance(path, readonly=readonly)

    def is_initialized(self):
        return self.initialized

    def cache_flush(self):
        if not self.lmdb_store.readonly:
            # Subclasses can define lmdb_mappings to be cleared
            if hasattr(self, "lmdb_mappings"):
                for mapping in self.lmdb_mappings:
                    mapping.clear()

    def invalidate(self):
        self._delete()

    def __init(self):
        self.init()

    def __getattr__(self, attr):
        if not attr == "__setstate__" and not self.initialized:
            self.__init()
            self.initialized = True

        if attr not in self.__dict__:
            raise AttributeError(attr)

        return self.__dict__[attr]
