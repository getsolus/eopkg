# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

# Generic functions for common usage of pisitools #

# Standart Python Modules
import os
import glob

from pisi import translate as _

# Pisi Modules
import pisi.context as ctx

# ActionsAPI Modules
import pisi.actionsapi
from pisi.actionsapi.shelltools import *


class FileError(pisi.actionsapi.Error):
    def __init__(self, value=""):
        pisi.actionsapi.Error.__init__(self, value)
        self.value = value
        ctx.ui.error(value)


class ArgumentError(pisi.actionsapi.Error):
    def __init__(self, value=""):
        pisi.actionsapi.Error.__init__(self, value)
        self.value = value
        ctx.ui.error(value)


def executable_insinto(destinationDirectory, *sourceFiles):
    """insert a executable file into destinationDirectory"""

    if not sourceFiles or not destinationDirectory:
        raise ArgumentError(_("Insufficient arguments."))

    if not can_access_directory(destinationDirectory):
        makedirs(destinationDirectory)

    for sourceFile in sourceFiles:
        sourceFileGlob = glob.glob(sourceFile)
        if len(sourceFileGlob) == 0:
            raise FileError(_('No executable file matched pattern "%s".') % sourceFile)

        for source in sourceFileGlob:
            # FIXME: use an internal install routine for these
            system(
                "install -m0755 -o root -g root %s %s" % (source, destinationDirectory)
            )


def readable_insinto(destinationDirectory, *sourceFiles):
    """inserts file list into destinationDirectory"""

    if not sourceFiles or not destinationDirectory:
        raise ArgumentError(_("Insufficient arguments."))

    if not can_access_directory(destinationDirectory):
        makedirs(destinationDirectory)

    for sourceFile in sourceFiles:
        sourceFileGlob = glob.glob(sourceFile)
        if len(sourceFileGlob) == 0:
            raise FileError(_('No file matched pattern "%s".') % sourceFile)

        for source in sourceFileGlob:
            system('install -m0644 "%s" %s' % (source, destinationDirectory))


def lib_insinto(sourceFile, destinationDirectory, permission=0o644):
    """inserts a library fileinto destinationDirectory with given permission"""

    if not sourceFile or not destinationDirectory:
        raise ArgumentError(_("Insufficient arguments."))

    if not can_access_directory(destinationDirectory):
        makedirs(destinationDirectory)

    if os.path.islink(sourceFile):
        os.symlink(
            os.path.realpath(sourceFile), os.path.join(destinationDirectory, sourceFile)
        )
    else:
        system("install -m0%o %s %s" % (permission, sourceFile, destinationDirectory))
