# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, 2017-Present Solus Developers
# SPDX-License-Identifier: GPL-2.0-or-later

import os
import glob
import pisi
import pisi.util as util
from pisi.version import Version
from pisi.delta import create_delta_package


def minsandmaxes():
    packages = [
        os.path.basename(x).split(".eopkg")[0]
        for x in set(glob.glob("*.eopkg")) - set(glob.glob("*.delta.eopkg"))
    ]

    versions = {}
    for file in packages:
        name, version = util.parse_package_name(file)
        versions.setdefault(name, []).append(Version(version))

    mins = {}
    maxs = {}
    for pkg in list(versions.keys()):
        mins[pkg] = min(versions[pkg])
        maxs[pkg] = max(versions[pkg])

    return mins, maxs


if __name__ == "__main__":
    mi, ma = minsandmaxes()
    for pkg in list(mi.keys()):
        old_pkg = "%s-%s.eopkg" % (pkg, str(mi[pkg]))
        new_pkg = "%s-%s.eopkg" % (pkg, str(ma[pkg]))
        name, version = util.parse_package_name(pkg)

        if not old_pkg == new_pkg:
            # skip if same
            if not os.path.exists(
                "%s-%s-%s.delta.eopkg" % (name, str(mi[pkg].build), str(ma[pkg].build))
            ):
                # skip if delta exists
                print(
                    (
                        "%s --> Min: %s Max: %s \n %s-%s-%s.delta.eopkg"
                        % (
                            pkg,
                            old_pkg,
                            new_pkg,
                            name,
                            str(mi[pkg].build),
                            str(ma[pkg].build),
                        )
                    )
                )
                create_delta_package(old_pkg, new_pkg)
