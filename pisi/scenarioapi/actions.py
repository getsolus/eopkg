# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, 2017-Present Solus Developers
# SPDX-License-Identifier: GPL-2.0-or-later


class Actions:
    template = """
from pisi.actionsapi import pisitools

WorkDir = "skeleton"

def install():
    pisitools.dobin("skeleton.py")
    pisitools.rename("/usr/bin/skeleton.py", "%s")
"""

    def __init__(self, name, filepath):
        self.name = name
        self.filepath = filepath

    def write(self):
        open(self.filepath, "w").write(self.template % self.name)
