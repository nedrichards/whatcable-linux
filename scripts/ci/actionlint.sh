#!/usr/bin/env bash
set -euo pipefail
case "$(uname -m)" in
    x86_64) arch=amd64; digest=8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8 ;;
    aarch64) arch=arm64; digest=325e971b6ba9bfa504672e29be93c24981eeb1c07576d730e9f7c8805afff0c6 ;;
    *) echo 'Unsupported actionlint architecture' >&2; exit 2 ;;
esac
directory=$(mktemp -d)
trap 'rm -rf "$directory"' EXIT
archive="$directory/actionlint.tar.gz"
curl --fail --location --silent --show-error --max-time 60 \
    "https://github.com/rhysd/actionlint/releases/download/v1.7.12/actionlint_1.7.12_linux_$arch.tar.gz" -o "$archive"
printf '%s  %s\n' "$digest" "$archive" | sha256sum --check --status
tar -xzf "$archive" -C "$directory" actionlint
"$directory/actionlint" -color
