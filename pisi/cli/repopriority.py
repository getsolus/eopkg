# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

from pathlib import Path
import os
import sys
import xml.etree.ElementTree as ET

import optparse

from pisi import translate as _

import pisi.api
import pisi.cli.command as command
import pisi.context as ctx

class RepoPriority(command.Command, metaclass=command.autocommand):
    __doc__ = _(
        """Set a repository's priority

Usage: repo-priority <repo> <priority>

<repo>: Name of repository to adjust priority
<priority>: Set the repository's priority at given position (0 is first)
"""
    )

    def __init__(self, args):
        super(RepoPriority, self).__init__(args)

    name = ("repo-priority", "rp")

    def run(self):
        if len(self.args) == 2:
            self.init()
            repo_name, repo_priority = self.args
            self.reorder_repo(repo_name, repo_priority)
        else:
            self.help()
            return

    def reorder_repo(self, repo_name, repo_priority):
        if repo_priority.isdigit() is False:
            raise pisi.Error(_("Priority needs to be a number"))

        repos_xml_file = os.path.join(ctx.config.info_dir(), ctx.const.repos)
        if not Path(repos_xml_file).is_file():
            raise pisi.Error(_("Unable to locate repository file, expected: %s") % repos_xml_file)

        tree = ET.parse(repos_xml_file)
        root = tree.getroot()

        matched_repo = None

        for subitem in root.findall('Repo'):
            name = subitem.find('Name')
            if name is not None and name.text == repo_name:
                matched_repo = subitem
                break

        if matched_repo is None:
            raise pisi.Error(_("Repository %s does not exist. Cannot reorder.") % repo_name)

        root.remove(matched_repo)
        root.insert(int(repo_priority), matched_repo)
        ET.indent(root, "    ", 0)

        try:
            tree.write(repos_xml_file)
        except IOError as e:
            raise pisi.Error(_("Failed to write to repository file"))

        ctx.ui.info(_("Repo %s reordered to position %s.") % (repo_name, repo_priority))
