# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

"""supports globs in sourceFile arguments"""


# Standart Python Modules
import os
import glob
import sys
import fileinput
import re
import filecmp

from pisi import translate as _

# Pisi Modules
import pisi.context as ctx
from pisi.util import join_path, remove_prefix, uncompress

# ActionsAPI Modules
import pisi.actionsapi
import pisi.actionsapi.get as get
from pisi.actionsapi.pisitoolsfunctions import *
from pisi.actionsapi.shelltools import *

from pisi.actionsapi import error


def dobin(sourceFile, destinationDirectory="/usr/bin"):
    """insert a executable file into /bin or /usr/bin"""
    """ example call: pisitools.dobin("bin/xloadimage", "/bin", "xload") """
    executable_insinto(join_path(get.installDIR(), destinationDirectory), sourceFile)


def dodir(destinationDirectory):
    """creates a directory tree"""
    makedirs(join_path(get.installDIR(), destinationDirectory))


def dodoc(*sourceFiles, **kw):
    """inserts the files in the list of files into /usr/share/doc/PACKAGE"""
    destDir = kw.get("destDir", get.srcNAME())
    readable_insinto(join_path(get.installDIR(), get.docDIR(), destDir), *sourceFiles)


def doexe(sourceFile, destinationDirectory):
    """insert a executable file into destination directory"""

    """ example call: pisitools.doexe("kde-3.4.sh", "/etc/X11/Sessions")"""
    executable_insinto(join_path(get.installDIR(), destinationDirectory), sourceFile)


def dohtml(*sourceFiles, **kw):
    """inserts the files in the list of files into /usr/share/doc/PACKAGE/html"""

    """ example call: pisitools.dohtml("doc/doxygen/html/*")"""
    destDir = kw.get("destDir", get.srcNAME())
    destinationDirectory = join_path(get.installDIR(), get.docDIR(), destDir, "html")

    if not can_access_directory(destinationDirectory):
        makedirs(destinationDirectory)

    allowed_extensions = [".png", ".gif", ".html", ".htm", ".jpg", ".css", ".js"]
    disallowed_directories = ["CVS", ".git", ".svn", ".hg"]

    for sourceFile in sourceFiles:
        sourceFileGlob = glob.glob(sourceFile)
        if len(sourceFileGlob) == 0:
            raise FileError(_('No file matched pattern "%s"') % sourceFile)

        for source in sourceFileGlob:
            if (
                os.path.isfile(source)
                and os.path.splitext(source)[1] in allowed_extensions
            ):
                system('install -m0644 "%s" %s' % (source, destinationDirectory))
            if (
                os.path.isdir(source)
                and os.path.basename(source) not in disallowed_directories
            ):
                eraser = os.path.split(source)[0]
                for root, dirs, files in os.walk(source):
                    newRoot = remove_prefix(eraser, root)
                    for sourcename in files:
                        if os.path.splitext(sourcename)[1] in allowed_extensions:
                            makedirs(join_path(destinationDirectory, newRoot))
                            system(
                                "install -m0644 %s %s"
                                % (
                                    join_path(root, sourcename),
                                    join_path(
                                        destinationDirectory, newRoot, sourcename
                                    ),
                                )
                            )


def doinfo(*sourceFiles):
    """inserts the into files in the list of files into /usr/share/info"""
    readable_insinto(join_path(get.installDIR(), get.infoDIR()), *sourceFiles)


def dolib(sourceFile, destinationDirectory="/usr/lib"):
    """insert the library into /usr/lib"""

    """example call: pisitools.dolib("libz.a")"""
    """example call: pisitools.dolib("libz.so")"""
    sourceFile = join_path(os.getcwd(), sourceFile)
    destinationDirectory = join_path(get.installDIR(), destinationDirectory)

    lib_insinto(sourceFile, destinationDirectory, 0o755)


def dolib_a(sourceFile, destinationDirectory="/usr/lib"):
    """insert the static library into /usr/lib with permission 0644"""

    """example call: pisitools.dolib_a("staticlib/libvga.a")"""
    sourceFile = join_path(os.getcwd(), sourceFile)
    destinationDirectory = join_path(get.installDIR(), destinationDirectory)

    lib_insinto(sourceFile, destinationDirectory, 0o644)


