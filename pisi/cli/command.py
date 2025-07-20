# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

import optparse
import os
import sys

import pisi.api
from pisi import context as ctx
from pisi import translate as _


class autocommand(type):
    def __init__(cls, name, bases, dict):
        super(autocommand, cls).__init__(name, bases, dict)
        Command.cmd.append(cls)
        name = getattr(cls, "name", None)
        if name is None:
            raise pisi.cli.Error(_("Command lacks name"))
        longname, shortname = name

        def add_cmd(cmd):
            if cmd in Command.cmd_dict:
                raise pisi.cli.Error(_("Duplicate command %s") % cmd)
            else:
                Command.cmd_dict[cmd] = cls

        add_cmd(longname)
        if shortname:
            add_cmd(shortname)


class Command(object):
    """generic help string for any command"""

    # class variables

    cmd = []
    cmd_dict = {}

    @staticmethod
    def commands_string():
        s = ""
        l = [x.name[0] for x in Command.cmd]
        l.sort()
        for name in l:
            commandcls = Command.cmd_dict[name]
            summary = _(commandcls.__doc__).split("\n")[0]
            name = commandcls.name[0]
            if commandcls.name[1]:
                name += " (%s)" % commandcls.name[1]
            s += " %23s - %s\n" % (name, summary)
        return s

    @staticmethod
    def get_command(cmd, fail=False, args=None):
        if cmd in Command.cmd_dict:
            return Command.cmd_dict[cmd](args)

        if fail:
            raise pisi.cli.Error(_("Unrecognized command: %s") % cmd)
        else:
            return None

    # instance variabes

    def __init__(self, args=None):
        # now for the real parser
        import pisi

        self.parser = optparse.OptionParser(
            usage=getattr(self, "__doc__"),
            version="%prog " + pisi.__version__,
            formatter=PisiHelpFormatter(),
        )
        self.options()
        self.commonopts()
        (self.options, self.args) = self.parser.parse_args(args)
        if self.args:
            self.args.pop(0)  # exclude command arg

        self.process_opts()

    def commonopts(self):
        """common options"""
        p = self.parser

        group = optparse.OptionGroup(self.parser, _("general options"))

        group.add_option(
            "-D",
            "--destdir",
            action="store",
            default=None,
            help=_("Change the system root for eopkg commands"),
        )
        group.add_option(
            "-y",
            "--yes-all",
            action="store_true",
            default=False,
            help=_("Assume yes in all yes/no queries"),
        )
        # Username and password are leftovers from auth-basic support.
        # These are here (but hidden) so we can issue a deprecation warning.
        group.add_option("-u", "--username", action="store", help=optparse.SUPPRESS_HELP)
        group.add_option("-p", "--password", action="store", help=optparse.SUPPRESS_HELP)
        group.add_option(
            "-L",
            "--bandwidth-limit",
            action="store",
            default=0,
            help=_("Keep bandwidth usage under specified KB's"),
        )
        group.add_option(
            "-R",
            "--retry-attempts",
            action="store",
            default=0,
            help=_(
                "Set the max number of retry attempts in case of connection timeouts"
            ),
        )
        group.add_option(
            "-v",
            "--verbose",
            action="store_true",
            dest="verbose",
            default=False,
            help=_("Detailed output"),
        )
        group.add_option(
            "-d",
            "--debug",
            action="store_true",
            default=False,
            help=_("Show debugging information"),
        )
        group.add_option(
            "-N",
            "--no-color",
            action="store_true",
            default=False,
            help=_("Suppresses all coloring of eopkg's output"),
        )

        p.add_option_group(group)

        return p

    def options(self):
        """This is a fall back function. If the implementer module provides an
        options function it will be called"""
        pass

    def process_opts(self):
        if self.options.username or self.options.password:
            raise pisi.cli.Error(_("HTTP Basic-Auth is no longer supported. Please reconfigure your repository."))

        # make destdir absolute
        if self.options.destdir:
            d = str(self.options.destdir)
            if not os.path.exists(d):
                pisi.cli.printu(
                    _("Destination directory %s does not exist. Creating directory.\n")
                    % d
                )
                os.makedirs(d)
            self.options.destdir = os.path.realpath(d)

    def init(self, database=True, write=True):
        """initialize eopkg components"""

        if self.options:
            ui = pisi.cli.CLI(self.options.debug, self.options.verbose)
        else:
            ui = pisi.cli.CLI()

        if write and not os.access(pisi.context.config.packages_dir(), os.W_OK):
            try:
                os.execv('/usr/bin/pkexec',  ['/usr/bin/pkexec', ] + sys.argv)
            except:
                raise pisi.cli.Error(_("You have to be root for this operation."))

        pisi.api.set_userinterface(ui)
        pisi.api.set_options(self.options)

        # Disable configuration for destdir ops (ISO builds and such)
        if self.options.destdir and self.options.destdir != "/":
            pisi.api.set_can_configure(False)
        else:
            pisi.api.set_can_configure(not ctx.get_option("ignore_comar"))

    def get_name(self):
        return self.__class__.name

    def format_name(self):
        (name, shortname) = self.get_name()
        if shortname:
            return "%s (%s)" % (name, shortname)
        else:
            return name

    def help(self):
        """print help for the command"""
        print("%s: %s\n" % (self.format_name(), _(self.__doc__)))
        print(self.parser.format_option_help())

    def die(self):
        """exit program"""
        # FIXME: not called from anywhere?
        ctx.ui.error(_("Command terminated abnormally."))
        sys.exit(-1)


