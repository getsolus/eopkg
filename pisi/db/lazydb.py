# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

import os
import pickle
import time

import pisi
from pisi import context as ctx
from pisi import util

# lower borks for international locales. What we want is ascii lower.
ascii_lowercase = "abcdefghijklmnopqrstuvwxyz"
ascii_uppercase = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
lower_map = str.maketrans(ascii_uppercase, ascii_lowercase)


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
    cache_version = pisi.__version__

    def __init__(self, cacheable=False, cachedir=None):
        if "initialized" not in self.__dict__:
            self.initialized = False
        self.cacheable = cacheable
        self.cachedir = cachedir

    def is_initialized(self):
        return self.initialized

    def __cache_file(self):
        return util.join_path(
            ctx.config.cache_root_dir(),
            "%s.cache" % self.__class__.__name__.translate(lower_map),
        )

    def __cache_version_file(self):
        return "%s.version" % self.__cache_file()

    def cache_save(self):
        if os.access(ctx.config.cache_root_dir(), os.W_OK) and self.cacheable:
            with open(self.__cache_version_file(), "w") as f:
                f.write(LazyDB.cache_version)
                f.flush()
                os.fsync(f.fileno())
            pickle.dump(self._instance, open(self.__cache_file(), "wb"), protocol=2)

    def cache_valid(self):
        try:
            f = self.__cache_version_file()
            ver = open(f).read().strip()
        except IOError:
            return False
        return ver == LazyDB.cache_version

    def cache_load(self):
        if os.path.exists(self.__cache_file()) and self.cache_valid():
            try:
                self._instance = pickle.load(
                    open(self.__cache_file(), "rb"), encoding="utf8"
                )
                return True
            except (pickle.UnpicklingError, EOFError):
                if os.access(ctx.config.cache_root_dir(), os.W_OK):
                    os.unlink(self.__cache_file())
                return False
        return False

    def cache_flush(self):
        for path in [self.__cache_file(), self.__cache_version_file()]:
            try:
                os.remove(path)
            except FileNotFoundError:
                pass

    def invalidate(self):
        self._delete()

    def cache_regenerate(self):
        try:
            self.this_attr_does_not_exist()
        except AttributeError:
            pass

    def __init(self):
        if not self.cache_load():
            self.init()

    def __getattr__(self, attr):
        if not attr == "__setstate__" and not self.initialized:
            start = time.time()
            self.__init()
            end = time.time()
            ctx.ui.debug(
                "%s initialized in %s." % (self.__class__.__name__, end - start)
            )
            self.initialized = True

        if attr not in self.__dict__:
            raise AttributeError(attr)

        return self.__dict__[attr]
