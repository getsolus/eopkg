# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

import dbm
import hashlib
import os
import re
import shelve

from pisi import translate as _
from pisi import ngettext

import pisi
from pisi import context as ctx
from pisi import util
from pisi.db import lazydb

# FIXME:
# We could traverse through files.xml files of the packages to find the path and
# the package - a linear search - as some well known package managers do. But the current
# file conflict mechanism of pisi prevents this and needs a fast has_file function.
# So currently filesdb is the only db and we cant still get rid of rebuild-db :/

# This MUST match the version used in eopkg.py2 as long as that is in use.
FILESDB_PICKLE_PROTOCOL_VERSION = 2

# We suspect that there will be an advantage in versioning this separately
FILESDB_FORMAT_VERSION = 4

class FilesDB(lazydb.LazyDB):
    def init(self, force_rebuild=False):
        self.filesdb = {}
        self.__check_filesdb(force_rebuild)

    def has_file(self, path):
        return hashlib.md5(path.encode()).hexdigest() in self.filesdb

    def get_file(self, path):
        return self.filesdb[hashlib.md5(path.encode()).hexdigest()], path

    def search_file(self, term):
        if self.has_file(term):
            pkg, path = self.get_file(term)
            return [(pkg, [path])]

        installdb = pisi.db.installdb.InstallDB()
        found = []
        for pkg in installdb.list_installed():
            files_xml = open(
                os.path.join(installdb.package_path(pkg), ctx.const.files_xml)
            ).read()
            paths = re.compile(
                "<Path>(.*?%s.*?)</Path>" % re.escape(term), re.I
            ).findall(files_xml)
            if paths:
                found.append((pkg, paths))
        return found

    def get_pkgconfig_provider(self, pkgconfigName):
        """get_pkgconfig_provider will try known paths to find the provider
        of a given pkgconfig name"""
        pcPaths = [
            "usr/lib64/pkgconfig",
            "usr/share/pkgconfig",
        ]
        for p in pcPaths:
            fp = p + "/" + str(pkgconfigName) + ".pc"
            if self.has_file(fp):
                return self.get_file(fp)
        return None

    def get_pkgconfig32_provider(self, pkgconfigName):
        """get_pkgconfig32_provider will try known paths to find the provider
        of a given pkgconfig32 name"""
        fp = "usr/lib32/pkgconfig/" + pkgconfigName + ".pc"
        if self.has_file(fp):
            return self.get_file(fp)
        return None

    def add_files(self, pkg, files):
        self.__check_filesdb()

        for f in files.list:
            self.filesdb[hashlib.md5(f.path.encode()).hexdigest()] = pkg

    def remove_files(self, files):
        for f in files:
            if hashlib.md5(f.path.encode()).hexdigest() in self.filesdb:
                del self.filesdb[hashlib.md5(f.path.encode()).hexdigest()]

    def destroy(self):
        files_db = os.path.join(ctx.config.info_dir(), ctx.const.files_db)
        if os.path.exists(files_db):
            os.unlink(files_db)

    def close(self):
        if isinstance(self.filesdb, shelve.DbfilenameShelf):
            self.filesdb.sync()
            self.filesdb.close()

    def __check_filesdb(self, force_rebuild=False):
        """Sets valid self.files_db reference and automatically rebuilds the underlying db if necessary."""

        # the db has already been correctly initialised and doesn't need a rebuild
        if isinstance(self.filesdb, shelve.DbfilenameShelf):
            return

        # Valid states:
        #
        # file does not exist:
        #   can write
        #     => open flag "n" (rebuild)
        #   cannot write
        #     => ignore, don't rebuild
        # file exists:
        #   can write:
        #     type == gdbm:
        #       version match:
        #         => open flag "w", don't rebuild
        #       else:
        #         => open flag "n" (rebuild)
        #     else:
        #       => open flag "n" (rebuild)
        #   cannot write:
        #     type == gdbm:
        #       version match:
        #         => open flag "r", don't rebuild
        #       else:
        #         => ignore, don't rebuild
        #     else:
        #       => ignore, don't rebuild

        # Does the FilesDB filename exist?
        file_exists = None
        # Can we write to the file?
        can_write = None
        # Which type is the db?
        db_type = None
        # Which access rights do we open the shelve with?
        # Note that flag = "n" is equivalent to "rebuild"
        flag = None
        # Can we read the shelve?
        valid_shelve = None
        # Does the FilesDB have a version?
        version = None
        # Do we need to rebuild the FilesDB?
        needs_rebuild = None
        # Do we need to display a reminder to rebuild FilesDB manually?
        please_rebuild_manually = None
        # Has the user asked for verbose output
        verbose = ctx.config.options.verbose

        files_db = os.path.join(ctx.config.info_dir(), ctx.const.files_db)

        # The goal of this large block is to deduce the flags with which to
        # open the FilesDB shelve.
        #
        # The "best" paths are the one where 'flag' is set and where neither
        # 'needs_rebuild' nor 'please_rebuild_manually' are True.
        #
        # Any path that results in needs_rebuild being set to True will
        # auto-rebuild the db.
        # 
        # All other paths imply that something is wrong with the FilesDB,
        # which in turn implies falling back to slow XML access for searches.
        #
        if not os.path.exists(files_db):
            msg = _("FilesDB %s does not exist.") % files_db
            file_exists = False
            try:
                with open(files_db, "w") as fp:
                    pass
                os.unlink(files_db)
                can_write = True
                flag = "n"
                if verbose:
                    ctx.ui.info(msg)
                needs_rebuild = True
            except:
                can_write = False
                if verbose:
                    ctx.ui.warning(msg)
                please_rebuild_manually = True
                # This block falls back to simple XML search because FilesDB is missing.
        # path exists
        else:
            file_exists = True
            db_type = dbm.whichdb(files_db)
            # Opening a db format not linked into CPython at build time will result in "".
            if not "dbm" in db_type:
                db_type = "unknown"
            if os.access(files_db, os.W_OK):
                can_write = True
                # we need dbm.gnu here for success
                if db_type != "dbm.gnu":
                    if verbose:
                        ctx.ui.info(_("FilesDB %s is writable, but is of wrong type '%s'.") % (files_db, db_type))
                    flag = "n"
                    needs_rebuild = True
                else:
                    flag = "w"
                    # db_type is dbm.gnu and the backing file looks to be writable
                    # So far, so good
            elif os.access(files_db, os.R_OK):
                can_write = False
                # we need dbm.gnu here for success
                if db_type != "dbm.gnu":
                    if verbose:
                        ctx.ui.info(_("FilesDB %s is readable, but is of wrong type '%s'.") % (files_db, db_type))
                    please_rebuild_manually = True
                else:
                    if verbose:
                        ctx.ui.info(_("Cannot open FilesDB %s for writing. Opening it read-only.") % files_db)
                    flag = "r"
                    # db_type is dbm.gnu and the backing file looks to be readable.
                # This block falls back to simple XML search if FilesDB is not the correct format
            else:
                can_write = False
                # the file exists, but we can neither read nor write to it
                if verbose:
                    ctx.ui.warning(_("FilesDB %s of type '%s' exists, but we cannot access it.") % (files_db, db_type))
                please_rebuild_manually = True
                # This block falls back to simple search because FilesDB isn't available

        # At this point, we have checked the first three indentation levels of the
        # decision tree. This means we need to try to open the shelve.

        if flag is not None:
            # At this point, we _should_ be able to _open_ the file.
            try:
                self.filesdb = shelve.open(files_db, flag, protocol=FILESDB_PICKLE_PROTOCOL_VERSION)
                valid_shelve = True
            except:
                if verbose:
                    ctx.ui.debug("shelve.open(files_db=%s, flag=%s, protocol=%s) failed."
                                % (files_db, flag, FILESDB_PICKLE_PROTOCOL_VERSION))
                valid_shelve = False
                # Can't open the shelve, it needs a rebuild
                msg = _("FilesDB %s is not in a valid shelve format.") % files_db
                if can_write:
                    if verbose:
                        ctx.ui.info(msg)
                    needs_rebuild = True
                else:
                    if verbose:
                        ctx.ui.warning(msg)
                    please_rebuild_manually = True
                    # This falls back to simple XML search if FilesDB isn't valid

            # If the backing shelve exists and is valid, check if it has a version key
            if valid_shelve and file_exists:
                try:
                    version = self.filesdb["version"]
                except:
                    msg = _("FilesDB %s has no version.") % files_db
                    if can_write:
                        if verbose:
                            ctx.ui.info(msg)
                        needs_rebuild = True
                    else:
                        if verbose:
                           ctx.ui.warning(msg)
                        please_rebuild_manually = True
                        # This falls back to simple XML search if FilesDB is unversioned

                if version is not None:
                    if version != FILESDB_FORMAT_VERSION:
                        msg = _("FilesDB is version %s, need version %s.") % (version, FILESDB_FORMAT_VERSION)
                        if can_write:
                            if verbose:
                                ctx.ui.info(msg)
                            needs_rebuild = True
                        else:
                            if verbose:
                                ctx.ui.warning(msg)
                            please_rebuild_manually = True
                            # This falls back to simple XML search if FilesDB has the wrong version

                    else:
                        # Everything is ok, the shelve is open with flag = "w"
                        needs_rebuild = False

        ctx.ui.debug("FilesDB %s check result:" % files_db)
        ctx.ui.debug("> file_exists = %s" % file_exists)
        ctx.ui.debug("> can_write = %s" % can_write)
        ctx.ui.debug("> db_type = %s" % db_type)
        ctx.ui.debug("> flag = %s" % flag)
        ctx.ui.debug("> valid_shelve = %s" % valid_shelve)
        ctx.ui.debug("> version = %s" % version)
        ctx.ui.debug("=> force_rebuild = %s" % force_rebuild)
        ctx.ui.debug("=> needs_rebuild = %s" % needs_rebuild)
        ctx.ui.debug("=> please_rebuild_manually = %s" % please_rebuild_manually)

        # This block implies that the state is invalid
        if please_rebuild_manually:
            ctx.ui.warning(_("FilesDB is invalid. Please rebuild it with 'sudo eopkg.py3 -y rdb'"))
            ctx.ui.warning(_("Falling back to slow and inaccurate XML search..."))

        if force_rebuild or needs_rebuild:
            self.__rebuild()

    def __rebuild(self):
        # This assumes that __check_db() has run
        files_db = os.path.join(ctx.config.info_dir(), ctx.const.files_db)
        ctx.ui.info(_("Rebuilding the FilesDB..."))
        self.close()
        self.destroy()
        self.filesdb = {}

        try:
            # "n" means we're opening a new shelve, overwriting the old one
            self.filesdb = shelve.open(files_db, "n", protocol=FILESDB_PICKLE_PROTOCOL_VERSION)
        except Exception as err:
            ctx.ui.debug("shelve.open(files_db=%s, flag=%s, protocol=%s) failed."
                           % (files_db, flag, FILESDB_PICKLE_PROTOCOL_VERSION))
            ctx.ui.error(_("FilesDB rebuild failed!"))
            raise err

        self.filesdb["version"] = FILESDB_FORMAT_VERSION
        # we need a list of installed files per package
        installdb = pisi.db.installdb.InstallDB()
        pkgs = 0
        verbose = ctx.config.options.verbose
        ctx.ui.info(_("Adding packages to FilesDB %s:") % files_db)
        for pkg in installdb.list_installed():
            files = installdb.get_files(pkg)
            if verbose:
                ctx.ui.info(_("Adding '%s' ...") % pkg, noln=True)
            self.add_files(pkg, files)
            if verbose:
                ctx.ui.info(_("Okay."))
            pkgs += 1
            # Print out useful markers every so often
            if pkgs % 50 == 0:
                if verbose:
                    ctx.ui.info("-------------")
                    ctx.ui.info(_("Added so far: %s") % pkgs)
                    ctx.ui.info("-------------")
                else:
                    ctx.ui.info(".", noln=True)
        ctx.ui.info(ngettext("\n%(num)d package added in total.", "\n%(num)d packages added in total.", pkgs) % {"num": pkgs})
        # ensure that the changes get pushed out to disk
        self.filesdb.sync()
        # This acts as a check that the version has been correctly added and synced to disk
        ctx.ui.info(_("Done rebuilding FilesDB (version: %s)") % self.filesdb["version"])

    def __check_filesdb_old(self):
        """Sets valid self.files_db reference and returns whether the underlying db needs to be rebuilt."""
        # whether or not we need to rebuild the FilesDB
        needs_rebuild = False

        if isinstance(self.filesdb, shelve.DbfilenameShelf):
            # the db has already been correctly initialised
            return needs_rebuild

        # We don't know the db type by default
        db_type = "?"

        files_db = os.path.join(ctx.config.info_dir(), ctx.const.files_db)

        if os.path.exists(files_db):
            # check the kind of db
            db_type = dbm.whichdb(files_db)
            if db_type != "dbm.gnu":
                if not os.access(files_db, os.W_OK):
                    ctx.ui.debug("Cannot write to type %s database cache %s, ignoring." % (db_type, files_db))
                    return needs_rebuild
                else:
                    ctx.ui.debug("Incompatible type %s database cache %s found, needs_rebuild = True" % (db_type, files_db))
                    needs_rebuild = True

        if not os.path.exists(files_db):
            flag = "n"
            ctx.ui.debug("No database cache %s found, needs_rebuild = True" % (files_db))
            needs_rebuild = True
        elif os.access(files_db, os.W_OK):
            flag = "w"
        else:
            flag = "r"
            ctx.ui.debug("Type %s database cache %s is read-only." % (db_type, files_db))

        # At this point, we _should_ be able to _open_ the file.
        # The only remaining question is whether the pickle protocol version is correct
        try:
            # NOTE: This will use gdbm format db files by default
            self.filesdb = shelve.open(files_db, flag, protocol=FILESDB_PICKLE_PROTOCOL_VERSION)
        except:
             ctx.ui.debug("shelve.open(files_db=%s, flag=%s, protocol=%s) failed, needs_rebuild = True"
                           % (files_db, flag, FILESDB_PICKLE_PROTOCOL_VERSION))
             needs_rebuild = True
             return needs_rebuild

        # Check if self.filesdb has a version key
        has_version = True
        version = 0
        try:
            version = self.filesdb["version"]
        except:
            has_version = False

        # At this point, either:
        #  has_version is True and version != 0,
        #   XOR
        #  has_version is False and version == 0

        if flag != "r":
            if not has_version or version != FILESDB_FORMAT_VERSION:
                ctx.ui.debug("Incompatible type %s database cache %s found (version: (%s, %s), expected (%s, %s)), needs_rebuild = True" % (db_type, files_db, has_version, version, True, FILESDB_FORMAT_VERSION))
                needs_rebuild = True

        # False unless the logic above caused it to be toggled to True
        return needs_rebuild

