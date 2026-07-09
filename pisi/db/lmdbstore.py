# SPDX-FileCopyrightText: 2024 Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

import os
import pickle
from collections.abc import MutableMapping

import lmdb


class LMDBMapping(MutableMapping):
    """A dictionary-like interface backed by LMDB."""

    def __init__(self, env, name, readonly=False):
        self.env = env
        self.name = name
        self.readonly = readonly
        self._db = self.env.open_db(name.encode())

    def __getitem__(self, key):
        with self.env.begin(db=self._db) as txn:
            value = txn.get(key.encode())
            if value is None:
                raise KeyError(key)
            return pickle.loads(value)

    def __setitem__(self, key, value):
        if self.readonly:
            raise PermissionError("Database is read-only")
        with self.env.begin(db=self._db, write=True) as txn:
            txn.put(key.encode(), pickle.dumps(value))

    def __delitem__(self, key):
        if self.readonly:
            raise PermissionError("Database is read-only")
        with self.env.begin(db=self._db, write=True) as txn:
            if not txn.delete(key.encode()):
                raise KeyError(key)

    def __iter__(self):
        with self.env.begin(db=self._db) as txn:
            cursor = txn.cursor()
            for key in cursor.iternext(keys=True, values=False):
                yield key.decode()

    def __len__(self):
        with self.env.begin(db=self._db) as txn:
            return txn.stat()["entries"]

    def update_bulk(self, mapping):
        """Efficiently update multiple items in a single transaction."""
        if self.readonly:
            raise PermissionError("Database is read-only")
        with self.env.begin(db=self._db, write=True) as txn:
            for key, value in mapping.items():
                txn.put(key.encode(), pickle.dumps(value))

    def clear(self):
        if self.readonly:
            raise PermissionError("Database is read-only")
        with self.env.begin(write=True) as txn:
            txn.drop(self._db, delete=False)


_lmdb_instance = None


class LMDBStore:
    """Manages the LMDB environment for LazyDB."""

    def __init__(self, path, map_size=10 * 1024 * 1024 * 1024, readonly=False):
        self.path = path
        self.readonly = readonly
        self.env = None

        # Ensure path exists
        if not readonly and not os.path.exists(path):
            os.makedirs(path, exist_ok=True)

        self.env = lmdb.open(
            self.path,
            map_size=map_size,
            subdir=True,
            readonly=readonly,
            lock=not readonly,
            max_dbs=128,
        )

    @staticmethod
    def get_instance(path, readonly=False):
        global _lmdb_instance
        if _lmdb_instance is None:
            _lmdb_instance = LMDBStore(path, readonly=readonly)
        return _lmdb_instance

    def get_mapping(self, name):
        return LMDBMapping(self.env, name, readonly=self.readonly)

    def close(self):
        if self.env:
            self.env.close()
