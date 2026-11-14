#!/usr/bin/env bash
# The official Builder image has Xvfb/Weston and a compiler, but no package manager.
# Build two pinned X11 helpers inside that disposable container, never on its host.
set -euo pipefail
prefix=${SKYLOOM_CI_TOOLS_DIR:-"$PWD/build-ci/display-tools"}
mkdir -p "$prefix"
prefix=$(cd "$prefix" && pwd)
directory=$(mktemp -d)
trap 'rm -rf "$directory"' EXIT
build_tool() {
    local name=$1 url=$2 digest=$3
    shift 3
    local archive="$directory/$name.archive"
    curl --fail --location --silent --show-error --max-time 60 "$url" -o "$archive"
    printf '%s  %s\n' "$digest" "$archive" | sha256sum --check --status
    mkdir "$directory/$name"
    tar -xf "$archive" --strip-components=1 -C "$directory/$name"
    # Openbox's bundled 2008 GNU config scripts predate aarch64. Use the
    # config scripts supplied by the pinned build image's Automake toolchain.
    local config_dir
    config_dir=$(automake --print-libdir)
    for config in config.guess config.sub; do
        install -m 755 "$config_dir/$config" "$directory/$name/$config"
    done
    (
        cd "$directory/$name"
        ./configure --prefix="$prefix" "$@"
        make -j2
        make install
    )
}
build_tool openbox https://deb.debian.org/debian/pool/main/o/openbox/openbox_3.6.1.orig.tar.gz \
    8b4ac0760018c77c0044fab06a4f0c510ba87eae934d9983b10878483bde7ef7 \
    --disable-startup-notification --disable-session-management --disable-imlib2 --disable-nls
build_tool xcompmgr https://www.x.org/releases/individual/app/xcompmgr-1.1.10.tar.xz \
    7824f709c4f22432eaea7542ec93384e5dd48f6fcb85c12ff82d721423b0b98f
if [[ -n ${GITHUB_PATH:-} ]]; then
    echo "$prefix/bin" >> "$GITHUB_PATH"
fi
