# eopkg package manager

Fork of the PiSi Package Manager, originally from Pardus Linux, and adapted/maintained during the lifetime of SolusOS, EvolveOS and Solus.

The python3 port is now the main development branch.

## FilesDB on-disk version format 4

From version 4.1.5, eopkg.py3/bin will be using a FILESDB_FORMAT_VERSION = 4 versioned gdbm/dbm.gnu format
`/var/lib/eopkg/info/files.db` database, and will auto-regen its FilesDB cache if it encounters
anything but the above.

In earlier versions, eopkg.py3 was using an unversioned gdbm/dbm.gnu format `/var/lib/eopkg/info/files.db` database.

This implies that from version 4.1.5 and forward, eopkg.py3/bin will need to be built with gdbm support, but no
longer needs to be built with bsddb/db5 support (for which upstream CPython support was dropped in 3.9 anyway).

## Updating translations

There are two parts to updating translations: compiling the strings to be translated, and pulling the translations. Since this project has been added to the [Solus Transifex organization](https://explore.transifex.com/solus/), both parts are relatively easy.

First, you need to have the Transifex CLI tool installed. If you do not have it installed, check out [their webpage](https://developers.transifex.com/docs/cli#installation) for instructions.

To compile the strings and push them to Transifex, run:

```bash
./update_pot.sh
tx push -s
```

To pull updated translations, run:

```bash
tx pull
```

When `eopkg` is built, the build system will then compile the translations into a format usable by Python.

## eopkg venv testing

### Prerequisites

On e.g. RHEL 9.x compatible distros, install the following:

`sudo dnf install python3.11-pip-wheel python3.11-devel python3.11 python3.11-libs`

On other distributions, install the equivalent packages.

To build the eopkg.1 man-page, the `pandoc` executable needs to be available.

### Setting up the `eopkg_venv` venv

- Execute `./prepare_eopkg_venv.sh`
- Depending on the shell you use, `source` one of `eopkg_venv/bin/activate`, `eopkg_venv/bin/activate.fish`, or `eopkg_venv/bin/activate.zsh`.

Now you should be able to execute `eopkg.py3 --version` successfully, independently of whether your host system is running Solus or not.

### Running commands with sudo inside the venv

To run a command with elevated privileges via sudo inside the venv, execute:

    sudo -E env PATH="${PATH}" <the command>

**Example:**

    source eopkg_venv/bin/activate
    sudo -E env PATH="${PATH}" eopkg.py3 --version
    deactivate

### Building a Solus chroot using the eopkg_venv eopkg.py3 version

After setting up and activating the venv as above, run `./build_chroot.sh` followed by `./start_systemd_nspawn.sh` (recommended) or `/start_chroot.sh`.

This will dump you to a root shell in a minimal Solus chroot.

#### Exiting systemd-nspawn chroot

Execute `poweroff` as root.

#### Exiting non-systemd-nspawn chroot

Type `exit` or CTRL+D to exit the chroot.

After exiting the chroot, you might be prompted by `sudo` to enter your user password; this is because the kernel virtual
filesystems that were mounted into the chroot directory need to be properly unmounted again.

### Deactivating the eopkg_venv

Type `deactivate` to deactivate the `eopkg_venv`, after which you should be back to your normal shell session.
