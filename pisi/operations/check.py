# -*- coding: utf-8 -*-
#
# Copyright (C) 2008 - 2011, TUBITAK/UEKAE
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free
# Software Foundation; either version 2 of the License, or (at your option)
# any later version.
#
# Please read the COPYING file.

import os
import pisi
import pisi.context as ctx

from pisi import translate as _

def file_corrupted(pfile):
    path = os.path.join(ctx.config.dest_dir(), pfile.path)
    if os.path.islink(path):
        if pisi.util.sha1_data(pisi.util.read_link(path)) != pfile.hash:
            return True
    else:
        try:
            if pisi.util.sha1_file(path) != pfile.hash:
                return True
        except pisi.util.FilePermissionDeniedError, e:
            raise e
        except pisi.util.FileNotFoundError, e:
            raise e
    return False


# These guys will change due to depmod calls.
_blessed_kernel_borks = [
    "modules.alias",
    "modules.alias.bin",
    "modules.dep",
    "modules.dep.bin",
    "modules.symbols",
    "modules.symbols.bin",
]


def ignorance_is_bliss(f):
    """ Too many complaints about things that are missing. """
    p = f
    if not p.startswith("/"):
        p = "/{}".format(f)

    pbas = os.path.basename(p)
    p = p.replace("/lib64/", "/lib/")

    # Ignore kernel depmod changes?
    if p.startswith("/lib/modules"):
        if pbas in _blessed_kernel_borks:
            return True

    # Running eopkg as root will mutate .pyc files. Ignore them.
    if p.endswith(".pyc"):
        return True


def check_files(files, check_config=False):
    results = {
                'missing'   :   [],
                'corrupted' :   [],
                'denied'    :   [],
                'config'    :   [],
              }

    for f in files:
        if not check_config and f.type == "config":
            continue
        if not f.hash:
            continue
        if ignorance_is_bliss(f.path):
            continue

        is_file_corrupted = False

        path = os.path.join(ctx.config.dest_dir(), f.path)
        try:
            is_file_corrupted = file_corrupted(f)

        except pisi.util.FilePermissionDeniedError, e:
            # Can't read file, probably because of permissions, skip
            results['denied'].append(f.path)
        
        except pisi.util.FileNotFoundError, e:
            # Shipped file doesn't exist on the system
            results['missing'].append(f.path)

        else:
            if is_file_corrupted:
                # Detect file type
                if f.type == "config":
                    results['config'].append(f.path)
                else:
                    results['corrupted'].append(f.path)

    return results

def check_config_files(package):
    config_files = pisi.db.installdb.InstallDB().get_config_files(package)
    return check_files(config_files, True)

def check_package_files(package):
    files = pisi.db.installdb.InstallDB().get_files(package).list
    return check_files(files)

def check_package(package, config=False):
    if config:
        return check_config_files(package)
    else:
        return check_package_files(package)
