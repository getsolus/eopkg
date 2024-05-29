#!/usr/bin/env bash
#
# SPDX-License-Identifier: MPL-2.0
#
# Copyright: © 2024 Serpent OS Developers
#

# build_chroot.sh:
# script for conveniently creating a clean, minimal, self-hosting Solus root
# suitable for use in a chroot or systemd-nspawn context for testing.

source shared_functions.bash

showHelp() {
    cat <<EOF

This will create an up-to-date Solus minimal root dir using the -unstable repo.

Current \$PATH:

${PATH}

EOF
}

# clean up env
cleanEnv () {
    unset EOPKGCACHE
    unset LOCALREPO
    unset MSG
    unset PACKAGES
    unset SOLNAME
    unset SOLROOT

    unset BOLD
    unset RED
    unset RESET
    unset YELLOW
}

EDITION=

if [[ "$1" == "-h" ]] || [[ "$1" == "--help" ]];
then
    showHelp
    cleanEnv
    exit 1
else
    EDITION="minimal"
    echo "Building ${EDITION} self-hosting Solus chroot environment ..."
fi

LOCALREPO="/var/lib/solbuild/local"
EOPKGCACHE="/var/cache/eopkg/packages"
SOLNAME="solus_${EDITION}_chroot"
SOLROOT="${PWD}/${SOLNAME}"

checkPrereqs () {
    # prerequisite checks
    test -x $(command -v chroot) || die "\n${0} assumes that chroot is available\n"
    test -x $(command -v eopkg.py3) || die "\n${0} assumes that eopkg.py3 is available\n"
    test -x $(command -v find) || die "\n${0} assumes that find is available\n"
    test -x $(command -v groupadd) || die "\n${0} assumes that groupadd is available\n"
    test -x $(command -v passwd) || die "\n${0} assumes that passwd is available\n"
    test -x $(command -v systemd-nspawn) || die "\n${0} assumes that systemd-nspawn is available\n"
    test -x $(command -v useradd) || die "\n${0} assumes that useradd is available\n"
    test -x $(command -v yq) || die "\n${0} assumes that yq is available.\n"
    ldconfig -p |grep -q iksemel.so || die "\n${0} assumes that iksemel.so is available (check /etc/ld.so.conf).\n"
}

mountBindMounts() {
    # automagically go out of scope
    local mkdir='sudo mkdir -pv'
    local mount='sudo mount -v'

    MSG="Setting up virtual kernel file systems..."
    printInfo "${MSG}"
    # NB: systemd-nspawn handles all the necessary /dev setup on its own.
    #${mount} -t devtmpfs devtmpfs "${SOLROOT}"/dev
    #${mkdir} "${SOLROOT}"/dev/pts
    #${mount} -t devpts devpts "${SOLROOT}"/dev/pts
    #${mkdir} "${SOLROOT}"/dev/shm
    #${mount} -t tmpfs tmpfs "${SOLROOT}"/dev/shm
    ${mount} -t proc proc "${SOLROOT}"/proc
    ${mount} -t sysfs sysfs "${SOLROOT}"/sys
    ${mount} -t tmpfs tmpfs "${SOLROOT}"/run

    if [[ -d "${LOCALREPO}" ]]; then
        MSG="Bind-mounting the host ${LOCALREPO} directory..."
        printInfo "${MSG}"
        ${mkdir} "${SOLROOT}${LOCALREPO}"
        ${mount} --bind "${LOCALREPO}" "${SOLROOT}${LOCALREPO}"
    fi

    if [[ -d "${EOPKGCACHE}" ]]; then
        MSG="Bind-mounting the host ${EOPKGCACHE} directory..."
        printInfo "${MSG}"
        ${mkdir} "${SOLROOT}${EOPKGCACHE}"
        ${mount} --bind "${EOPKGCACHE}" "${SOLROOT}${EOPKGCACHE}"
    fi
}

unmountBindMounts() {
    # automagically goes out of scope
    local umount='sudo umount -Rfv'

    if [[ -d "${SOLROOT}/${EOPKGCACHE}" ]]; then
        MSG="Unmounting existing ${SOLROOT}${EOPKGCACHE} bind-mount...."
        printInfo "${MSG}"
        ${umount} "${SOLROOT}${EOPKGCACHE}"
    fi

    if [[ -d "${SOLROOT}/${LOCALREPO}" ]]; then
        MSG="Unmounting existing ${SOLROOT}${LOCALREPO} bind-mount...."
        printInfo "${MSG}"
        ${umount} "${SOLROOT}${LOCALREPO}"
    fi

    MSG="Unmounting existing ${SOLROOT} virtual kernel file systems..."
    printInfo "${MSG}"
    for d in run sys proc; do
        ${umount} "${SOLROOT}"/${d}
        # avoid the kernel tripping itself up and failing to recursively unmount
        sleep 1
    done
}

