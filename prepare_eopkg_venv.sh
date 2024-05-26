#!/usr/bin/env bash
#
# Set up isolated, clean eopkg  python3.11 venv
#

source ./eopkg_venv_functions.bash

# set up a nice and clean venv environment from newest upstream commits
prepare_venv

# show useful next steps re. testing
help
