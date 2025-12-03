# SPDX-FileCopyrightText: 2024 Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

"""This module provides utility functions for usr merged systems."""

import os.path
import pisi.context as ctx
import pisi.util

from pisi.files import FileInfo


def _islink(path):
    return os.path.islink(pisi.util.join_path(ctx.config.dest_dir(), path))


def is_usr_merged(path):
    """
    Check if the given path is usr merged by symlink.

    :param path: Path to check. Must be relative to the destination directory.
    :return: Boolean indicating if the file has been usr merged.
    """
    components = normpath(path).split('/')

    if components[0] not in ['bin', 'sbin', 'lib', 'lib32', 'lib64']:
        return False

    for i, _ in enumerate(components[:-1]):
        if _islink(os.path.join(*components[0:i + 1])):
            return True

    return False


def is_usr_merged_duplicate(files, path):
    """
    Check if the given path is usr merged *and* a duplicate of an existing file.
    All paths must be relative to the destination directory.

    :param files: List of files to search in.
    :param path: Path to check.
    :return: Boolean indicating if the file is usr merged and a duplicate.
    """
    if not is_usr_merged(path):
        return False

    if len(files) > 0 and isinstance(files[0], FileInfo):
        files = [f.path for f in files]

    return usr_merged_path(path) in files


def usr_merged_path(path):
    """
    Return the usr merged path equivalent of the given path.

    :param path: Path to check. Must be relative to the destination directory.
    :return: Usr-merged equivalent path.
    """
    return os.path.normpath(os.path.join('usr', path))

def normpath(path):
    """
    Normalize the given path.

    Normalize the path by removing any relative ('..', '.') and
    absolute ('/', '//', etc.) path components.
    The returned path is always relative.

    :param path: Path to normalize. Must be relative to the destination directory.
    :return: Normalized path.
    """
    norm = os.path.normpath(os.path.join('/', path)).lstrip('/')
    if norm != path:
        ctx.ui.debug("normpath: %s -> %s" % (path, norm))

    return norm
