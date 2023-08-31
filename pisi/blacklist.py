# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, 2017-Present Solus Developers
# SPDX-License-Identifier: GPL-2.0-or-later

import os
import fnmatch

import pisi.db


def exclude_from(packages, exfrom):
    if not os.path.exists(exfrom):
        return packages

    patterns = []
    if os.path.exists(exfrom):
        for line in open(exfrom, "r").readlines():
            if not line.startswith("#") and not line == "\n":
                patterns.append(line.strip())
        if patterns:
            return exclude(packages, patterns)

    return packages


def exclude(packages, patterns):
    packages = set(packages)
    componentdb = pisi.db.componentdb.ComponentDB()

    for pattern in patterns:
        # match pattern in package names
        match = fnmatch.filter(packages, pattern)
        packages = packages - set(match)

        if not match:
            # match pattern in component names
            for compare in fnmatch.filter(componentdb.list_components(), pattern):
                packages = packages - set(
                    componentdb.get_union_packages(compare, walk=True)
                )

    return list(packages)
