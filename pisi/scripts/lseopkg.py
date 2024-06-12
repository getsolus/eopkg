#!/usr/bin/env python3
#
# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

import os
import sys
import pisi


def show_info(filename):
    metadata, files = pisi.api.info_file(filename)

    paths = [fileinfo.path for fileinfo in files.list]
    paths.sort()
    return paths


def uniq(alist):
    set = {}
    return [set.setdefault(e, e) for e in alist if e not in set]


def usage(errmsg):
    print(
        """
    Error: %s

    Usage:
      lseopkg eopkg_package.eopkg         (lists the content of package)
      lseopkg dirs eopkg_package.eopkg    (lists directories in the package for the package developer)
    """
        % (errmsg)
    )

    sys.exit(1)


def main():
    if len(sys.argv) < 2 or ("dirs" in sys.argv and len(sys.argv) < 3):
        usage("eopkg package required...")

    if sys.argv[1] == "dirs":
        dirlist = []
        for file in show_info(sys.argv[2]):
            dirlist.append(os.path.dirname(file))

        for dir in uniq(dirlist):
            print('<Path fileType="">/%s</Path>' % dir)

    elif not os.path.exists(sys.argv[1]):
        print("File %s not found" % sys.argv[1])

    else:
        for file in show_info(sys.argv[1]):
            print("/%s" % file)


if __name__ == "__main__":
    sys.exit(main())
