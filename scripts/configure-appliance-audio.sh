#!/bin/sh
set -eu
printf 'snd_bcm2835\n' > /etc/modules-load.d/pi-games-launcher-audio.conf
modprobe snd_bcm2835 || true
card=$(awk -F'[][]' '/bcm2835 HDMI/ { gsub(/[[:space:]]/, "", $2); print $2; exit }' /proc/asound/cards 2>/dev/null || true)
if [ -z "$card" ]; then
    rm -f /etc/asound.conf
    echo "BCM2835 HDMI ALSA card is unavailable; it will be detected after reboot." >&2
    exit 0
fi
printf '%s\n' '# pi-games-launcher: BCM2835 HDMI ALSA default.' \
    'pcm.!default {' '    type plug' "    slave.pcm \"hw:$card,0\"" '}' \
    'ctl.!default {' '    type hw' "    card \"$card\"" '}' > /etc/asound.conf