class PackageOp(Command):
    """Abstract package operation command"""

    def __init__(self, args):
        super(PackageOp, self).__init__(args)

    def options(self, group):
        group.add_option(
            "--ignore-dependency",
            action="store_true",
            default=False,
            help=_("Do not take dependency information into account"),
        )
        group.add_option(
            "--ignore-comar",
            action="store_true",
            default=False,
            help=_("Bypass comar configuration agent"),
        )
        group.add_option(
            "--ignore-safety",
            action="store_true",
            default=False,
            help=_("Bypass safety switch"),
        )
        group.add_option(
            "-n",
            "--dry-run",
            action="store_true",
            default=False,
            help=_("Do not perform any action, just show what would be done"),
        )

    def init(self, database=True, write=True):
        super(PackageOp, self).init(database, write)


class PisiHelpFormatter(optparse.HelpFormatter):
    def __init__(
        self, indent_increment=1, max_help_position=32, width=None, short_first=1
    ):
        optparse.HelpFormatter.__init__(
            self, indent_increment, max_help_position, width, short_first
        )

        self._short_opt_fmt = "%s"
        self._long_opt_fmt = "%s"

    def format_usage(self, usage):
        return _("usage: %s\n") % usage

    def format_heading(self, heading):
        return "%*s%s:\n" % (self.current_indent, "", heading)

    def format_option_strings(self, option):
        """Return a comma-separated list of option strings & metavariables."""
        if option.takes_value():
            short_opts = [self._short_opt_fmt % sopt for sopt in option._short_opts]
            long_opts = [self._long_opt_fmt % lopt for lopt in option._long_opts]
        else:
            short_opts = option._short_opts
            long_opts = option._long_opts

        if long_opts and short_opts:
            opt = "%s [%s]" % (short_opts[0], long_opts[0])
        else:
            opt = long_opts[0] or short_opts[0]

        if option.takes_value():
            opt += " arg"

        return opt

    def format_option(self, option):
        import textwrap

        result = []
        opts = self.option_strings[option]
        opt_width = self.help_position - self.current_indent - 2
        if len(opts) > opt_width:
            opts = "%*s%s\n" % (self.current_indent, "", opts)
            indent_first = self.help_position
        else:  # start help on same line as opts
            opts = "%*s%-*s  " % (self.current_indent, "", opt_width, opts)
            indent_first = 0
        result.append(opts)
        if option.help:
            help_text = self.expand_default(option)
            help_lines = textwrap.wrap(help_text, self.help_width)
            result.append(": %*s%s\n" % (indent_first, "", help_lines[0]))
            result.extend(
                [
                    "  %*s%s\n" % (self.help_position, "", line)
                    for line in help_lines[1:]
                ]
            )
        elif opts[-1] != "\n":
            result.append("\n")
        return "".join(result)
