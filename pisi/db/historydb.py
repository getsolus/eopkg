# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

import os

from pisi import context as ctx
from pisi import history, util
from pisi.db import lazydb


class HistoryDB(lazydb.LazyDB):
    def __init__(self):
        # Set cacheable=False because we use LMDB now
        lazydb.LazyDB.__init__(self, cacheable=False)

    @property
    def lmdb_mappings(self):
        return [self.__history_ops, self.__history_files]

    def init(self):
        self.__history_ops = self.lmdb_store.get_mapping("history_ops")
        self.__history_files = self.lmdb_store.get_mapping("history_files")
        meta = self.lmdb_store.get_mapping("meta")

        history_dir = ctx.config.history_dir()
        if not os.path.exists(history_dir):
            os.makedirs(history_dir, exist_ok=True)

        mtime = os.path.getmtime(history_dir)
        cached_mtime = meta.get("mtime_history")

        if len(self.__history_ops) == 0 or cached_mtime != mtime:
            if self.lmdb_store.readonly and not self.lmdb_store.use_memory:
                # Stale but we can't write to LMDB. Use memory for this session.
                from pisi.db.lmdbstore import MemoryMapping

                self.__history_ops = MemoryMapping()
                self.__history_files = MemoryMapping()

            self.__repopulate(history_dir)

            if not self.lmdb_store.readonly:
                meta["mtime_history"] = mtime

        # For compatibility with existing code that uses self.__logs
        self.__logs = sorted(
            self.__history_files.keys(),
            key=lambda x: int(x.split("_")[0].replace("0o", "0")),
            reverse=True,
        )
        self.history = history.History()

    def __repopulate(self, history_dir):
        logs = [x for x in os.listdir(history_dir) if x.endswith(".xml")]

        # We only need to parse what we don't have or if we are doing a full refresh
        # To keep it simple, we clear and re-parse if mtime changed,
        # but we could be more surgical.
        self.__history_ops.clear()
        self.__history_files.clear()

        ops = {}
        files = {}
        for log in logs:
            try:
                hist = history.History(os.path.join(history_dir, log))
                op_no = log.split("_")[0]
                hist.operation.no = int(op_no)
                ops[op_no] = hist.operation
                files[log] = op_no
            except Exception as e:
                ctx.ui.warning(_("Failed to parse history file %s: %s") % (log, str(e)))

        self.__history_ops.update_bulk(ops)
        self.__history_files.update_bulk(files)

    def create_history(self, operation):
        self.history.create(operation)

    def add_and_update(self, pkgBefore=None, pkgAfter=None, operation=None, otype=None):
        self.add_package(pkgBefore, pkgAfter, operation, otype)
        self.update_history()

    def add_package(self, pkgBefore=None, pkgAfter=None, operation=None, otype=None):
        self.history.add(pkgBefore, pkgAfter, operation, otype)

    def load_config(self, operation, package):
        config_dir = os.path.join(ctx.config.history_dir(), "%03d" % operation, package)
        if os.path.exists(config_dir):
            import distutils.dir_util as dir_util

            dir_util.copy_tree(config_dir, "/")

    def save_config(self, package, config_file):
        hist_dir = os.path.join(
            ctx.config.history_dir(), self.history.operation.no, package
        )
        if os.path.isdir(config_file):
            os.makedirs(os.path.join(hist_dir, config_file))
            return

        destdir = os.path.join(hist_dir, config_file[1:])
        util.copy_file_stat(config_file, destdir)

    def update_repo(self, repo, uri, operation=None):
        self.history.update_repo(repo, uri, operation)
        self.update_history()

    def update_history(self):
        self.history.update()
        # Invalidate cache so it's re-read next time
        meta = self.lmdb_store.get_mapping("meta")
        if not self.lmdb_store.readonly:
            meta["mtime_history"] = 0

    def get_operation(self, operation):
        op_no = "%03d" % operation
        # Try finding by exact op_no first
        if op_no in self.__history_ops:
            return self.__history_ops[op_no]

        # Fallback for non-padded or different naming if any
        for log, log_op_no in self.__history_files.items():
            if int(log_op_no) == operation:
                return self.__history_ops[log_op_no]
        return None

    def get_package_config_files(self, operation, package):
        package_path = os.path.join(
            ctx.config.history_dir(), "%03d/%s" % (operation, package)
        )
        if not os.path.exists(package_path):
            return None

        configs = []
        for root, dirs, files in os.walk(package_path):
            for f in files:
                configs.append(("%s/%s" % (root, f)))

        return configs

    def get_config_files(self, operation):
        config_path = os.path.join(ctx.config.history_dir(), "%03d" % operation)
        if not os.path.exists(config_path):
            return None

        allconfigs = {}
        packages = os.listdir(config_path)
        for package in packages:
            allconfigs[package] = self.get_package_config_files(operation, package)

        return allconfigs

    def get_till_operation(self, operation):
        target_op_no = "%03d" % operation

        # Sort logs descending
        logs = sorted(
            self.__history_files.keys(),
            key=lambda x: int(x.split("_")[0].replace("0o", "0")),
            reverse=True,
        )

        found = False
        for log in logs:
            op_no = self.__history_files[log]
            if op_no == target_op_no:
                found = True
                break

        if not found:
            return

        for log in logs:
            op_no = self.__history_files[log]
            if op_no == target_op_no:
                return
            yield self.__history_ops[op_no]

    def get_last(self, count=0):
        logs = sorted(
            self.__history_files.keys(),
            key=lambda x: int(x.split("_")[0].replace("0o", "0")),
            reverse=True,
        )

        count = count or len(logs)
        for log in logs[:count]:
            op_no = self.__history_files[log]
            yield self.__history_ops[op_no]

    def get_last_repo_update(self, last=1):
        repoupdates = [
            l for l in self.__history_files.keys() if l.endswith("repoupdate.xml")
        ]
        repoupdates.sort(key=lambda x: int(x.split("_")[0].replace("0o", "0")))

        if not len(repoupdates) >= 2:
            return None

        if last != 1 and len(repoupdates) <= last:
            return None

        op_no = self.__history_files[repoupdates[-last]]
        return self.__history_ops[op_no].date
