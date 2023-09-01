# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, 2017-Present Solus Developers
# SPDX-License-Identifier: GPL-2.0-or-later

"""version structure"""

from pisi import translate as _

import pisi

# Basic rule is:
# p > (no suffix) > m > rc > pre > beta > alpha
# m: milestone. this was added for OO.o
# p: patch-level
__keywords = (
    ("alpha", -5),
    ("beta", -4),
    ("pre", -3),
    ("rc", -2),
    ("m", -1),
    ("p", 1),
)


# For Python2 compatibility
def cmp(a, b):
    return (a > b) - (a < b)


class InvalidVersionError(pisi.Error):
    pass


def __make_version_item(v):
    try:
        return int(v), None
    except ValueError:
        return int(v[:-1]), v[-1]


def make_version(version):
    ver, sep, suffix = version.partition("_")
    try:
        if sep:
            # "s" is a string greater than the greatest keyword "rc"
            if "a" <= suffix <= "s":
                for keyword, value in __keywords:
                    if suffix.startswith(keyword):
                        return (
                            list(map(__make_version_item, ver.split("."))),
                            value,
                            list(
                                map(
                                    __make_version_item,
                                    suffix[len(keyword):].split("."),
                                )
                            ),
                        )
                else:
                    # Probably an invalid version string. Reset ver string
                    # to raise an exception in __make_version_item function.
                    ver = ""
            else:
                return (
                    list(map(__make_version_item, ver.split("."))),
                    0,
                    list(map(__make_version_item, suffix.split("."))),
                )

        return list(map(__make_version_item, ver.split("."))), 0, [(0, None)]

    except ValueError:
        raise InvalidVersionError(_("Invalid version string: '%s'") % version)


class Version(object):
    __slots__ = ("__version", "__version_string")

    @staticmethod
    def valid(version):
        try:
            make_version(version)
        except InvalidVersionError:
            return False
        return True

    def __init__(self, verstring):
        self.__version_string = verstring
        self.__version = make_version(verstring)

    def string(self):
        return self.__version_string

    def compare(self, ver):
        if isinstance(ver, str):
            return cmp(self.__version, make_version(ver))

        return cmp(self.__version, ver.__version)

    def __lt__(self, rhs):
        if isinstance(rhs, str):
            return self.__version < make_version(rhs)

        return self.__version < rhs.__version

    def __le__(self, rhs):
        if isinstance(rhs, str):
            return self.__version <= make_version(rhs)

        return self.__version <= rhs.__version

    def __gt__(self, rhs):
        if isinstance(rhs, str):
            return self.__version > make_version(rhs)

        return self.__version > rhs.__version

    def __ge__(self, rhs):
        if isinstance(rhs, str):
            return self.__version >= make_version(rhs)

        return self.__version >= rhs.__version

    def __eq__(self, rhs):
        if isinstance(rhs, str):
            return self.__version_string == rhs

        return self.__version_string == rhs.__version_string

    def __str__(self):
        return self.__version_string
