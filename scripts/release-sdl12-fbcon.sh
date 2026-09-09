#!/bin/sh
# Build locally, then publish the immutable SDL artifact without CI.
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
tag=${1:?Usage: scripts/release-sdl12-fbcon.sh <tag>}
artifact="$repo/dist/sdl12-fbcon-rpi1-armv6-armhf.tar.gz"
case "$tag" in *[!A-Za-z0-9._-]*|'') echo "Tag may contain only letters, digits, ., _, and -." >&2; exit 2;; esac
command -v gh >/dev/null 2>&1 || { echo "Install and authenticate GitHub CLI first." >&2; exit 1; }
"$repo/scripts/sync-pi-sysroot.sh"
"$repo/scripts/cross-build-sdl12-fbcon.sh"
[ -f "$artifact" ]
gh release create "$tag" "$artifact#sdl12-fbcon-rpi1-armv6-armhf.tar.gz" --repo matejbudzel/pi-games-launcher --title "SDL fbcon $tag" --generate-notes
