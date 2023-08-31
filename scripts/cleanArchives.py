# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, 2017-Present Solus Developers
# SPDX-License-Identifier: GPL-2.0-or-later

import os
import sys

import pisi.uri
import pisi.specfile


def scanPSPEC(folder):
    packages = []
    for root, dirs, files in os.walk(folder):
        if "pspec.xml" in files:
            packages.append(root)
        # dont walk into the versioned stuff
        if ".svn" in dirs:
            dirs.remove(".svn")
    return packages


def cleanArchives(file):
    try:
        os.remove(file)
    except OSError:
        print("Permission denied...")


if __name__ == "__main__":
    try:
        packages = scanPSPEC(sys.argv[1])
    except:
        print("Usage: cleanArchives.py path2repo")
        sys.exit(1)

    if "--dry-run" in sys.argv:
        clean = False
    elif "--clean" in sys.argv:
        clean = True
    else:
        sys.exit(0)

    files = []
    for package in packages:
        spec = pisi.specfile.SpecFile()
        spec.read(os.path.join(package, "pspec.xml"))

        URI = pisi.uri.URI(spec.source.archive.uri)
        files.append(URI.filename())

    archiveFiles = os.listdir("/var/cache/eopkg/archives/")
    unneededFiles = [x for x in archiveFiles if x not in files]

    for i in unneededFiles:
        if not clean:
            print(("/var/cache/eopkg/archives/%s" % i))
        else:
            cleanArchives("/var/cache/eopkg/archives/%s" % i)
