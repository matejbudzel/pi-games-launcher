#!/bin/sh
set -eu
repo=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
conf=${LAUNCHER_CONF:-$repo/config/launcher.conf}
setting() { sed -n "s/^[[:space:]]*$1[[:space:]]*=[[:space:]]*//p" "$conf" 2>/dev/null | tail -n1; }
width=$(setting framebuffer_width); width=${width:-640}; height=$(setting framebuffer_height); height=${height:-480}; depth=$(setting framebuffer_depth); depth=${depth:-16}; group=$(setting framebuffer_hdmi_group); group=${group:-2}; mode=$(setting framebuffer_hdmi_mode); mode=${mode:-4}
boot=/boot/config.txt
[ -f /boot/firmware/config.txt ] && boot=/boot/firmware/config.txt
[ -f "$boot" ] || { echo "No Raspberry Pi config.txt found." >&2; exit 0; }
sed -i '/# pi-games-launcher legacy framebuffer/,$d' "$boot"
{
    echo '# pi-games-launcher legacy framebuffer'
    echo 'dtparam=audio=on'
    echo 'framebuffer_ignore_alpha=1'
    echo "hdmi_group=$group"
    echo "hdmi_mode=$mode"
    echo "framebuffer_width=$width"
    echo "framebuffer_height=$height"
    echo "framebuffer_depth=$depth"
} >> "$boot"
echo "Configured ${width}x${height} legacy framebuffer; reboot required."
