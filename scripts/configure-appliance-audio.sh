#!/bin/sh
set -eu
printf 'snd_bcm2835\n' > /etc/modules-load.d/pi-games-launcher-audio.conf
printf '%s\n' '# pi-games-launcher: BCM2835 HDMI ALSA default.' 'defaults.pcm.card snd_bcm2835' 'defaults.ctl.card snd_bcm2835' > /etc/asound.conf
