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

# Standard Python Modules
import os

from pisi import translate as _

# Pisi Modules
import pisi.context as ctx

# ActionsAPI Modules
import pisi.actionsapi
import pisi.actionsapi.get as get
from pisi.actionsapi.shelltools import system
from pisi.actionsapi.shelltools import can_access_file
from pisi.actionsapi.shelltools import unlink
from pisi.actionsapi.shelltools import export
from pisi.actionsapi.libtools import gnuconfig_update
from pisi.actionsapi.shelltools import isDirectory
from pisi.actionsapi.shelltools import ls
from pisi.actionsapi.pisitools import dosed
from pisi.actionsapi.pisitools import removeDir

class ConfigureError(pisi.actionsapi.Error):
    def __init__(self, value=''):
        pisi.actionsapi.Error.__init__(self, value)
        self.value = value
        ctx.ui.error(value)
        if can_access_file('config.log'):
            ctx.ui.error(_('Please attach the config.log to your bug report:\n%s/config.log') % os.getcwd())

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

class RunTimeError(pisi.actionsapi.Error):
    def __init__(self, value=''):
        pisi.actionsapi.Error.__init__(self, value)
        self.value = value
        ctx.ui.error(value)

def configure(parameters = ''):
    '''configure source with given parameters = "--with-nls --with-libusb --with-something-usefull"'''
    # Set clang as compiler if supported
    if get.canClang():
		export ("CC", "clang")
		export ("CXX", "clang++")
		
    if can_access_file('configure'):
        gnuconfig_update()

        prefix = get.emul32prefixDIR() if get.buildTYPE() == "emul32" else get.defaultprefixDIR()
        args = './configure \
                --prefix=/%s \
                --build=%s \
                --mandir=/%s \
                --infodir=/%s \
                --datadir=/%s \
                --sysconfdir=/%s \
                --localstatedir=/%s \
                --libexecdir=/%s \
                %s' % (prefix, \
                       get.HOST(), get.manDIR(), \
                       get.infoDIR(), get.dataDIR(), \
                       get.confDIR(), get.localstateDIR(), get.libexecDIR(), parameters)

        if get.buildTYPE() == "emul32":
            args += " --libdir=/usr/lib32"

        if system(args):
            raise ConfigureError(_('Configure failed.'))
    else:
        raise ConfigureError(_('No configure script found.'))

def rawConfigure(parameters = ''):
    '''configure source with given parameters = "--prefix=/usr --libdir=/usr/lib --with-nls"'''
    # Set clang as compiler if supported
    if get.canClang():
		export ("CC", "clang")
		export ("CXX", "clang++")
		    
    if can_access_file('configure'):
        gnuconfig_update()

        if system('./configure %s' % parameters):
            raise ConfigureError(_('Configure failed.'))
    else:
        raise ConfigureError(_('No configure script found.'))

def compile(parameters = ''):
    system('%s %s %s' % (get.CC(), get.CFLAGS(), parameters))

def make(parameters = ''):
    '''make source with given parameters = "all" || "doc" etc.'''
    # Set clang as compiler if supported
    if get.canClang():
		export ("CC", "clang")
		export ("CXX", "clang++")
		    
    if system('make %s %s' % (get.makeJOBS(), parameters)):
        raise MakeError(_('Make failed.'))

def fixInfoDir():
    infoDir = '%s/usr/share/info/dir' % get.installDIR()
    if can_access_file(infoDir):
        unlink(infoDir)

def fixpc():
    ''' fix .pc files in installDIR()/usr/lib32/pkgconfig'''
    path = "%s/usr/lib32/pkgconfig" % get.installDIR()
    if isDirectory(path):
        for f in ls("%s/*.pc" % path):
            dosed(f, get.emul32prefixDIR(), get.defaultprefixDIR())

def install(parameters = '', argument = 'install'):
    '''install source into install directory with given parameters'''
    # Set clang as compiler if supported
    if get.canClang():
		export ("CC", "clang")
		export ("CXX", "clang++")
		    
    args = 'make prefix=%(prefix)s/%(defaultprefix)s \
            datadir=%(prefix)s/%(data)s \
            infodir=%(prefix)s/%(info)s \
            localstatedir=%(prefix)s/%(localstate)s \
            mandir=%(prefix)s/%(man)s \
            sysconfdir=%(prefix)s/%(conf)s \
            %(parameters)s \
            %(argument)s' % {
                                'prefix': get.installDIR(),
                                'defaultprefix': get.defaultprefixDIR(),
                                'man': get.manDIR(),
                                'info': get.infoDIR(),
                                'localstate': get.localstateDIR(),
                                'conf': get.confDIR(),
                                'data': get.dataDIR(),
                                'parameters': parameters,
                                'argument':argument,
                            }

    if system(args):
        raise InstallError(_('Install failed.'))
    else:
        fixInfoDir()

    if get.buildTYPE() == "emul32":
        fixpc()
        if isDirectory("%s/emul32" % get.installDIR()): removeDir("/emul32")

def rawInstall(parameters = '', argument = 'install'):
    '''install source into install directory with given parameters = PREFIX=%s % get.installDIR()'''
    # Set clang as compiler if supported
    if get.canClang():
		export ("CC", "clang")
		export ("CXX", "clang++")
		    
    if system('make %s %s' % (parameters, argument)):
        raise InstallError(_('Install failed.'))
    else:
        fixInfoDir()

    if get.buildTYPE() == "emul32":
        fixpc()
        if isDirectory("%s/emul32" % get.installDIR()): removeDir("/emul32")

def aclocal(parameters = ''):
    '''generates an aclocal.m4 based on the contents of configure.in.'''
    if system('aclocal %s' % parameters):
        raise RunTimeError(_('Running aclocal failed.'))

def autoconf(parameters = ''):
    '''generates a configure script'''
    if system('autoconf %s' % parameters):
        raise RunTimeError(_('Running autoconf failed.'))

def autoreconf(parameters = ''):
    '''re-generates a configure script'''
    if system('autoreconf %s' % parameters):
        raise RunTimeError(_('Running autoreconf failed.'))

def automake(parameters = ''):
    '''generates a makefile'''
    if system('automake %s' % parameters):
        raise RunTimeError(_('Running automake failed.'))

def autoheader(parameters = ''):
    '''generates templates for configure'''
    if system('autoheader %s' % parameters):
        raise RunTimeError(_('Running autoheader failed.'))
