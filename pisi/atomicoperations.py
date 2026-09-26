# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

"""Atomic package operations such as install/remove/upgrade"""

from __future__ import annotations

import base64
import os
import shutil
import zipfile

import pisi
import pisi.context as ctx
import pisi.db
import pisi.files
import pisi.operations.delta
import pisi.ui
import pisi.version
from pisi import translate as _
from pisi import util
from pisi.events import Operation
from pisi.path import is_usr_merged_duplicate


class Error(pisi.Error):
    pass


class NotfoundError(pisi.Error):
    pass


class AtomicOperation:
    def __init__(self, ignore_dep=None):
        # self.package = package
        if ignore_dep == None:
            self.ignore_dep = ctx.config.get_option("ignore_dependency")
        else:
            self.ignore_dep = ignore_dep

        self.historydb = pisi.db.historydb.HistoryDB()

    def run(self, package):
        "perform an atomic package operation"
        pass


# Short aliases used throughout the codebase (see pisi.events.Operation)
INSTALL = Operation.INSTALL
REINSTALL = Operation.REINSTALL
UPGRADE = Operation.UPGRADE
DOWNGRADE = Operation.DOWNGRADE
REMOVE = Operation.REMOVE


class Install(AtomicOperation):
    "Install class, provides install routines for pisi packages"

    # Is this an automatic install?
    automatic = False

    def __init__(self, package_fname, ignore_dep=None, ignore_file_conflicts=None):
        "initialize from a file name"
        super().__init__(ignore_dep)
        if not ignore_file_conflicts:
            ignore_file_conflicts = ctx.get_option("ignore_file_conflicts")
        self.ignore_file_conflicts = ignore_file_conflicts
        self.package_fname = package_fname
        try:
            self.package = pisi.package.Package(package_fname)
            self.package.read()
        except zipfile.BadZipfile:
            raise zipfile.BadZipfile(self.package_fname)
        self.metadata = self.package.metadata
        self.files = self.package.files
        self.pkginfo = self.metadata.package
        self.filesdb = pisi.db.filesdb.FilesDB()
        self.installdb = pisi.db.installdb.InstallDB()
        self.operation = INSTALL
        self.automatic = False
        # Config files renamed by check_configs() (pre-extraction); restored
        # by rename_configs() from update_databases() in the main process.
        self.config_changed = []
        self.progress_callback = None

    def preflight(self, ask_reinstall=True):
        self.check_replaces()
        self.ask_reinstall = ask_reinstall
        self.check_operation()
        self.check_versioning(self.pkginfo.version, self.pkginfo.release)

    def install(self, ask_reinstall=True):
        # Any package should remove the package it replaces before
        self.preflight(ask_reinstall)
        self.check_configs()
        self.extract()
        self.update_databases()

    def extract(self):
        """Extract package files.

        Pure extraction — no DB access and no preflight state required — so
        it can be safely called from parallelized workers. All upgrade/
        reinstall bookkeeping (config handling, delta relocations, storing
        package info, removing leftovers and the old pkg dir) happens in the
        main process in check_configs()/update_databases(). Progress events
        reach the frontend via `progress_callback` → progress queue →
        `ctx.ui.work_phase()`.
        """

        self.extract_install()

    def check_replaces(self):
        for replaced in self.pkginfo.replaces:
            if self.installdb.has_package(replaced.package):
                pisi.operations.remove.remove_replaced_packages([replaced.package])

    def check_versioning(self, version, release):
        try:
            int(release)
            pisi.version.make_version(version)
        except (ValueError, pisi.version.InvalidVersionError):
            raise Error(
                _("%s-%s is not a valid eopkg version format") % (version, release)
            )

    def check_relations(self, plan_packages=None):
        # check dependencies
        if not ctx.config.get_option("ignore_dependency"):
            if not self.pkginfo.installable(plan_packages):
                raise Error(
                    _(
                        "%s package cannot be installed unless the dependencies are satisfied"
                    )
                    % self.pkginfo.name
                )

        # If it is explicitly specified that package conflicts with this package and also
        # we passed check_conflicts tests in operations.py than this means a non-conflicting
        # pkg is in "order" to be installed that has no file conflict problem with this package.
        # PS: we need this because "order" generating code does not consider conflicts.
        def really_conflicts(pkg):
            if not self.pkginfo.conflicts:
                return True

            return not pkg in [x.package for x in self.pkginfo.conflicts]

        # check file conflicts
        file_conflicts = []
        for f in self.files.list:
            if self.filesdb.has_file(f.path):
                pkg, existing_file = self.filesdb.get_file(f.path)
                dst = util.join_path(ctx.config.dest_dir(), f.path)
                if (
                    pkg != self.pkginfo.name
                    and not os.path.isdir(dst)
                    and really_conflicts(pkg)
                ):
                    file_conflicts.append((pkg, existing_file))
        if file_conflicts:
            upgradable_pkgs = pisi.api.list_upgradable()
            file_conflicts_str = ""
            for pkg, existing_file in file_conflicts:
                paths = [fileinfo.path for fileinfo in self.files.list]
                replaced_by = False
                if existing_file in paths:
                    # FIXME: If the package is in the updates list assume it's been vetted for now...
                    #        What we really want to do is see if the conflicting pkg exists in the
                    #        install order and the conflicting file no longer exists there.
                    if pkg in upgradable_pkgs:
                        file_conflicts_str += _(
                            "/%s from %s gets replaced by %s package\n"
                        ) % (existing_file, pkg, self.pkginfo.name)
                        replaced_by = True
                    else:
                        file_conflicts_str += _("/%s from %s package\n") % (
                            existing_file,
                            pkg,
                        )
                else:
                    file_conflicts_str += _("/%s from %s package\n") % (
                        existing_file,
                        pkg,
                    )
                msg = _("File conflicts:\n%s") % file_conflicts_str
            if self.ignore_file_conflicts or replaced_by:
                ctx.ui.warning(msg)
            else:
                raise Error(msg)

    def check_operation(self):
        self.old_pkginfo = None
        pkg = self.pkginfo

        if self.installdb.has_package(pkg.name):  # is this a reinstallation?
            _ipkg = self.installdb.get_package(pkg.name)
            (iversion_s, irelease_s, _ibuild) = self.installdb.get_version(pkg.name)

            # determine if same distribution release
            if pkg.release == irelease_s:
                if self.ask_reinstall and not ctx.ui.confirm(
                    _("Re-install same distribution release of package?")
                ):
                    raise Error(_("Package re-install declined"))
                self.operation = REINSTALL
            else:
                pkg_release = int(pkg.release)
                irelease = int(irelease_s)

                # is this an upgrade?
                if pkg_release > irelease:
                    self.operation = UPGRADE

                # is this a downgrade? confirm this action.
                if self.operation != UPGRADE:
                    if pkg_release < irelease:
                        x = _("Downgrade to old distribution release?")
                    else:
                        x = None
                    if self.ask_reinstall and x and not ctx.ui.confirm(x):
                        raise Error(_("Package downgrade declined"))
                    self.operation = DOWNGRADE

            # schedule for reinstall
            self.old_files = self.installdb.get_files(pkg.name)
            self.old_pkginfo = self.installdb.get_info(pkg.name)
            self.old_path = self.installdb.pkg_dir(pkg.name, iversion_s, irelease_s)
            self.remove_old = Remove(pkg.name)

    def reinstall(self):
        return self.operation != INSTALL

    def extract_install(self):
        "unzip package in place"

        extracted_count = 0

        def extract_callback(tarinfo, extracted):
            nonlocal extracted_count
            if extracted:
                extracted_count += 1
                if self.progress_callback:
                    self.progress_callback(extracted_count, len(self.files.list))

        self.package.extract_install(ctx.config.dest_dir(), callback=extract_callback)
        self.restore_xattrs()

    def _check_config_changed(self, config):
        fpath = util.join_path(ctx.config.dest_dir(), config.path)
        if util.config_changed(config):
            self.config_changed.append(fpath)
            self.historydb.save_config(self.pkginfo.name, fpath)
            if os.path.exists(fpath + ".old"):
                os.unlink(fpath + ".old")
            os.rename(fpath, fpath + ".old")

    def check_configs(self):
        """Pre-extraction step, main process only.

        User-modified config files are renamed to ".old" before extraction
        so the new package cannot clobber them; rename_configs() restores
        them afterwards. Must run after preflight() (needs old_files) and
        before extract().
        """
        self.config_changed = []
        if self.reinstall():
            # get 'config' typed file objects
            new = [x for x in self.files.list if x.type == "config"]
            old = [x for x in self.old_files.list if x.type == "config"]

            # get config path lists
            newconfig = {str(x.path) for x in new}
            oldconfig = {str(x.path) for x in old}

            config_overlaps = newconfig & oldconfig
            if config_overlaps:
                files = [x for x in old if x.path in config_overlaps]
                for f in files:
                    self._check_config_changed(f)
        else:
            for f in self.files.list:
                if f.type == "config":
                    # there may be left over config files
                    self._check_config_changed(f)

    def rename_configs(self):
        """Post-extraction step, main process only.

        Old config files are kept as they are. New config files from the
        installed packages are saved with ".newconfig" appended to their
        names.
        """
        for path in self.config_changed:
            newconfig = path + ".newconfig"
            oldconfig = path + ".old"
            if os.path.exists(newconfig):
                os.unlink(newconfig)

            # In the case of delta packages: the old package and the new package
            # may contain same config typed files with same hashes, so the delta
            # package will not have that config file. In order to protect user
            # changed config files, they are renamed with ".old" prefix in case
            # of the hashes of these files on the filesystem and the new config
            # file that is coming from the new package. But in delta package case
            # with the given scenario there wont be any, so we can pass this one.
            # If the config files were not be the same between these packages the
            # delta package would have it and extract it and the path would point
            # to that new config file. If they are same and the user had changed
            # that file and using the changed config file, there is no problem
            # here.
            if os.path.exists(path):
                os.rename(path, newconfig)

            os.rename(oldconfig, path)

    # Package file's path may not be relocated or content may not be changed but
    # permission may be changed
    def update_permissions(self):
        permissions = pisi.operations.delta.find_permission_changes(
            self.old_files, self.files
        )
        for path, mode in permissions:
            os.chmod(path, mode)

    # Delta package does not contain the files that have the same hash as in
    # the old package's. Because it means the file has not changed. But some
    # of these files may be relocated to some other directory in the new package.
    # We handle these cases here.
    def relocate_files(self):
        missing_old_files = set()

        for old_file, new_file in pisi.operations.delta.find_relocations(
            self.old_files, self.files
        ):
            old_path = os.path.join(ctx.config.dest_dir(), old_file.path)
            new_path = os.path.join(ctx.config.dest_dir(), new_file.path)

            if not os.path.lexists(old_path):
                missing_old_files.add(old_path)
                continue

            if os.path.lexists(new_path):
                # If one of the parent directories is a symlink, it is possible
                # that the new and old file paths refer to the same file.
                # In this case, there is nothing to do here.
                #
                # e.g. /lib/libdl.so and /lib64/libdl.so when /lib64 is
                # a symlink to /lib.
                if os.path.basename(old_path) == os.path.basename(
                    new_path
                ) and os.path.samestat(os.lstat(old_path), os.lstat(new_path)):
                    continue

                os.unlink(new_path)

            destdir = os.path.dirname(new_path)
            if not os.path.exists(destdir):
                os.makedirs(destdir)

            if os.path.islink(old_path):
                os.symlink(os.readlink(old_path), new_path)
            else:
                shutil.copy(old_path, new_path)

        if missing_old_files:
            ctx.ui.warning(
                _(
                    "Unable to relocate following files. Reinstallation of this package is strongly recommended."
                )
            )
            for f in sorted(missing_old_files):
                ctx.ui.warning(f"    - {f}")

    def clean_leftovers(self):
        """Remove files left over from the old package after extraction.

        Deliberately runs in the main process (from update_databases), not
        in the extraction workers: it needs the system-wide FilesDB for
        conflict checks, and workers cold-initialize DBs (multiprocessing
        defaults to forkserver on py3.13+), which is expensive and can
        even trigger a full FilesDB rebuild from every package's files.xml.
        """
        stat_cache = {}

        files_by_name = {}
        new_paths = set()
        for f in self.files.list:
            files_by_name.setdefault(os.path.basename(f.path), []).append(f)
            new_paths.add(f.path)

        for old_file in self.old_files.list:
            if old_file.path in new_paths:
                continue

            old_file_path = os.path.join(ctx.config.dest_dir(), old_file.path)

            try:
                old_file_stat = os.lstat(old_file_path)
            except OSError:
                continue

            old_filename = os.path.basename(old_file.path)

            # If one of the parent directories is a symlink, it is possible
            # that the new and old file paths refer to the same file.
            # In this case, we must not remove the old file.
            #
            # e.g. /lib/libdl.so and /lib64/libdl.so when /lib64 is
            # a symlink to /lib.
            for new_file in files_by_name.get(old_filename, []):
                new_file_stat = stat_cache.get(new_file.path)

                if new_file_stat is None:
                    path = os.path.join(ctx.config.dest_dir(), new_file.path)
                    try:
                        new_file_stat = os.lstat(path)
                    except OSError:
                        continue

                    stat_cache[new_file.path] = new_file_stat

                if os.path.samestat(new_file_stat, old_file_stat):
                    break
            else:
                Remove.remove_file(old_file, self.pkginfo.name)

    def restore_xattrs(self):
        try:
            import xattr

            for file in self.files.list:
                if not file.extendedAttributes:
                    continue
                for attrPair in file.extendedAttributes:
                    realVal = base64.b64decode(bytes(attrPair.value, "utf-8"))
                    xattr.setxattr("/" + file.path, attrPair.label, realVal)
        except ImportError as e:
            ctx.ui.warning(f"{e}")
        except OSError as e:
            ctx.ui.warning(f"Failed to restore xattr: {e}")
            # ctx.ui.warning("Please run: eopkg fix-attributes")

    def store_pisi_files(self):
        """put files.xml, metadata.xml, actions.py and COMAR scripts
        somewhere in the file system. We'll need these in future..."""

        if self.reinstall():
            util.clean_dir(self.old_path)

        ctx.ui.info(_("Storing %s") % ctx.const.files_xml, verbose=True)
        self.package.extract_file_synced(ctx.const.files_xml, self.package.pkg_dir())

        ctx.ui.info(_("Storing %s") % ctx.const.metadata_xml, verbose=True)
        self.package.extract_file_synced(ctx.const.metadata_xml, self.package.pkg_dir())

        for pcomar in self.metadata.package.providesComar:
            fpath = os.path.join(ctx.const.comar_dir, pcomar.script)
            # comar prefix is added to the pkg_dir while extracting comar
            # script file. so we'll use pkg_dir as destination.
            ctx.ui.info(_("Storing %s") % fpath, verbose=True)
            self.package.extract_file_synced(fpath, self.package.pkg_dir())

    def update_databases(self):
        "update databases"
        if self.config_changed:
            self.rename_configs()

        if self.package_fname.endswith(ctx.const.delta_package_suffix):
            self.relocate_files()
            self.update_permissions()

        self.store_pisi_files()

        if self.reinstall():
            self.clean_leftovers()
            self.remove_old.remove_db()

        # need system restart?
        if self.installdb.has_package(self.pkginfo.name):
            (_version, release, _build) = self.installdb.get_version(self.pkginfo.name)
            actions = self.pkginfo.get_update_actions(release)
        else:
            actions = self.pkginfo.get_update_actions("1")

        for package_name in actions.get("systemRestart", []):
            pisi.api.add_needs_reboot(package_name)

        # filesdb
        self.filesdb.add_files(self.metadata.package.name, self.files)

        # Store old package info for history before adding the new one
        if not hasattr(self, 'old_pkginfo'):
            self.old_pkginfo = (
                self.installdb.get_info(self.pkginfo.name)
                if self.installdb.has_package(self.pkginfo.name)
                else None
            )

        # installed packages
        self.installdb.add_package(self.pkginfo)

        # If we're manually installed, remove flag
        if self.automatic:
            self.installdb.mark_auto_installed(self.pkginfo.name)
        else:
            self.installdb.clear_auto_installed(self.pkginfo.name)

        otype = (
            "delta"
            if self.package_fname.endswith(ctx.const.delta_package_suffix)
            else None
        )
        self.historydb.add_and_update(
            pkgBefore=self.old_pkginfo,
            pkgAfter=self.pkginfo,
            operation=self.operation.value.name,
            otype=otype,
        )