basicSetup () {
    # local variables go out of scope at the end of the function
    local chroot="sudo systemd-nspawn --as-pid2 --quiet -D ${SOLROOT}" # better chroot essentially
    #local chroot="sudo chroot ${SOLROOT}"
    # necessary cruft for sudo to work with the eopkg_venv
    local eopkg_py3="sudo -E env PATH=${PATH} eopkg.py3"
    local eopkg_bin='eopkg4-bin'
    local mkdir='sudo mkdir -pv'

    local eopkg_py3_path="$(command -v eopkg.py3)"
    MSG="Path to eopkg.py3: ${eopkg_py3_path}"
    printInfo "${MSG}"
    MSG="Elevated eopkg.py3 command: ${eopkg_py3}"
    printInfo "${MSG}"

    # should no longer be necessary
    # unmountBindMounts

    MSG="Removing old ${SOLROOT} directory..."
    printInfo "${MSG}"
    sudo rm -rf "${SOLROOT}" || { unmountBindMounts && sudo rm -rf "${SOLROOT}"; } || die "${MSG}"

    MSG="Setting up new ${SOLROOT} directory..."
    printInfo "${MSG}"
    ${mkdir} "${SOLROOT}"/{dev,dev/shm,proc,sys,run} || die "${MSG}"

    mountBindMounts

    if [[ -d ${LOCALREPO} ]]; then
        MSG="Adding ${LOCALREPO} repo to list of active repositories..."
        printInfo "${MSG}"
        ls -l "${SOLROOT}/${LOCALREPO}"
        ${eopkg_py3} add-repo --ignore-check Local "${LOCALREPO}/eopkg-index.xml" -D "${SOLROOT}" || die "${MSG}"
    fi

    MSG="Adding unstable solus repository..."
    printInfo "${MSG}"
    ${eopkg_py3} add-repo Unstable https://packages.getsol.us/unstable/eopkg-index.xml.xz -D "${SOLROOT}" || die "${MSG}"

    MSG="Removing automatically (and unhelpfully) added Solus repo..."
    printInfo "${MSG}"
    ${eopkg_py3} remove-repo Solus -D "${SOLROOT}" || die "${MSG}"

    MSG="Installing baselayout..."
    ${eopkg_py3} install -y -D "${SOLROOT}" --ignore-safety --ignore-comar baselayout || die "${MSG}"

    MSG="Installing packages to act as a seed for systemd-nspawn chroot runs..."
    printInfo "${MSG}"
    #${eopkg_py3} install -y -D "${SOLROOT}" --ignore-safety -c system.base || die "${MSG}"
    ${eopkg_py3} install -y -D "${SOLROOT}" --ignore-safety "${SELFHOSTINGEOPKG[@]}" || die "${MSG}"

    MSG="Adding root group and user in ${SOLROOT} install..."
    printInfo "${MSG}"
    # setting this as interactive, as the dir won't exist if $SOLROOT is non-empty.
    # IFF by some fluke $SOLROOT is empty, THEN we don't want to inadvertently rm -rf the _host_ /root dir,
    # hence the extra -i flag.
    sudo rm -irf "${SOLROOT}"/root
    sudo groupadd -g 0 -r -R "${SOLROOT}" root
    sudo useradd -c Charlie -r -m -d /root/ -u 0 -g 0 -R "${SOLROOT}" root || die "${MSG}"

    MSG="Re-setting password for root user in ${SOLROOT}..."
    printInfo "${MSG}"
    ${chroot} passwd -d root || die "${MSG}"
    echo -n "I am (g)"
    ${chroot} whoami || die "${MSG}"

    MSG="Listing eopkg related directory permissions..."
    printInfo "${MSG}"
    ${chroot} ls -la /var/cache/eopkg /var/run/lock/subsys/pisi

    MSG="Checking for network connectivity from within the systemd-nspawn chroot..."
    printInfo "${MSG}"
    ${chroot} ip addr
    ${chroot} ip route
    ${chroot} nslookup packages.getsol.us

    MSG="Forcing usysconf run inside the chroot (to enable eopkg to use https:// URIs)..."
    printInfo "${MSG}"
    ${chroot} usysconf run -f

    MSG="Installing system.base from within the systemd-nspawn chroot..."
    printInfo "${MSG}"
    ${chroot} ${eopkg_bin} install -y --ignore-safety -c system.base || die "${MSG}"

    MSG="Installing remaining ${EDITION} packages from within the systemd-nspawn chroot..."
    printInfo "${MSG}"
    ${chroot} ${eopkg_bin} install "${PACKAGES[@]}" -y || die "${MSG}"

    MSG="Disabling temporary Local repo within the systemd-nspawn chroot..."
    printInfo "${MSG}"
    ${chroot} ${eopkg_bin} dr Local
    ${chroot} ${eopkg_bin} lr
    ${chroot} ${mkdir} "${LOCALREPO}"
}

