# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later
#
# installation database
#

import os
import re

import iksemel

# eopkg
import pisi
import pisi.context as ctx
import pisi.db.lazydb as lazydb
import pisi.dependency
import pisi.files
import pisi.util
from pisi import Error
from pisi import translate as _


class InstallDBError(pisi.Error):
    pass


class InstallInfo:
    state_map = {"i": _("installed"), "ip": _("installed-pending")}

    def __init__(self, state, version, release, distribution, time):
        self.state = state
        self.version = version
        self.release = release
        self.distribution = distribution
        self.time = time

    def one_liner(self):
        import time

        time_str = time.strftime("%d %b %Y %H:%M", self.time)
        s = "%2s|%15s|%6s|%8s|%12s" % (
            self.state,
            self.version,
            self.release,
            self.distribution,
            time_str,
        )
        return s

    def __str__(self):
        s = _("State: %s\nVersion: %s, Release: %s\n") % (
            InstallInfo.state_map[self.state],
            self.version,
            self.release,
        )
        import time

        time_str = time.strftime("%d %b %Y %H:%M", self.time)
        s += _("Distribution: %s, Install Time: %s\n") % (self.distribution, time_str)
        return s


class InstallDB(lazydb.LazyDB):
    def __init__(self):
        lazydb.LazyDB.__init__(
            self, cacheable=False, cachedir=ctx.config.packages_dir()
        )

    @property
    def lmdb_mappings(self):
        return [self.installed_db, self.rev_deps_db, self.xmls_db]

    def init(self):
        self.installed_db = self.lmdb_store.get_mapping("installed_db")
        self.rev_deps_db = self.lmdb_store.get_mapping("rev_deps_db")
        self.xmls_db = self.lmdb_store.get_mapping("installed_xmls_db")

        meta = self.lmdb_store.get_mapping("meta")
        packages_dir = ctx.config.packages_dir()

        mtime = os.path.getmtime(packages_dir) if os.path.exists(packages_dir) else 0
        cached_mtime = meta.get("mtime_idb")

        if (
            len(self.installed_db) == 0
            or len(self.xmls_db) == 0
            or cached_mtime != mtime
        ):
            if self.lmdb_store.readonly and not self.lmdb_store.use_memory:
                from pisi.db.lmdbstore import MemoryMapping

                self.installed_db = MemoryMapping()
                self.rev_deps_db = MemoryMapping()
                self.xmls_db = MemoryMapping()

            # Initial population or staleness detected
            self.installed_db.clear()
            self.rev_deps_db.clear()
            self.xmls_db.clear()

            installed_pkgs = self.__generate_installed_pkgs()
            self.installed_db.update_bulk(installed_pkgs)
            self.rev_deps_db.update_bulk(self.__generate_revdeps())
            self.xmls_db.update_bulk(self.__generate_xmls(installed_pkgs))

            if not self.lmdb_store.readonly:
                meta["mtime_idb"] = mtime

    def __generate_xmls(self, installed_pkgs):
        import gzip

        xmls = {}
        for package, ver_rel in installed_pkgs.items():
            pkg_path = os.path.join(ctx.config.packages_dir(), f"{package}-{ver_rel}")
            metadata_xml = os.path.join(pkg_path, ctx.const.metadata_xml)
            if os.path.exists(metadata_xml):
                with open(metadata_xml, "rb") as f:
                    xmls[package] = gzip.zlib.compress(f.read())
        return xmls

    def __generate_installed_pkgs(self):
        def split_name(dirname):
            try:
                name, version, release = dirname.rsplit("-", 2)
                return name, version + "-" + release
            except ValueError:
                return None

        dirs = os.listdir(ctx.config.packages_dir())
        pkgs = {}
        for d in dirs:
            res = split_name(d)
            if res:
                pkgs[res[0]] = res[1]
        return pkgs

    def __get_marked_packages(self, _type):
        info_path = os.path.join(ctx.config.info_dir(), _type)
        if os.path.exists(info_path):
            return open(info_path, "r").read().split()
        return []

    def __add_to_revdeps(self, package, revdeps):
        metadata_xml = os.path.join(self.package_path(package), ctx.const.metadata_xml)
        try:
            meta_doc = iksemel.parse(metadata_xml)
            pkg = meta_doc.getTag("Package")
        except:
            pkg = None

        if pkg is None:
            # If package info is broken or not available, skip it.
            ctx.ui.warning(
                _(
                    "Installation info for package '%s' is broken. "
                    "Reinstall it to fix this problem."
                )
                % package
            )
            if package in self.installed_db:
                del self.installed_db[package]
            return

        deps = pkg.getTag("RuntimeDependencies")
        if deps:
            for dep in deps.tags("Dependency"):
                dep_name = dep.firstChild().data()
                revdep = revdeps.get(dep_name, {})
                revdep[package] = dep.toString()
                revdeps[dep_name] = revdep
            for anydep in deps.tags("AnyDependency"):
                for dep in anydep.tags("Dependency"):
                    dep_name = dep.firstChild().data()
                    revdep = revdeps.get(dep_name, {})
                    revdep[package] = anydep.toString()
                    revdeps[dep_name] = revdep

    def __generate_revdeps(self):
        revdeps = {}
        for package in self.list_installed():
            self.__add_to_revdeps(package, revdeps)
        return revdeps

    def list_installed(self):
        return list(self.installed_db.keys())

    def has_package(self, package):
        return package in self.installed_db

    def list_installed_with_build_host(self, build_host):
        build_host_re = re.compile("<BuildHost>(.*?)</BuildHost>")
        found = []
        for name in self.list_installed():
            xml = self.xmls_db.get(name)
            if xml:
                import gzip

                xml_data = gzip.zlib.decompress(xml).decode()
            else:
                try:
                    xml_data = open(
                        os.path.join(self.package_path(name), ctx.const.metadata_xml)
                    ).read()
                except Exception:
                    continue

            matched = build_host_re.search(xml_data)
            if matched:
                if build_host != matched.groups()[0]:
                    continue
            elif build_host:
                continue

            found.append(name)

        return found

    def __get_version(self, meta_doc):
        history = meta_doc.getTag("Package").getTag("History")
        version = history.getTag("Update").getTagData("Version")
        release = history.getTag("Update").getAttribute("release")

        # TODO Remove None
        return version, release, None

    def __get_distro_release(self, meta_doc):
        distro = meta_doc.getTag("Package").getTagData("Distribution")
        release = meta_doc.getTag("Package").getTagData("DistributionRelease")

        return distro, release

    def __get_meta_doc(self, package):
        xml = self.xmls_db.get(package)
        if xml:
            import gzip

            return iksemel.parseString(gzip.zlib.decompress(xml).decode())
        else:
            metadata_xml = os.path.join(
                self.package_path(package), ctx.const.metadata_xml
            )
            return iksemel.parse(metadata_xml)

    def get_version_and_distro_release(self, package):
        meta_doc = self.__get_meta_doc(package)
        return self.__get_version(meta_doc) + self.__get_distro_release(meta_doc)

    def get_version(self, package):
        meta_doc = self.__get_meta_doc(package)
        return self.__get_version(meta_doc)

    def get_files(self, package):
        files = pisi.files.Files()
        files_xml = os.path.join(self.package_path(package), ctx.const.files_xml)
        files.read(files_xml)
        return files

    def get_config_files(self, package):
        files = self.get_files(package)
        return [x for x in files.list if x.type == "config"]

    def search_package(self, terms, lang=None, fields=None):
        """
        fields (dict) : looks for terms in the fields which are marked as True
        If the fields is equal to None this method will search in all fields

        example :
        if fields is equal to : {'name': True, 'summary': True, 'desc': False}
        This method will return only package that contents terms in the package
        name or summary
        """
        resum = "<Summary xml:lang=.(%s|en).>.*?%s.*?</Summary>"
        redesc = "<Description xml:lang=.(%s|en).>.*?%s.*?</Description>"
        if not fields:
            fields = {"name": True, "summary": True, "desc": True}
        if not lang:
            lang = pisi.pxml.autoxml.LocalText.get_lang()
        found = []
        for name in self.list_installed():
            xml = self.xmls_db.get(name)
            if xml:
                import gzip

                xml_data = gzip.zlib.decompress(xml).decode()
            else:
                try:
                    xml_data = open(
                        os.path.join(self.package_path(name), ctx.const.metadata_xml)
                    ).read()
                except Exception:
                    continue

            if terms == [
                term
                for term in terms
                if (fields["name"] and re.compile(term, re.I).search(name))
                or (
                    fields["summary"]
                    and re.compile(resum % (lang, term), re.I).search(xml_data)
                )
                or (
                    fields["desc"]
                    and re.compile(redesc % (lang, term), re.I).search(xml_data)
                )
            ]:
                found.append(name)
        return found

    def get_isa_packages(self, isa):
        risa = "<IsA>%s</IsA>" % isa
        packages = []
        for name in self.list_installed():
            xml = self.xmls_db.get(name)
            if xml:
                import gzip

                xml_data = gzip.zlib.decompress(xml).decode()
            else:
                try:
                    xml_data = open(
                        os.path.join(self.package_path(name), ctx.const.metadata_xml)
                    ).read()
                except Exception:
                    continue

            if re.compile(risa).search(xml_data):
                packages.append(name)
        return packages

    def get_info(self, package):
        files_xml = os.path.join(self.package_path(package), ctx.const.files_xml)
        ctime = pisi.util.creation_time(files_xml)
        pkg = self.get_package(package)
        state = "i"
        if pkg.name in self.list_pending():
            state = "ip"

        info = InstallInfo(state, pkg.version, pkg.release, pkg.distribution, ctime)
        return info

    def __make_dependency(self, depStr):
        node = iksemel.parseString(depStr)
        dependency = pisi.dependency.Dependency()
        dependency.package = node.firstChild().data()
        if node.attributes():
            attr = node.attributes()[0].decode()
            dependency.__dict__[attr] = node.getAttribute(attr)
        return dependency

    def __create_dependency(self, depStr: str):
        if "<AnyDependency>" in depStr:
            anydependency = pisi.specfile.AnyDependency()
            for dep in re.compile("(<Dependency .*?>.*?</Dependency>)").findall(depStr):
                anydependency.dependencies.append(self.__make_dependency(dep))
            return anydependency
        else:
            return self.__make_dependency(depStr)

    def get_rev_deps(self, name):
        rev_deps = []

        package_revdeps = self.rev_deps_db.get(name)
        if package_revdeps:
            for pkg, dep in list(package_revdeps.items()):
                dependency = self.__create_dependency(dep)
                rev_deps.append((pkg, dependency))

        return rev_deps

    def pkg_dir(self, pkg, version, release):
        return pisi.util.join_path(
            ctx.config.packages_dir(), pkg + "-" + version + "-" + release
        )

    def get_package(self, package):
        metadata = pisi.metadata.MetaData()
        metadata_xml = os.path.join(self.package_path(package), ctx.const.metadata_xml)
        metadata.read(metadata_xml)
        return metadata.package

    def get_package_by_pkgconfig(self, pkgconfig):
        for item in self.list_installed():
            pkg = self.get_package(item)
            if pkg.providesPkgConfig is not None and len(pkg.providesPkgConfig) > 0:
                for pc in pkg.providesPkgConfig:
                    if pc.om == pkgconfig:
                        return pkg

    def get_package_by_pkgconfig32(self, pkgconfig):
        for item in self.list_installed():
            pkg = self.get_package(item)
            if pkg.providesPkgConfig32 is not None and len(pkg.providesPkgConfig32) > 0:
                for pc in pkg.providesPkgConfig32:
                    if pc.om == pkgconfig:
                        return pkg

    def __mark_package(self, _type, package):
        packages = self.__get_marked_packages(_type)
        if package not in packages:
            packages.append(package)
            self.__write_marked_packages(_type, packages)

    def mark_pending(self, package):
        self.__mark_package(ctx.const.config_pending, package)

    def mark_needs_restart(self, package):
        self.__mark_package(ctx.const.needs_restart, package)

    def mark_needs_reboot(self, package):
        self.__mark_package(ctx.const.needs_reboot, package)

    def mark_auto_installed(self, package):
        self.__mark_package(ctx.const.auto_installed, package)

    def add_package(self, pkginfo):
        # Cleanup old revdep info
        if pkginfo.name in self.installed_db:
            self.remove_package(pkginfo.name)

        self.installed_db[pkginfo.name] = "%s-%s" % (pkginfo.version, pkginfo.release)
        self.__add_to_revdeps(pkginfo.name, self.rev_deps_db)

        # Cache metadata XML
        pkg_path = self.package_path(pkginfo.name)
        metadata_xml = os.path.join(pkg_path, ctx.const.metadata_xml)
        if os.path.exists(metadata_xml):
            import gzip

            with open(metadata_xml, "rb") as f:
                self.xmls_db[pkginfo.name] = gzip.zlib.compress(f.read())

        # Update mtime in meta
        meta = self.lmdb_store.get_mapping("meta")
        packages_dir = ctx.config.packages_dir()
        if os.path.exists(packages_dir):
            meta["mtime_idb"] = os.path.getmtime(packages_dir)

    def remove_package(self, package_name):
        if package_name in self.installed_db:
            # Cleanup revdep info efficiently by only looking at the package's own dependencies
            try:
                metadata_xml = os.path.join(
                    self.package_path(package_name), ctx.const.metadata_xml
                )
                meta_doc = iksemel.parse(metadata_xml)
                pkg = meta_doc.getTag("Package")
                deps = pkg.getTag("RuntimeDependencies")
                if deps:
                    all_deps = []
                    for dep in deps.tags("Dependency"):
                        all_deps.append(dep.firstChild().data())
                    for anydep in deps.tags("AnyDependency"):
                        for dep in anydep.tags("Dependency"):
                            all_deps.append(dep.firstChild().data())

                    for dep_name in set(all_deps):
                        if dep_name in self.rev_deps_db:
                            revdep_info = self.rev_deps_db[dep_name]
                            if package_name in revdep_info:
                                del revdep_info[package_name]
                                if not revdep_info:
                                    del self.rev_deps_db[dep_name]
                                else:
                                    self.rev_deps_db[dep_name] = revdep_info
            except Exception:
                # Fallback to slow cleanup if metadata is broken or not found
                for dep_name in list(self.rev_deps_db.keys()):
                    revdep_info = self.rev_deps_db[dep_name]
                    if package_name in revdep_info:
                        del revdep_info[package_name]
                        if not revdep_info:
                            del self.rev_deps_db[dep_name]
                        else:
                            self.rev_deps_db[dep_name] = revdep_info

            del self.installed_db[package_name]
            if package_name in self.xmls_db:
                del self.xmls_db[package_name]

            # Update mtime in meta
            meta = self.lmdb_store.get_mapping("meta")
            packages_dir = ctx.config.packages_dir()
            if os.path.exists(packages_dir):
                meta["mtime_idb"] = os.path.getmtime(packages_dir)

        self.clear_pending(package_name)

    def list_pending(self):
        return self.__get_marked_packages(ctx.const.config_pending)

    def list_needs_restart(self):
        return self.__get_marked_packages(ctx.const.needs_restart)

    def list_needs_reboot(self):
        return self.__get_marked_packages(ctx.const.needs_reboot)

    def list_auto_installed(self):
        return self.__get_marked_packages(ctx.const.auto_installed)

    def __write_marked_packages(self, _type, packages):
        info_file = os.path.join(ctx.config.info_dir(), _type)
        config = open(info_file, "w")
        for pkg in set(packages):
            config.write("%s\n" % pkg)
        config.close()

    def __clear_marked_packages(self, _type, package):
        if package == "*":
            self.__write_marked_packages(_type, [])
            return
        packages = self.__get_marked_packages(_type)
        if package in packages:
            packages.remove(package)
            self.__write_marked_packages(_type, packages)

    def clear_pending(self, package):
        self.__clear_marked_packages(ctx.const.config_pending, package)

    def clear_needs_restart(self, package):
        self.__clear_marked_packages(ctx.const.needs_restart, package)

    def clear_needs_reboot(self, package):
        self.__clear_marked_packages(ctx.const.needs_reboot, package)

    def clear_auto_installed(self, package):
        self.__clear_marked_packages(ctx.const.auto_installed, package)

    def package_path(self, package):
        if package in self.installed_db:
            return os.path.join(
                ctx.config.packages_dir(),
                "%s-%s" % (package, self.installed_db[package]),
            )

        raise Error(_("Package %s is not installed") % package)
