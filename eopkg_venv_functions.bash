# Set up isolated, clean eopkg_venv python3.11 venv
#
# This is designed to be sourced from other bash scripts

source shared_functions.bash

function prepare_venv () {
    # Assume the user starts in the eopkg dir
    echo ">>> Updating the eopkg git repo ..."
    # ensure we show the current branch
    git fetch && git checkout python3 && git pull && git branch

    echo ">>> Set up a clean eopkg_venv venv ..."
    python3.11 -m venv --clear eopkg_venv
    source eopkg_venv/bin/activate
    python3.11 -m pip install -r requirements.txt
    compile_iksemel_cleanly

    echo ">>> Symlink eopkg-cli into the eopkg_venv bin/ directory so it can be executed as eopkg.py3 ..."
    ln -srvf ./eopkg-cli eopkg_venv/bin/eopkg.py3

    # get rid of any existing lines w/git ref version info
    sed "/__version__ += /d" -i pisi/__init__.py
    echo ">>> pisi version variable BEFORE patching:":
    grep -Hn version pisi/__init__.py
    # append the git ref to __version__ on a new line
    gawk -i inplace 'BEGIN { "git rev-parse --short HEAD" | getline gitref } { print }; /__version__ = / { printf "%s %s\n", $1, "+= \" (" gitref ")\"" }' pisi/__init__.py
    echo ">>> pisi version variable AFTER patching w/git revision:"
    grep -Hn version pisi/__init__.py
}

function compile_iksemel_cleanly () {
    # Solus is currently carrying a patch to iksemel that has not yet been upstreamed
    # clone iksemel fresh to ensure patches apply cleanly every time
    if [[ -d ../iksemel/build ]]; then
        echo ">>> Uninstalling existing custom-compiled iksemel copy ..."
        pushd ../iksemel/
        sudo ninja uninstall -C build/
        popd
    fi
    echo ">>> Set up a clean iksemel copy w/Solus patches ..."
    rm -rf ../iksemel/
    git clone https://github.com/Zaryob/iksemel.git ../iksemel/
    # fetch solus patches into iksemel dir
    pushd ../iksemel/
        for p in 0001-src-iks.c-Retain-py2-piksemel-behaviour.patch 0001-Escape-non-ASCII-characters.patch 0002-Escape-non-printable-ASCII-characters.patch
        do
            wget https://raw.githubusercontent.com/getsolus/packages/main/packages/i/iksemel/files/"${p}"
            patch -p1 -i "${p}"
        done
        # this should now build against the python in the eopkg_venv
        meson build -Dwith_python=true
        meson compile -C build/
        # Install iksemel, except for on Solus systems that already have iksemel installed
        grep -q 'NAME="Solus"' /etc/os-release && find /usr/lib* -name libiksemel.so -quit || \
        sudo meson install -C build/
    popd
    # symlink the iksemel python C module into our eopkg_venv
    echo -e ">>> Symlink the newly built Solus-patched iksemel python C-extension into the eopkg_venv ..."
    ln -srvf ../iksemel/build/python/iksemel.cpython-311-x86_64-linux-gnu.so eopkg_venv/lib/python3.11/site-packages/
    ls -l eopkg_venv/lib/python3.11/site-packages/*.so
}

function help () {
    cat << EOF

    1. To activate the newly prepared eopkg venv, execute:

           source eopkg_venv/bin/activate
       XOR
           source eopkg_venv/bin/activate.fish
       XOR
           source eopkg_venv/bin/activate.zsh

       ... depending on which shell you use.

    2. To run a command with elevated privileges via sudo inside the venv, execute:

       sudo -E env PATH="\${PATH}" <the command>

    3. When you are done, execute:

         deactivate

       ... to exit the eopkg venv.

EOF
}
