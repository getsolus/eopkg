# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

"""eopkg source/package index"""

import os
import shutil
import multiprocessing

from pisi import translate as _

import pisi
import pisi.context as ctx
import pisi.specfile as specfile
import pisi.metadata as metadata
import pisi.util as util
import pisi.package
import pisi.pxml.xmlfile as xmlfile
import pisi.file
import pisi.pxml.autoxml as autoxml
import pisi.component as component
import pisi.group as group
import pisi.appstream as appstream
import pisi.operations.build


class Error(pisi.Error):
    pass


class Index(xmlfile.XmlFile, metaclass=autoxml.autoxml):
    tag = "PISI"

    t_Distribution = [component.Distribution, autoxml.OPTIONAL]
    t_Specs = [[specfile.SpecFile], autoxml.OPTIONAL, "SpecFile"]
    t_Packages = [[metadata.Package], autoxml.OPTIONAL, "Package"]
    # t_Metadatas = [ [metadata.MetaData], autoxml.optional, "MetaData"]
    t_Components = [[component.Component], autoxml.OPTIONAL, "Component"]
    t_Groups = [[group.Group], autoxml.OPTIONAL, "Group"]
    t_Appstreams = [[appstream.AppstreamCatalog], autoxml.OPTIONAL, "AppstreamCatalog"]

    def read_uri(self, uri, tmpdir, force=False):
        return self.read(
            uri,
            tmpDir=tmpdir,
            sha1sum=not force,
            compress=pisi.file.File.COMPRESSION_TYPE_AUTO,
            sign=pisi.file.File.detached,
            copylocal=True,
            nodecode=True,
        )

    # read index for a given repo, force means download even if remote not updated
    def read_uri_of_repo(self, uri, repo=None, force=False):
        """Read PSPEC file"""
        if repo:
            tmpdir = os.path.join(ctx.config.index_dir(), repo)
        else:
            tmpdir = os.path.join(ctx.config.tmp_dir(), "index")
            pisi.util.clean_dir(tmpdir)

        pisi.util.ensure_dirs(tmpdir)

        # write uri
        urlfile = open(pisi.util.join_path(tmpdir, "uri"), "w")
        urlfile.write(uri)  # uri
        urlfile.close()

        doc = self.read_uri(uri, tmpdir, force)

        if not repo:
            repo = self.distribution.name()
            # and what do we do with it? move it to index dir properly
            newtmpdir = os.path.join(ctx.config.index_dir(), repo)
            pisi.util.clean_dir(newtmpdir)  # replace newtmpdir
            shutil.move(tmpdir, newtmpdir)

    def check_signature(self, filename, repo):
        tmpdir = os.path.join(ctx.config.index_dir(), repo)
        pisi.file.File.check_signature(filename, tmpdir)

    def index(self, repo_uri):
        self.repo_dir = repo_uri

        packages = []
        specs = []
        deltas = {}

        for root, dirs, files in os.walk(repo_uri):
            # Filter hidden directories
            # TODO: Add --exclude-dirs parameter to CLI and filter according
            # directories here
            dirs[:] = [d for d in dirs if not d.startswith(".")]

            for fn in files:
                if fn.endswith(ctx.const.delta_package_suffix):
                    name, version = util.parse_package_name(fn)
                    deltas.setdefault(name, []).append(os.path.join(root, fn))
                elif fn.endswith(ctx.const.package_suffix):
                    packages.append(os.path.join(root, fn))

                if fn == "appstream.xml":
                    self.appstreams.extend(add_appstreams(os.path.join(root, fn)))
                if fn == "components.xml":
                    self.components.extend(add_components(os.path.join(root, fn)))
                if fn == "distribution.xml":
                    self.distribution = add_distro(os.path.join(root, fn))
                if fn == "groups.xml":
                    self.groups.extend(add_groups(os.path.join(root, fn)))

        ctx.ui.info("")

        # Create a process pool, as many processes as the number of CPUs we
        # have
        pool = multiprocessing.Pool()

        # Before calling pool.map check if list is empty or not: python#12157
        if specs:
            try:
                # Add source packages to index using a process pool
                self.specs = pool.map(add_spec, specs)
            except:
                # If an exception occurs (like a keyboard interrupt),
                # immediately terminate worker processes and propagate
                # exception. (CLI honors KeyboardInterrupt exception, if you're
                # not using CLI, you must handle KeyboardException yourself)
                pool.terminate()
                pool.join()
                ctx.ui.info("")
                raise

        try:
            obsoletes_list = list(map(str, self.distribution.obsoletes))
        except AttributeError:
            obsoletes_list = []

        latest_packages = []

        for pkg in util.filter_latest_packages(packages):
            pkg_name = util.parse_package_name(os.path.basename(pkg))[0]
            if pkg_name.endswith(ctx.const.debug_name_suffix):
                pkg_name = util.remove_suffix(ctx.const.debug_name_suffix, pkg_name)
            if pkg_name not in obsoletes_list:
                # Currently, multiprocessing.Pool.map method accepts methods
                # with single parameters only. So we have to send our
                # parameters as a tuple to workaround that

                latest_packages.append((pkg, deltas, repo_uri))

        # Before calling pool.map check if list is empty or not: python#12157
        if latest_packages:
            try:
                # Add binary packages to index using a process pool
                if ctx.ui.show_verbose:
                    ctx.ui.info(_("Adding packages to index:"))
                self.packages = pool.map(add_package, latest_packages)
            except:
                pool.terminate()
                pool.join()
                ctx.ui.info("")
                raise

        ctx.ui.info("")
        pool.close()
        pool.join()


