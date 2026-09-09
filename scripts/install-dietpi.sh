#!/bin/sh
# Install/update the ARMv6 DietPi appliance as its autologin user.
set -eu

[ "$(id -u)" -ne 0 ] || { echo "Run as the autologin user, not root." >&2; exit 1; }
repo=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
user=$(id -un)
home_dir=$(getent passwd "$user" | cut -d: -f6)
[ "$(uname -m)" = armv6l ] || { echo "This installer supports the ARMv6 Pi appliance only." >&2; exit 1; }
if git -C "$repo" diff --quiet && git -C "$repo" diff --cached --quiet; then
    git -C "$repo" pull --ff-only
else
    echo "Local repository changes found; not updating Git checkout." >&2
fi
if ! command -v fbset >/dev/null 2>&1 || ! command -v aplay >/dev/null 2>&1 || ! command -v curl >/dev/null 2>&1; then
    sudo apt-get update
    sudo apt-get install -y fbset alsa-utils curl
fi
for group in input audio video; do getent group "$group" >/dev/null 2>&1 && sudo usermod -aG "$group" "$user" || true; done
[ -f "$repo/config/launcher.conf" ] || cp "$repo/config/launcher.conf.example" "$repo/config/launcher.conf"
"$repo/scripts/install-sdl12-fbcon-release.sh"
sudo LAUNCHER_CONF="$repo/config/launcher.conf" "$repo/scripts/configure-legacy-framebuffer.sh"
sudo "$repo/scripts/configure-appliance-boot.sh"
sudo "$repo/scripts/configure-appliance-audio.sh"
printf '%s ALL=(root) NOPASSWD: /sbin/shutdown -h now\n' "$user" | sudo tee /etc/sudoers.d/pi-games-launcher-shutdown >/dev/null
sudo chmod 0440 /etc/sudoers.d/pi-games-launcher-shutdown
sudo systemctl disable --now pi-286-games.service pi-286-games-audio.service 2>/dev/null || true
sudo rm -f /etc/systemd/system/pi-286-games.service /etc/systemd/system/pi-286-games-audio.service /etc/sudoers.d/pi-286-games-shutdown
sed -e "s|@USER@|$user|g" -e "s|@HOME@|$home_dir|g" -e "s|@REPO@|$repo|g" "$repo/systemd/pi-games-launcher.service.in" | sudo tee /etc/systemd/system/pi-games-launcher.service >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable pi-games-launcher.service
echo "Installed. Reboot to enter the launcher; Ctrl-C on tty1 is the maintenance escape hatch."
