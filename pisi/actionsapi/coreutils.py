# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, 2017-Present Solus Developers
# SPDX-License-Identifier: GPL-2.0-or-later

# Standard Python Modules
import re
import sys


from itertools import count

from itertools import filterfalse

# ActionsAPI
import pisi.actionsapi


def cat(filename):
    return file(filename)


class grep:
    """keep only lines that match the regexp"""

    def __init__(self, pat, flags=0):
        self.fun = re.compile(pat, flags).match

    def __ror__(self, input):
        return filter(self.fun, input)


class tr:
    """apply arbitrary transform to each sequence element"""

    def __init__(self, transform):
        self.tr = transform

    def __ror__(self, input):
        return map(self.tr, input)


class printto:
    """print sequence elements one per line"""

    def __init__(self, out=sys.stdout):
        self.out = out

    def __ror__(self, input):
        for line in input:
            print(line, file=self.out)


printlines = printto(sys.stdout)


class terminator:
    def __init__(self, method):
        self.process = method

    def __ror__(self, input):
        return self.process(input)


aslist = terminator(list)
asdict = terminator(dict)
astuple = terminator(tuple)
join = terminator("".join)
enum = terminator(enumerate)


class sort:
    def __ror__(self, input):
        ll = list(input)
        ll.sort()
        return ll


sort = sort()


class uniq:
    def __ror__(self, input):
        for i in input:
            try:
                if i == prev:
                    continue
            except NameError:
                pass
            prev = i
            yield i


uniq = uniq()
