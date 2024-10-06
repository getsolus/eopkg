eopkg package manager
---------------------

Fork of the PiSi Package Manager, originally from Pardus Linux,
and adapted/maintained during the lifetime of SolusOS, EvolveOS and Solus.

Please note that we plan to replace eopkg with [`moss`](https://github.com/serpent-os/moss).

FilesDB on-disk version format 3
--------------------------------

From version 3.12.5, eopkg.py2 will be using a FILESDB_FORMAT_VERSION = 3 versioned gdbm format `/var/lib/eopkg/info/files.db` database, and will auto-regen its FilesDB cache if it encounters anything but the above.

In earlier versions, eopkg.py2 was using an unversioned bsddb format `/var/lib/eopkg/info/files.db` database.

This implies that from version 3.12.5 and forward, eopkg.py2 will need to be built with gdbm support, but no longer needs to be built with bsddb/db5 support.
