# SPDX-FileCopyrightText: 2005-2011 TUBITAK/UEKAE, 2013-2017 Ikey Doherty, Solus Project
# SPDX-License-Identifier: GPL-2.0-or-later

import os
import gettext

from pisi import appstream

__trans = gettext.translation("pisi", fallback=True)
_ = __trans.gettext

import pisi
import pisi.uri
import pisi.context as ctx
import pisi.util
import pisi.db
import pisi.db.appstreamdb
import pisi.fetcher as fetcher
import gzip
import lzma
import posixpath
from email.utils import formatdate
import email.utils
from contextlib import contextmanager
from datetime import datetime
import shutil
from pathlib import Path
from pisi.archive import ArchiveTar
import xml.etree.ElementTree as ET

from pisi.db.appstreamdb import AppstreamNotFound

# https://www.freedesktop.org/software/appstream/docs/chap-CatalogData.html#sect-AppStream-XML

CATALOG_BASE_PATH = "/var/lib/swcatalog"
CATALOG_XML_PATH = os.path.join(CATALOG_BASE_PATH, "xml")
CATALOG_ICONS_BASE_PATH = os.path.join(CATALOG_BASE_PATH, "icons")


def __appstream_get_catalog_origin(file_path):
    """ Returns the 'origin' of the compressed or uncompressed appstream catalog XML file """
    with __read_appstream_catalog(file_path) as f:
        tree = ET.parse(f)
        root = tree.getroot()

        if root.tag == 'components':
            return root.attrib.get('origin')
        else:
            raise ValueError("Root tag is not 'components'")


@contextmanager
def __read_appstream_catalog(file_path):
    valid_extensions = ('.xml', '.xml.gz', '.xml.xz')

    if not file_path.endswith(valid_extensions):
        raise ValueError(f"Unsupported appstream catalog extension: {file_path}")

    def open_file(path):
        if path.endswith('.gz'):
            return gzip.open(path, 'rt', encoding='utf-8')
        elif path.endswith('.xz'):
            return lzma.open(path, 'rt', encoding='utf-8')
        else:
            return open(path, 'rt', encoding='utf-8')
    f = open_file(file_path)
    try:
        yield f
    finally:
        f.close()


#def __store_file_modified_time(file, output_file):
#    headers = {}
#    mtime = os.path.getmtime(file)
#    dt = datetime.utcfromtimestamp(mtime)
#    headers["If-Modified-Since"] = format_datetime(dt)
#    print("FILE LAST MODIFIED TIME:", file, headers["If-Modified-Since"])
#
#    with open(output_file, "w", encoding="utf-8") as f:
#        f.write(headers["If-Modified-Since"])

def __get_last_modified_http_header(file_path):
    # Get last modified time as seconds since epoch
    mtime = os.path.getmtime(file_path)

    # Convert to RFC 1123 formatted date in GMT
    http_date = formatdate(timeval=mtime, usegmt=True)

    return http_date


def __get_full_extension(uri):
    from urllib.parse import urlparse
    path = urlparse(uri).path
    basename = os.path.basename(path)
    parts = basename.split('.')
    if len(parts) > 1:
        return '.' + '.'.join(parts[1:])
    return ''


