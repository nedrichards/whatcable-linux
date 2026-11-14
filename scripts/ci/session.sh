#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)
export XDG_DATA_DIRS="$root/build-ci/display-tools/share:${XDG_DATA_DIRS:-/app/share:/usr/share}"
export XDG_CONFIG_DIRS="$root/build-ci/display-tools/etc/xdg:${XDG_CONFIG_DIRS:-/etc/xdg}"
pids=()
cleanup() { for pid in "${pids[@]}"; do kill "$pid" 2>/dev/null || true; done; }
trap cleanup EXIT
/app/libexec/flatpak-portal --replace --no-idle-exit --verbose >.ci-results/flatpak-portal.log 2>&1 &
pids+=("$!")
gdbus wait --session --timeout 10 org.freedesktop.portal.Flatpak
openbox --sm-disable >.ci-results/window-manager.log 2>&1 &
pids+=("$!")
xcompmgr >.ci-results/compositor.log 2>&1 &
pids+=("$!")
sleep 1
for pid in "${pids[@]}"; do kill -0 "$pid"; done
"$@"
