import glob
import inspect
import os
from os.path import join as path
import sys
from setuptools.command.build import build


PROJECT = "pisi"

DATA_DIR = path(PROJECT, "data")
CONF_FILE = path(DATA_DIR, "eopkg.conf")

PO_DIR = "po"
POTFILE = path(PO_DIR, "pisi.pot")

DIST_DIR = "dist"
MAN_DIR = path(DIST_DIR, "man")


def source_files():
    files = []
    for root, dirs, filenames in os.walk(PROJECT):
        files.extend(path(root, f) for f in filenames if f.endswith(".py"))
    return files


class Build(build):
    def run(self):
        super().run()
        self.extract_pot()
        self.update_po()
        self.compile_mo()
        self.compile_manpage()
        self.generate_config_file()

    def extract_pot(self):
        self.spawn(["xgettext", "-L", "Python", "-o", POTFILE] + source_files())

    def update_po(self):
        for item in glob.glob("*.po", root_dir=PO_DIR):
            self.spawn(
                [
                    "msgmerge",
                    "--backup=none",
                    "--no-wrap",
                    "--sort-by-file",
                    "--update",
                    path(PO_DIR, item),
                    POTFILE,
                ]
            )

    def compile_mo(self):
        for item in glob.glob("*.po", root_dir=PO_DIR):
            dir = path(self._locale_dir(), item[:-3], "LC_MESSAGES")
            os.makedirs(dir, exist_ok=True)
            self.spawn(
                [
                    "msgfmt",
                    path(PO_DIR, item),
                    "-o",
                    path(dir, PROJECT + ".mo"),
                ]
            )

    def compile_manpage(self):
        try:
            for page in glob.glob("*.md", root_dir=MAN_DIR):
                # strip the .md suffix
                man_page = '.'.join(page.split('.')[:-1])
                # Example: `pandoc --standalone --to man dist/man/eopkg.1.md -o dist/man/eopkg.1`
                self.spawn(["pandoc", "--standalone", "--to", "man", path(MAN_DIR, page), "-o", path(MAN_DIR, man_page)])
        except Exception as e:
            # It's not that important if we didn't manage
            # to build a manpage. Just warn the user.
            print("Failed to build man pages:", e)

    def generate_config_file(self):
        sys.path.append(".")
        import pisi

        conffile = open(path(self.build_lib, CONF_FILE), "w")

        klasses = inspect.getmembers(pisi.configfile, inspect.isclass)
        defaults = [klass for klass in klasses if klass[0].endswith("Defaults")]
        for d in defaults:
            section_name = d[0][: -len("Defaults")].lower()
            conffile.write("[%s]\n" % section_name)

            section_members = [
                m
                for m in inspect.getmembers(d[1])
                if not m[0].startswith("__") and not m[0].endswith("__")
            ]
            for member in section_members:
                if not member[1]:
                    conffile.write("# ")
                conffile.write("%s = %s\n" % (member[0], member[1]))
            conffile.write("\n")

    def _locale_dir(self):
        return path(self.build_lib, DATA_DIR, "locale")
