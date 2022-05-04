# -*- coding: utf-8 -*-
#
# Copyright (C) 2005-2010 TUBITAK/UEKAE
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free
# Software Foundation; either version 2 of the License, or (at your option)
# any later version.
#
# Please read the COPYING file.

# standard python modules
import os
import glob

from pisi import translate as _

# Pisi Modules
import pisi.context as ctx

# ActionsAPI Modules
import pisi.actionsapi
import pisi.actionsapi.get as get
from pisi.actionsapi.shelltools import system
from pisi.actionsapi.shelltools import can_access_file
from pisi.actionsapi.shelltools import export
from pisi.actionsapi.shelltools import unlink
from pisi.actionsapi.shelltools import unlinkDir

class ConfigureError(pisi.actionsapi.Error):
    def __init__(self, value=''):
        pisi.actionsapi.Error.__init__(self, value)
        self.value = value
        ctx.ui.error(value)

class MakeError(pisi.actionsapi.Error):
    def __init__(self, value=''):
        pisi.actionsapi.Error.__init__(self, value)
        self.value = value
        ctx.ui.error(value)

class InstallError(pisi.actionsapi.Error):
    def __init__(self, value=''):
        pisi.actionsapi.Error.__init__(self, value)
        self.value = value
        ctx.ui.error(value)

def configure(parameters = ''):
    '''configure source with given parameters.'''
    export('PERL_MM_USE_DEFAULT', '1')
    if can_access_file('Build.PL'):
        if system('perl Build.PL installdirs=vendor destdir=%s' % get.installDIR()):
            raise ConfigureError, _('Configure failed.')
    else:
        if system('perl Makefile.PL %s PREFIX=/usr INSTALLDIRS=vendor DESTDIR=%s' % (parameters, get.installDIR())):
            raise ConfigureError, _('Configure failed.')

def make(parameters = ''):
    '''make source with given parameters.'''
    if can_access_file('Makefile'):
        if system('make %s' % parameters):
            raise MakeError, _('Make failed.')
    else:
        if system('perl Build %s' % parameters):
            raise MakeError, _('perl build failed.')

def install(parameters = 'install'):
    '''install source with given parameters.'''
    if can_access_file('Makefile'):
        if system('make %s' % parameters):
            raise InstallError, _('Make failed.')
    else:
        if system('perl Build install'):
            raise MakeError, _('perl install failed.')

    removePacklist()
    removePodfiles()

def removePacklist(path = 'usr/lib/perl5/'):
    ''' cleans .packlist file from perl packages '''
    full_path = '%s/%s' % (get.installDIR(), path)
    for root, dirs, files in os.walk(full_path):
        for packFile in files:
            if packFile == ".packlist":
                if can_access_file('%s/%s' % (root, packFile)):
                    unlink('%s/%s' % (root, packFile))
                    removeEmptydirs(root)

def removePodfiles(path = 'usr/lib/perl5/'):
    ''' cleans *.pod files from perl packages '''
    full_path = '%s/%s' % (get.installDIR(), path)
    for root, dirs, files in os.walk(full_path):
        for packFile in files:
            if packFile.endswith(".pod"):
                if can_access_file('%s/%s' % (root, packFile)):
                    unlink('%s/%s' % (root, packFile))
                    removeEmptydirs(root)

def removeEmptydirs(d):
    ''' remove empty dirs from perl package if exists after deletion .pod and .packlist files '''
    if not os.listdir(d) and not d == get.installDIR():
        unlinkDir(d)
        d = d[:d.rfind("/")]
        removeEmptydirs(d)