def __download_appstream_catalog(catalog: appstream.AppstreamCatalog, force=False):
    catalog_uri = pisi.uri.URI(catalog.uRI)
    full_ext = __get_full_extension(catalog.uRI)
    #print("full ext", full_ext)
    pisi.util.ensure_dirs(CATALOG_XML_PATH)

    existing = os.path.join(CATALOG_XML_PATH, f"{catalog.origin}{full_ext}")
    print("existing", existing)

    existing_last_mod = None
    if os.path.exists(existing):
        existing_last_mod = __get_last_modified_http_header(existing)
        print("existing last mod", existing_last_mod)

    fetch = fetcher.fetch_url(catalog.uRI, CATALOG_XML_PATH, ctx.ui.Progress, destfile=existing, headers_only=True)
    print("fetch", fetch.headers.get('Last-Modified'))

    if force is False and (fetch.headers.get('Last-Modified') == existing_last_mod):
        ctx.ui.debug(_("Appstream: 'Last-Modified' is identical, skipping %s") % catalog_uri.get_uri())
        return

    fetch.headers_only = False
    fetch.fetch()

    # Restore modified time to match URI
    mod_time = email.utils.parsedate_to_datetime(fetch.headers.get('Last-Modified')).timestamp()
    os.utime(existing, (mod_time, mod_time))

    origin = __appstream_get_catalog_origin(existing)
    if origin != catalog.origin:
        raise AppstreamNotFound(_("Appstream catalog origin doesn't match, expected %s, actual: %s") % (catalog.origin, origin))

    # Create a marker so we know this catalog is managed by eopkg
    existing_marker = Path(f"{existing}.eopkg")
    print("marker", existing_marker)
    if not os.path.exists(existing_marker):
        existing_marker.touch()

    if catalog.icons is None:
        return
    __download_appstream_icons(catalog, origin, force)


def __download_appstream_icons(catalog: appstream.AppstreamCatalog, origin: str, force=False):
    for icons in catalog.icons:
        target_dir = os.path.join(CATALOG_ICONS_BASE_PATH, origin, icons.size)
        pisi.util.ensure_dirs(target_dir)
        existing_last_mod = __get_last_modified_http_header(target_dir)
        icons_uri = pisi.uri.URI(icons.uRI)
        tmpfile = pisi.util.join_path("/tmp", icons_uri.filename())
        fetch = fetcher.fetch_url(icons.uRI, "/tmp", ctx.ui.Progress, destfile=tmpfile, headers_only=True)

        if force is False and (fetch.headers.get('Last-Modified') == existing_last_mod):
            ctx.ui.debug(_("Appstream: 'Last-Modified' is identical, skipping %s") % catalog_uri.get_uri())
            continue

        fetch.headers_only = False
        fetch.fetch()

        icons_archive = ArchiveTar(tmpfile, "targz")
        icons_archive.unpack(target_dir)

        # Restore modified time to match URI
        mod_time = email.utils.parsedate_to_datetime(fetch.headers.get('Last-Modified')).timestamp()
        os.utime(target_dir, (mod_time, mod_time))


def __get_obsolete_catalogs(appstreams: list):
    path = Path(CATALOG_XML_PATH)
    if path.exists() is False:
        return

    installed_catalogs = {path / f.name for f in path.iterdir() if f.is_file()}
    eopkg_managed = set()

    for catalog in installed_catalogs:
        if not os.path.exists(f"{catalog}.eopkg"):
            continue
        eopkg_managed.add(catalog)

    obsolete = {origin for origin in appstreams} - \
                {posixpath.basename(f)[: -sum(len(s) for s in f.suffixes)] for f in eopkg_managed}

    if obsolete:
        ctx.ui.debug(_("Appstream: Obsolete catalogs marked for removal: %s") % obsolete)
    return obsolete


def __nuke_dir(pattern):
    import glob
    for path in glob.glob(pattern):
        try:
            if os.path.isdir(path) and not os.path.islink(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
        except Exception as e:
            print(f"Error removing {path}: {e}")


def __remove_obsolete_catalog(catalog):
    xml_pattern = os.path.join(CATALOG_XML_PATH, catalog)
    icon_pattern = os.path.join(CATALOG_ICONS_BASE_PATH, catalog)
    __nuke_dir(xml_pattern)
    __nuke_dir(icon_pattern)
    ctx.ui.debug(_("Appstream: Removed obsolete catalog: %s") % catalog)


def update_catalogs(repo, force=False):
    appstreamdb = pisi.db.appstreamdb.AppstreamDB()
    catalogs = appstreamdb.list_catalogs(repo)
    obsoletes = __get_obsolete_catalogs(catalogs)
    if obsoletes is not None:
        for catalog in obsoletes:
            __remove_obsolete_catalog(catalog)
    if catalogs is not None:
        for origin in catalogs:
            catalog = appstreamdb.get_catalog(origin)
            __download_appstream_catalog(catalog, force)
