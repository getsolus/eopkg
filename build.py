import glob
import inspect
import os
import shutil
from os.path import join as path

from setuptools.command.build import build
from setuptools.command.install import install

IN_FILES = ("eopkg.xml.in",)
PROJECT = "pisi"
MIMEFILE_DIR = "usr/share/mime/packages"

PO_DIR = path(PROJECT, "data", "po")
LOCALE_DIR = path(PROJECT, "data", "locale")
POTFILE = path(PO_DIR, "pisi.pot")


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


class Install(install):
    def run(self):
        install.run(self)
        self.installi18n()
        self.installdoc()
        self.generateConfigFile()

    def installi18n(self):
        for name in os.listdir("po"):
            if not name.endswith(".po"):
                continue
            lang = name[:-3]
            print("Installing '%s' translations..." % lang)
            os.popen("msgfmt po/%s.po -o po/%s.mo" % (lang, lang))
            if not self.root:
                self.root = "/"
            destpath = path(self.root, "usr/share/locale/%s/LC_MESSAGES" % lang)
            if not os.path.exists(destpath):
                os.makedirs(destpath)
            shutil.copy("po/%s.mo" % lang, path(destpath, "pisi.mo"))

    def installdoc(self):
        destpath = path(self.root, "usr/share/doc/pisi")
        if not os.path.exists(destpath):
            os.makedirs(destpath)
        os.chdir("doc")
        for pdf in glob.glob("*.pdf"):
            print("Installing", pdf)
            # shutil.copy(pdf, path(destpath, pdf))
        os.chdir("..")

    def generateConfigFile(self):
        import pisi.configfile

        destpath = path(self.root, "usr/share/defaults/eopkg/")
        if not os.path.exists(destpath):
            os.makedirs(destpath)

        confFile = path(destpath, "eopkg.conf")
        if os.path.isfile(confFile):  # Don't overwrite existing eopkg.conf
            return

        eopkgconf = open(confFile, "w")

        klasses = inspect.getmembers(pisi.configfile, inspect.isclass)
        defaults = [klass for klass in klasses if klass[0].endswith("Defaults")]

        for d in defaults:
            section_name = d[0][: -len("Defaults")].lower()
            eopkgconf.write("[%s]\n" % section_name)

            section_members = [
                m
                for m in inspect.getmembers(d[1])
                if not m[0].startswith("__") and not m[0].endswith("__")
            ]

            for member in section_members:
                if member[1] == None or member[1] == "":
                    eopkgconf.write("# %s = %s\n" % (member[0], member[1]))
                else:
                    eopkgconf.write("%s = %s\n" % (member[0], member[1]))
            eopkgconf.write("\n")