buildStartChrootScript() {
    cat <<EOF > start_chroot.sh
#!/usr/bin/env bash
#
# Script for chroot-ing into ${SOLROOT}

source shared_functions.bash

mount_bind_mounts() {
    # automagically go out of scope
    local mkdir='sudo mkdir -pv'
    local mount='sudo mount -v'

    MSG="Setting up virtual kernel file systems..."
    printInfo "${MSG}"
    # --make-rslave prevents these mounts from affecting the parent dirs
    \${mount} -t proc proc "${SOLROOT}"/proc
    \${mount} -t sysfs /sys "${SOLROOT}"/sys --make-rslave
    \${mount} -o rbind /dev "${SOLROOT}"/dev --make-rslave
    \${mount} -t tmpfs tmpfs "${SOLROOT}"/run

    if [[ -d "${LOCALREPO}" ]]; then
        MSG="Bind-mounting the host ${LOCALREPO} directory..."
        printInfo "${MSG}"
        \${mkdir} "${SOLROOT}${LOCALREPO}"
        \${mount} --bind "${LOCALREPO}" "${SOLROOT}${LOCALREPO}"
    fi

    if [[ -d "${EOPKGCACHE}" ]]; then
        MSG="Bind-mounting the host ${EOPKGCACHE} directory..."
        printInfo "${MSG}"
        \${mkdir} "${SOLROOT}${EOPKGCACHE}"
        \${mount} --bind "${EOPKGCACHE}" "${SOLROOT}${EOPKGCACHE}"
    fi
}

unmount_bind_mounts() {
    # automagically goes out of scope
    local umount='sudo umount -Rfv'

    if [[ -d "${SOLROOT}/${EOPKGCACHE}" ]]; then
        MSG="Unmounting existing ${SOLROOT}${EOPKGCACHE} bind-mount...."
        printInfo "${MSG}"
        \${umount} "${SOLROOT}${EOPKGCACHE}"
    fi

    if [[ -d "${SOLROOT}/${LOCALREPO}" ]]; then
        MSG="Unmounting existing ${SOLROOT}${LOCALREPO} bind-mount...."
        printInfo "${MSG}"
        \${umount} "${SOLROOT}${LOCALREPO}"
    fi

    MSG="Unmounting existing ${SOLROOT} virtual kernel file systems..."
    printInfo "${MSG}"
    for d in run dev sys proc; do
        \${umount} "${SOLROOT}"/\${d}
        # avoid the kernel tripping itself up and failing to recursively unmount
        sleep 1
    done
}

# it sucks to leave mounts up in the chroot 
trap unmount_bind_mounts EXIT

MSG="Mounting virtual kernel filesystems in ${SOLROOT} ..."
printInfo "${MSG}"
mount_bind_mounts || die "${MSG}"

MSG="Chrooting into ${SOLROOT} ..."
printInfo "${MSG}"
# ensure that usysconf run -f is run before we exec the login shell for convenience
sudo -E TERM="${TERM}" $(command -v chroot) "${SOLROOT}" /usr/bin/bash -l -c "usysconf run -f && exec /usr/bin/bash -l" || die "${MSG}"

# Should no longer be necessary due to the trap EXIT usage
#MSG="Unmounting virtual kernel filesystems from ${SOLROOT} ..."
#printInfo "${MSG}"
#unmount_bind_mounts || die "${MSG}"

EOF
# be nice to the user
chmod -c a+x start_chroot.sh
}

showStartMessage() {
    cat <<EOF

Building '${EDITION}' chroot from the -unstable repo in the output folder:

  ${SOLROOT}

succeeded.

You can now chroot into the minimal Solus install folder above by executing:

  ./start_chroot.sh

Login: By default, the only enabled user is 'root' with no password.

EOF
}

# it sucks to leave mounts up in the chroot
trap unmountBindMounts EXIT

time {

# Pkg list check
checkPrereqs

# Just enough OS to enable eopkg4-bin to run from _within_ the root
# and to confirm that the network is working + enabling https to work
# NOTE: file and zlib are runtime reqs for eopgk4-bin
SELFHOSTINGEOPKG=(
    bash
    bind-utils
    ca-certs
    coreutils
    eopkg4-bin
    file
    inetutils
    iproute2
    kmod
    libnss
    libseccomp
    perl
    shadow
    sudo
    systemd
    usysconf
    util-linux
    zlib
)

# ISO creation prerequisites, including ssh for cloning iso-tooling,
# and keychain to manage ssh keys in the console
PACKAGES=(
    dosfstools
    git
    keychain
    libisoburn
    make
    openssh
    python3
    pyyaml
    sbsigntools
    squashfs-tools
    syslinux
    yq
)

# Convenience packages
PACKAGES+=(
    fish
    helix
    man-pages
    nano
    neovim
    zsh
)
    
#echo "COMPONENTS: ${COMPONENTS[@]}"
#echo "PACKAGES  : ${PACKAGES[@]}"
#die "Test of PACKAGES."

basicSetup

buildStartChrootScript

#unmountBindMounts

showStartMessage

#cleanEnv

} # end of `time` call