class Remove(AtomicOperation):
    def __init__(self, package_name, ignore_dep=None):
        super().__init__(ignore_dep)
        self.installdb = pisi.db.installdb.InstallDB()
        self.filesdb = pisi.db.filesdb.FilesDB()
        self.package_name = package_name
        self.package = self.installdb.get_package(self.package_name)
        try:
            self.files = self.installdb.get_files(self.package_name)
        except pisi.Error as e:
            # for some reason file was deleted, we still allow removes!
            ctx.ui.error(str(e))
            ctx.ui.warning(
                _("File list could not be read for package %s, continuing removal.")
                % package_name
            )
            self.files = pisi.files.Files()

    def run(self):
        """Remove a single package"""

        ctx.ui.status(_("Removing package %s") % self.package_name)
        ctx.ui.notify(pisi.ui.removing, package=self.package, files=self.files)
        if not self.installdb.has_package(self.package_name):
            raise Error(_("Trying to remove nonexistent package ") + self.package_name)

        self.check_dependencies()

        for fileinfo in self.files.list:
            if is_usr_merged_duplicate(self.files.list, fileinfo.path):
                ctx.ui.debug(f"Not removing usr-merged file: {fileinfo.path}")
                continue

            self.remove_file(fileinfo, self.package_name, True)

        self.update_databases()

        self.remove_pisi_files()

        ctx.ui.close()
        ctx.ui.notify(pisi.ui.removed, package=self.package, files=self.files)

    def check_dependencies(self):
        # FIXME: why is this not implemented? -- exa
        # we only have to check the dependencies to ensure the
        # system will be consistent after this removal
        pass
        # is there any package who depends on this package?

    @staticmethod
    def remove_file(fileinfo, package_name, remove_permanent=False):
        if fileinfo.permanent and not remove_permanent:
            return

        fpath = pisi.util.join_path(ctx.config.dest_dir(), fileinfo.path)

        historydb = pisi.db.historydb.HistoryDB()
        filesdb = pisi.db.filesdb.FilesDB()
        # we should check if the file belongs to another
        # package (this can legitimately occur while upgrading
        # two packages such that a file has moved from one package to
        # another as in #2911)
        if filesdb.has_file(fileinfo.path):
            pkg, existing_file = filesdb.get_file(fileinfo.path)
            if pkg != package_name:
                ctx.ui.warning(_("Not removing conflicted file : %s") % fpath)
                return

        if fileinfo.type == ctx.const.conf:
            # config files are precious, leave them as they are
            # unless they are the same as provided by package.
            # remove symlinks as they are, cause if the hash of the
            # file it links has changed, it will be kept as is,
            # and when the package is reinstalled the symlink will
            # link to that changed file again.
            try:
                if os.path.islink(fpath) or pisi.util.sha1_file(fpath) == fileinfo.hash:
                    os.unlink(fpath)
                else:
                    # keep changed file in history
                    historydb.save_config(package_name, fpath)

                    # after saving to history db, remove the config file any way
                    if ctx.get_option("purge"):
                        os.unlink(fpath)
            except pisi.util.FileError:
                pass
            except pisi.util.FileNotFoundError:
                ctx.ui.warning(
                    _(
                        "Installed config file %s does not exist on system [Probably you manually deleted]"
                    )
                    % fpath
                )
        else:
            if os.path.isfile(fpath) or os.path.islink(fpath):
                os.unlink(fpath)
            elif os.path.isdir(fpath) and not os.listdir(fpath):
                os.rmdir(fpath)
            else:
                ctx.ui.warning(
                    _(
                        "Installed file %s does not exist on system [Probably you manually deleted]"
                    )
                    % fpath
                )
                return

        # remove emptied directories
        dpath = os.path.dirname(fpath)
        while dpath != "/" and not os.listdir(dpath):
            os.rmdir(dpath)
            dpath = os.path.dirname(dpath)

    def update_databases(self):
        self.remove_db()
        self.historydb.add_and_update(pkgBefore=self.package, operation="remove")

    def remove_pisi_files(self):
        util.clean_dir(self.package.pkg_dir())

    def remove_db(self):
        self.installdb.remove_package(self.package_name)
        self.installdb.clear_auto_installed(self.package_name)
        self.filesdb.remove_files(self.files.list)


# FIX:DB
#         # FIXME: something goes wrong here, if we use ctx operations ends up with segmentation fault!
#         pisi.db.packagedb.remove_tracking_package(self.package_name)


def remove_single(package_name):
    Remove(package_name).run()


def build(package):
    # wrapper for build op
    from pisi.operations.build import build

    return build(package)
