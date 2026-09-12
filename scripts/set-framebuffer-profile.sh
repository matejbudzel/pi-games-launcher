#!/bin/sh
# Select an explicit legacy Pi HDMI/framebuffer profile. Run on the Pi.
set -eu

usage() {
    echo "Usage: $0 {640x480|854x480|720p} [--reboot]" >&2
    exit 2
}

profile=${1:-}
[ "$#" -ge 1 ] || usage
shift
reboot=0
case ${1:-} in
    '') ;;
    --reboot) reboot=1; shift ;;
    *) usage ;;
esac
[ "$#" -eq 0 ] || usage

repo=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
conf=${LAUNCHER_CONF:-"$repo/config/launcher.conf"}
[ -f "$conf" ] || { echo "Missing launcher configuration: $conf" >&2; exit 1; }

set_value() {
    key=$1 value=$2
    if grep -q "^[[:space:]]*$key[[:space:]]*=" "$conf"; then
        sed -i "s|^[[:space:]]*$key[[:space:]]*=.*|$key=$value|" "$conf"
    else
        sed -i "/^[[:space:]]*\[launcher\][[:space:]]*$/a $key=$value" "$conf"
    fi
}

remove_value() { sed -i "/^[[:space:]]*$1[[:space:]]*=/d" "$conf"; }

case $profile in
    640x480)
        set_value framebuffer_hdmi_group 2
        set_value framebuffer_hdmi_mode 4
        set_value framebuffer_width 640
        set_value framebuffer_height 480
        set_value framebuffer_depth 16
        remove_value framebuffer_hdmi_cvt
        ;;
    854x480)
        set_value framebuffer_hdmi_group 2
        set_value framebuffer_hdmi_mode 87
        set_value framebuffer_hdmi_cvt '854 480 60 3 0 0 0'
        set_value framebuffer_width 854
        set_value framebuffer_height 480
        set_value framebuffer_depth 16
        ;;
    720p)
        set_value framebuffer_hdmi_group 1
        set_value framebuffer_hdmi_mode 4
        set_value framebuffer_width 1280
        set_value framebuffer_height 720
        set_value framebuffer_depth 16
        remove_value framebuffer_hdmi_cvt
        ;;
    *) usage ;;
esac

sudo -n LAUNCHER_CONF="$conf" "$repo/scripts/configure-legacy-framebuffer.sh"
echo "Selected $profile. Reboot is required."
[ "$reboot" -eq 0 ] || exec sudo -n reboot
