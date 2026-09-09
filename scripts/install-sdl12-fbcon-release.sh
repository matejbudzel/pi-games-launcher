#!/bin/sh
# Download and atomically install the current published ARMv6 SDL artifact.
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
. "$repo/scripts/sdl12-fbcon-common.sh"
artifact_url=${SDL12_FBCON_ARTIFACT_URL:-https://github.com/matejbudzel/pi-games-launcher/releases/latest/download/sdl12-fbcon-rpi1-armv6-armhf.tar.gz}
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT HUP INT TERM
curl -fsSL "$artifact_url" -o "$work/sdl.tar.gz"
tar -xzf "$work/sdl.tar.gz" -C "$work"
prefix="$work$sdl12_fbcon_prefix"
[ -x "$prefix/bin/sdl-config" ]
[ "$("$prefix/bin/sdl-config" --version)" = "$sdl12_fbcon_version" ]
[ -e "$prefix/lib/libSDL-1.2.so.0" ]
file -L "$prefix/lib/libSDL-1.2.so.0" | grep -q ARM
readelf -A "$prefix/lib/libSDL-1.2.so.0" | grep -Eq 'Tag_CPU_arch: v6|Tag_CPU_arch: v6KZ'
readelf -A "$prefix/lib/libSDL-1.2.so.0" | grep -q 'Tag_ABI_VFP_args: VFP registers'
sudo rm -rf "$sdl12_fbcon_prefix.new"
sudo mv "$prefix" "$sdl12_fbcon_prefix.new"
sudo rm -rf "$sdl12_fbcon_prefix"
sudo mv "$sdl12_fbcon_prefix.new" "$sdl12_fbcon_prefix"
sudo chown -R root:root "$sdl12_fbcon_prefix"
echo "Installed latest SDL fbcon release to $sdl12_fbcon_prefix."
