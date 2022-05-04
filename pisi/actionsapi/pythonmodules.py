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
from pisi.actionsapi.shelltools import system, can_access_file, unlink, isEmpty
from pisi.actionsapi.pisitools import dodoc

class ConfigureError(pisi.actionsapi.Error):
    def __init__(self, value=''):
        pisi.actionsapi.Error.__init__(self, value)
        self.value = value
        ctx.ui.error(value)

class CompileError(pisi.actionsapi.Error):
    def __init__(self, value=''):
        pisi.actionsapi.Error.__init__(self, value)
        self.value = value
        ctx.ui.error(value)

class InstallError(pisi.actionsapi.Error):
    def __init__(self, value=''):
        pisi.actionsapi.Error.__init__(self, value)
        self.value = value
        ctx.ui.error(value)

class RunTimeError(pisi.actionsapi.Error):
    def __init__(self, value=''):
        pisi.actionsapi.Error.__init__(self, value)
        self.value = value
        ctx.ui.error(value)

def configure(parameters = '', pyVer = ''):
    '''does python setup.py configure'''
    if system('python%s setup.py configure %s' % (pyVer, parameters)):
        raise ConfigureError, _('Configuration failed.')


def compile(parameters = '', pyVer = ''):
    '''compile source with given parameters.'''
    if system('python%s setup.py build %s' % (pyVer, parameters)):
        raise CompileError, _('Make failed.')

def install(parameters = '', pyVer = ''):
    '''does python setup.py install'''
    if system('python%s setup.py install --root=%s --no-compile -O0 %s' % (pyVer, get.installDIR(), parameters)):
        raise InstallError, _('Install failed.')

    docFiles = ('AUTHORS', 'CHANGELOG', 'CONTRIBUTORS', 'COPYING*', 'COPYRIGHT',
                'Change*', 'KNOWN_BUGS', 'LICENSE', 'MAINTAINERS', 'NEWS',
                'README*', 'PKG-INFO')

    for docGlob in docFiles:
        for doc in glob.glob(docGlob):
            if not isEmpty(doc):
                dodoc(doc)

def run(parameters = '', pyVer = ''):
    '''executes parameters with python'''
    if system('python%s %s' % (pyVer, parameters)):
        raise RunTimeError, _('Running %s failed.') % parameters

def fixCompiledPy(lookInto = '/usr/lib/%s/' % get.curPYTHON()):
    ''' cleans *.py[co] from packages '''
    for root, dirs, files in os.walk('%s/%s' % (get.installDIR(),lookInto)):
        for compiledFile in files:
            if compiledFile.endswith('.pyc') or compiledFile.endswith('.pyo'):
                if can_access_file('%s/%s' % (root,compiledFile)):
                    unlink('%s/%s' % (root,compiledFile))
