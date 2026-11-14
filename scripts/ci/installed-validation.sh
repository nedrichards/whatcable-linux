#!/usr/bin/env bash
set -euo pipefail
app="$APP_ID"
args=(--user --socket=x11 --nosocket=wayland --env=GDK_BACKEND=x11 --env=GSK_RENDERER=cairo --env=GSETTINGS_BACKEND=memory --filesystem="$PWD:ro" --filesystem="$PWD/.ci-results")
for variant in standard high-contrast large-text; do
    extra=()
    [[ "$variant" != high-contrast ]] || extra+=(--env=ADW_DEBUG_HIGH_CONTRAST=1)
    [[ "$variant" != large-text ]] || extra+=(--env=CI_LARGE_TEXT=1)
    output="$PWD/.ci-results/visual/$variant"
    mkdir -p "$output"
    flatpak run "${args[@]}" "${extra[@]}" --unshare=network --env=PYTHONPATH= --command=python3 "$app" "$PWD/scripts/ci/visual-smoke.py" "$output"
done
