# eopkg package manager

Fork of the PiSi Package Manager, originally from Pardus Linux, and adapted/maintained during the lifetime of SolusOS, EvolveOS and Solus.

## eopkg venv testing

### Prerequisites

On e.g. AlmaLinux 9.x, install the following:

`sudo dnf install python3.11-pip-wheel python3.11-devel python3.11 python3.11-libs`

On other distributions, install the equivalent packages.

### Setting up the `eopkg_venv` venv

- Execute `./prepare_eopkg_venv.sh`
- source eopkg_venv/bin/activate || eopkg_venv/bin/activate.fish || eopkg_venv/bin/activate.zsh (depending on the shell you use)

Now you should be able to execute `eopkg --version` successfully.
