# -*- coding: utf-8 -*-
#
# Copyright (C) 2010 TUBITAK/UEKAE
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free
# Software Foundation; either version 2 of the License, or (at your option)
# any later version.
#
# Please read the COPYING file.

import glob
from pisi import translate as _

# Pisi Modules
import pisi.context as ctx

# ActionsAPI Modules
import pisi.actionsapi

# ActionsAPI Modules
from pisi.actionsapi import get
from pisi.actionsapi import cmaketools
from pisi.actionsapi import shelltools

basename = "qt4"

prefix = "/%s" % get.defaultprefixDIR()
libdir = "%s/lib" % prefix
bindir = "%s/bin" % prefix
datadir = "%s/share/%s" % (prefix, basename)
includedir = "%s/include" % prefix
docdir = "/%s/%s" % (get.docDIR(), basename)
examplesdir = "%s/%s/examples" % (libdir, basename)
demosdir = "%s/%s/demos" % (libdir, basename)
importdir = "%s/%s/imports" % (libdir, basename)
plugindir = "%s/%s/plugins" % (libdir, basename)
translationdir = "%s/translations" % datadir
sysconfdir= "/etc"
qmake = "%s/qmake" % bindir

class ConfigureError(pisi.actionsapi.Error):
    def __init__(self, value=''):
        pisi.actionsapi.Error.__init__(self, value)
        self.value = value
        ctx.ui.error(value)

def configure(projectfile='', parameters='', installPrefix=prefix):
    if projectfile != '' and not shelltools.can_access_file(projectfile):
        raise ConfigureError(_("Project file '%s' not found.") % projectfile)

    profiles = glob.glob("*.pro")
    if len(profiles) > 1 and projectfile == '':
        raise ConfigureError(_("It seems there are more than one .pro file, you must specify one. (Possible .pro files: %s)") % ", ".join(profiles))

    shelltools.system("%s -makefile %s PREFIX='%s' QMAKE_CFLAGS+='%s' QMAKE_CXXFLAGS+='%s' %s" % (qmake, projectfile, installPrefix, get.CFLAGS(), get.CXXFLAGS(), parameters))

def make(parameters=''):
    cmaketools.make(parameters)

def install(parameters='', argument='install'):
    cmaketools.install('INSTALL_ROOT="%s" %s' % (get.installDIR(), parameters), argument)