def dolib_so(sourceFile, destinationDirectory="/usr/lib"):
    """insert the dynamic library into /usr/lib with permission 0755"""

    """example call: pisitools.dolib_so("pppd/plugins/minconn.so")"""
    sourceFile = join_path(os.getcwd(), sourceFile)
    destinationDirectory = join_path(get.installDIR(), destinationDirectory)

    lib_insinto(sourceFile, destinationDirectory, 0o755)


def doman(*sourceFiles):
    """inserts the man pages in the list of files into /usr/share/man/"""

    """example call: pisitools.doman("man.1", "pardus.*")"""
    manDIR = join_path(get.installDIR(), get.manDIR())
    if not can_access_directory(manDIR):
        makedirs(manDIR)

    for sourceFile in sourceFiles:
        sourceFileGlob = glob.glob(sourceFile)
        if len(sourceFileGlob) == 0:
            raise FileError(_('No file matched pattern "%s"') % sourceFile)

        for source in sourceFileGlob:
            compressed = source.endswith("gz") and source
            if compressed:
                source = source[:-3]
            try:
                pageName, pageDirectory = (
                    source[: source.rindex(".")],
                    source[source.rindex(".") + 1 :],
                )
            except ValueError:
                error(_("ActionsAPI [doman]: Wrong man page file: %s") % (source))

            manPDIR = join_path(manDIR, "/man%s" % pageDirectory)
            makedirs(manPDIR)
            if not compressed:
                system("install -m0644 %s %s" % (source, manPDIR))
            else:
                uncompress(compressed, targetDir=manPDIR)


def domo(sourceFile, locale, destinationFile, localeDirPrefix="/usr/share/locale"):
    """inserts the mo files in the list of files into /usr/share/locale/LOCALE/LC_MESSAGES"""

    """example call: pisitools.domo("po/tr.po", "tr", "pam_login.mo")"""

    system("msgfmt %s" % sourceFile)
    makedirs("%s%s/%s/LC_MESSAGES/" % (get.installDIR(), localeDirPrefix, locale))
    move(
        "messages.mo",
        "%s%s/%s/LC_MESSAGES/%s"
        % (get.installDIR(), localeDirPrefix, locale, destinationFile),
    )


def domove(sourceFile, destination, destinationFile=""):
    """moves sourceFile/Directory into destinationFile/Directory"""

    """ example call: pisitools.domove("/usr/bin/bash", "/bin/bash")"""
    """ example call: pisitools.domove("/usr/bin/", "/usr/sbin")"""
    makedirs(join_path(get.installDIR(), destination))

    sourceFileGlob = glob.glob(join_path(get.installDIR(), sourceFile))
    if len(sourceFileGlob) == 0:
        raise FileError(
            _("No file matched pattern \"%s\". 'domove' operation failed.") % sourceFile
        )

    for filePath in sourceFileGlob:
        if not destinationFile:
            move(
                filePath,
                join_path(
                    get.installDIR(), join_path(destination, os.path.basename(filePath))
                ),
            )
        else:
            move(
                filePath,
                join_path(get.installDIR(), join_path(destination, destinationFile)),
            )


def rename(sourceFile, destinationFile):
    """renames sourceFile as destinationFile"""

    """ example call: pisitools.rename("/usr/bin/bash", "bash.old") """
    """ the result of the previous example would be "/usr/bin/bash.old" """

    baseDir = os.path.dirname(sourceFile)

    try:
        os.rename(
            join_path(get.installDIR(), sourceFile),
            join_path(get.installDIR(), baseDir, destinationFile),
        )
    except OSError as e:
        error(_("ActionsAPI [rename]: %s: %s") % (e, sourceFile))