def add_package(params):
    try:
        path, deltas, repo_uri = params

        if ctx.ui.show_verbose:
            ctx.ui.info("  %s" % os.path.basename(path))
        else:
            ctx.ui.info(
                "%-80.80s\r" % (_("Adding package to index: %s") % os.path.basename(path)),
                noln=True,
            )

        package = pisi.package.Package(path, "r")
        md = package.get_metadata()
        md.package.packageSize = int(os.path.getsize(path))
        md.package.packageHash = util.sha1_file(path)
        if ctx.config.options and ctx.config.options.absolute_urls:
            md.package.packageURI = os.path.realpath(path)
        else:
            md.package.packageURI = util.removepathprefix(repo_uri, path)

        # check package semantics
        errs = md.errors()
        if md.errors():
            ctx.ui.info("")
            ctx.ui.error(
                _("Package %s: metadata corrupt, skipping...") % md.package.name
            )
            ctx.ui.error(str(Error(*errs)))
        else:
            # No need to carry these with index (#3965)
            md.package.files = None
            md.package.additionalFiles = None

            if md.package.name in deltas:
                name, version, release, distro_id, arch = util.split_package_filename(
                    path
                )

                for delta_path in deltas[md.package.name]:
                    (
                        src_release,
                        dst_release,
                        delta_distro_id,
                        delta_arch,
                    ) = util.split_delta_package_filename(delta_path)[1:]

                    # Add only delta to latest build of the package
                    if dst_release != md.package.release or (
                        delta_distro_id,
                        delta_arch,
                    ) != (distro_id, arch):
                        continue

                    delta = metadata.Delta()
                    delta.packageURI = util.removepathprefix(repo_uri, delta_path)
                    delta.packageSize = int(os.path.getsize(delta_path))
                    delta.packageHash = util.sha1_file(delta_path)
                    delta.releaseFrom = src_release

                    md.package.deltaPackages.append(delta)

        return md.package

    except KeyboardInterrupt:
        # Handle KeyboardInterrupt exception to prevent ugly backtrace of all
        # worker processes and propagate the exception to main process.
        #
        # Probably it's better to use just 'raise' here, but multiprocessing
        # module has some bugs about that: (python#8296, python#9205 and
        # python#9207 )
        #
        # For now, worker processes do not propagate exceptions other than
        # Exception (like KeyboardInterrupt), so we have to manually propagate
        # KeyboardInterrupt exception as an Exception.

        raise Exception


def add_appstreams(path):
    ctx.ui.info("Adding appstream.xml to index")
    appstreams_xml = appstream.AppstreamCatalogs()
    appstreams_xml.read(path)
    return appstreams_xml.appstreams


def add_groups(path):
    ctx.ui.info(_("Adding groups.xml to index"))
    groups_xml = group.Groups()
    groups_xml.read(path)
    return groups_xml.groups


def add_components(path):
    ctx.ui.info(_("Adding components.xml to index"))
    components_xml = component.Components()
    components_xml.read(path)
    # try:
    return components_xml.components
    # except:
    #    raise Error(_('Component in %s is corrupt') % path)
    # ctx.ui.error(str(Error(*errs)))


def add_distro(path):
    ctx.ui.info("Adding distribution.xml to index")
    distro = component.Distribution()
    # try:
    distro.read(path)
    return distro
    # except:
    #    raise Error(_('Distribution in %s is corrupt') % path)
    # ctx.ui.error(str(Error(*errs)))


def add_spec(params):
    try:
        path, repo_uri = params
        # TODO: may use try/except to handle this
        builder = pisi.operations.build.Builder(path)
        builder.fetch_component()
        sf = builder.spec
        if ctx.config.options and ctx.config.options.absolute_urls:
            sf.source.sourceURI = os.path.realpath(path)
        else:
            sf.source.sourceURI = util.removepathprefix(repo_uri, path)

        ctx.ui.info(
            "%-80.80s\r" % (_("Adding %s to source index") % path),
            noln=False if ctx.config.get_option("verbose") else True,
        )
        return sf

    except KeyboardInterrupt:
        # Multiprocessing hack, see add_package method for explanation
        raise Exception
