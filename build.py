import glob
import inspect
import os
from os.path import join as path
import sys
from setuptools.command.build import build


PROJECT = "pisi"

DATA_DIR = path(PROJECT, "data")

PO_DIR = path(DATA_DIR, "po")
LOCALE_DIR = path(DATA_DIR, "locale")
POTFILE = path(PO_DIR, "pisi.pot")

CONF_FILE = path(DATA_DIR, "eopkg.conf")


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
            dir = path(LOCALE_DIR, item[:-3], "LC_MESSAGES")
            os.makedirs(dir, exist_ok=True)
            self.spawn(
                [
                    "msgfmt",
                    path(PO_DIR, item),
                    "-o",
                    path(dir, PROJECT + ".mo"),
                ]
            )

    def generate_config_file(self):
        sys.path.append(".")
        import pisi

        conffile = open(CONF_FILE, "w")

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