def dosed(sourceFiles, findPattern, replacePattern=""):
    """replaces patterns in sourceFiles"""

    """ example call: pisitools.dosed("/etc/passwd", "caglar", "cem")"""
    """ example call: pisitools.dosed("/etc/passwd", "caglar")"""
    """ example call: pisitools.dosed("/etc/pass*", "caglar")"""
    """ example call: pisitools.dosed("Makefile", "(?m)^(HAVE_PAM=.*)no", r"\1yes")"""

    backupExtension = ".pisi-backup"
    sourceFilesGlob = glob.glob(sourceFiles)

    # if there is no match, raise exception
    if len(sourceFilesGlob) == 0:
        raise FileError(
            _("No such file matching pattern: \"%s\". 'dosed' operation failed.")
            % sourceFiles
        )

    for sourceFile in sourceFilesGlob:
        if can_access_file(sourceFile):
            backupFile = "%s%s" % (sourceFile, backupExtension)
            for line in fileinput.input(sourceFile, inplace=1, backup=backupExtension):
                # FIXME: In-place filtering is disabled when standard input is read
                line = re.sub(findPattern, replacePattern, line)
                sys.stdout.write(line)
            if can_access_file(backupFile):
                # By default, filecmp.cmp() compares two files by looking file sizes.
                # shallow=False tells cmp() to look file content.
                if filecmp.cmp(sourceFile, backupFile, shallow=False):
                    ctx.ui.warning(
                        _("dosed method has not changed file '%s'.") % sourceFile
                    )
                os.unlink(backupFile)
        else:
            raise FileError(
                _("File does not exist or permission denied: %s") % sourceFile
            )


def dosbin(sourceFile, destinationDirectory="/usr/sbin"):
    """insert a executable file into /sbin or /usr/sbin"""

    """ example call: pisitools.dobin("bin/xloadimage", "/sbin") """
    executable_insinto(join_path(get.installDIR(), destinationDirectory), sourceFile)


def dosym(sourceFile, destinationFile):
    """creates soft link between sourceFile and destinationFile"""

    """ example call: pisitools.dosym("/usr/bin/bash", "/bin/bash")"""
    makedirs(join_path(get.installDIR(), os.path.dirname(destinationFile)))

    try:
        os.symlink(sourceFile, join_path(get.installDIR(), destinationFile))
    except OSError:
        error(_("ActionsAPI [dosym]: File already exists: %s") % (destinationFile))


def insinto(destinationDirectory, sourceFile, destinationFile="", sym=True):
    """insert a sourceFile into destinationDirectory as a destinationFile with same uid/guid/permissions"""
    makedirs(join_path(get.installDIR(), destinationDirectory))

    if not destinationFile:
        sourceFileGlob = glob.glob(sourceFile)
        if len(sourceFileGlob) == 0:
            raise FileError(_('No file matched pattern "%s".') % sourceFile)

        for filePath in sourceFileGlob:
            if can_access_file(filePath):
                copy(
                    filePath,
                    join_path(
                        get.installDIR(),
                        join_path(destinationDirectory, os.path.basename(filePath)),
                    ),
                    sym,
                )
    else:
        copy(
            sourceFile,
            join_path(
                get.installDIR(), join_path(destinationDirectory, destinationFile)
            ),
            sym,
        )


def newdoc(sourceFile, destinationFile):
    """inserts a sourceFile into /usr/share/doc/PACKAGE/ directory as a destinationFile"""
    destinationDirectory = ""  # 490
    destinationDirectory = os.path.dirname(destinationFile)
    destinationFile = os.path.basename(destinationFile)
    # Use copy instead of move or let build-install scream like file not found!
    copy(sourceFile, destinationFile)
    readable_insinto(
        join_path(
            get.installDIR(), "usr/share/doc", get.srcNAME(), destinationDirectory
        ),
        destinationFile,
    )


def newman(sourceFile, destinationFile):
    """inserts a sourceFile into /usr/share/man/manPREFIX/ directory as a destinationFile"""
    # Use copy instead of move or let build-install scream like file not found!
    copy(sourceFile, destinationFile)
    doman(destinationFile)


def remove(sourceFile):
    """removes sourceFile"""
    sourceFileGlob = glob.glob(join_path(get.installDIR(), sourceFile))
    if len(sourceFileGlob) == 0:
        raise FileError(
            _('No file matched pattern "%s". Remove operation failed.') % sourceFile
        )

    for filePath in sourceFileGlob:
        unlink(filePath)


def removeDir(destinationDirectory):
    """removes destinationDirectory and its subtrees"""
    destdirGlob = glob.glob(join_path(get.installDIR(), destinationDirectory))
    if len(destdirGlob) == 0:
        raise FileError(
            _('No directory matched pattern "%s". Remove directory operation failed.')
            % destinationDirectory
        )

    for directory in destdirGlob:
        unlinkDir(directory)
