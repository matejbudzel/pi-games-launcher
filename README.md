# pi-games-launcher

Text-only Raspberry Pi ARMv6 appliance launcher. It owns the Linux console, legacy framebuffer recovery, and menu input only while its menu is visible. Games are independent providers.

## Provider contract

Each `[provider ID]` section supplies a `manifest_command`. It must print exactly one JSON document:

```json
{"version":1,"games":[{"id":"provider-specific-id","title":"Prince of Persia","command":["/path/to/provider","run","provider-specific-id"]}]}
```

IDs are unique only within their provider; the launcher namespaces them internally. A bad command, failed command, or malformed document is logged and isolated. All manifests are refreshed at startup, after every guest exits, and on F2 from either menu.

## Ownership and handoff

The menu reads the console keyboard and the supported WiseGroup X-PAD directly, rediscovering `/dev/input/js*` every two seconds. Before executing a manifest command it stops its terminal UI, closes joystick descriptors, restores text/fbcon state, and foregrounds the child process group. The guest directly owns framebuffer, audio and input. On exit/crash the launcher restores the console, reacquires devices, and rebuilds the menu. It has no DOSBox, streaming, game asset, or panic-button knowledge.

## DietPi appliance setup

Clone this repository on the target and run `scripts/install-dietpi.sh` as the DietPi autologin user. A clean clone fast-forwards itself; local configuration or changes prevent that update. The installer fetches the latest published ARMv6 SDL 1.2 fbcon artifact, configures the proven legacy BCM2708 `/dev/fb0` and `snd_bcm2835` HDMI path, makes the boot quiet, and adds `panic=10` for automatic reboot after a kernel panic. It deliberately installs no desktop stack, X11, Wayland, KMS, or FKMS.

`Koniec` always shuts the Pi down. Ctrl-C is intentionally different: it exits the launcher on tty1 for maintenance. With no provider games, the menu still offers dimmed framebuffer and HDMI-audio smoke tests above `Koniec`.

The installer disables and removes the old `pi-286-games` service units and sudo rule. It does not remove a former source checkout itself; remove it after confirming the new service boots.

`tvservice` is queried best-effort before menu rendering when present; unknown probes do not stop the launcher. Provider hooks can be configured as `hook_input_added`, `hook_input_removed`, `hook_display_on`, or `hook_display_off`; they are reserved optional notifications and hook failures never affect launcher operation.

Run `scripts/set-framebuffer-profile.sh {640x480|854x480|720p} [--reboot]` on the Pi to select a legacy HDMI/framebuffer profile. The custom 854×480 profile uses DMT mode 87 and its CVT timing; the target display must support it.

The launcher also serves an unauthenticated local-network virtual dance mat on TCP port 8080 by default. It provides eight directions plus `START` and `SELECT` through a Linux virtual joystick, so the launcher and guest games can use it. Set `web_dancemat_port=0` in `[launcher]` to disable it.

## SDL build and release

SDL 1.2 fbcon source, patches, scripts, and host-local ARMv6 cache belong here exclusively. Build/release work is deliberately local—never GitHub Actions—because it synchronizes headers and runtime libraries from the real Pi:

```sh
scripts/release-sdl12-fbcon.sh sdl12-fbcon-YYYYMMDD
```

That command synchronizes the Pi sysroot, rebuilds, verifies ARMv6 hard-float/fbcon output, and uploads `sdl12-fbcon-rpi1-armv6-armhf.tar.gz` to a GitHub release. DietPi always installs the latest release asset. `scripts/dev-sdl.sh {sync|build|deploy|verify|all}` remains available for direct development deployment to `pi286`.

## Development

Run `PYTHONPATH=. python3 -m unittest discover -s tests`. Hardware code is intentionally small and should be manually checked on a Pi: boot with HDMI absent/attached, reconnect the dance pad and keyboard, run a framebuffer guest, kill it, and ensure the menu returns cleanly.

The ignored `.cache/` and `dist/` directories hold SDL cross-build inputs and artifacts. Provider-specific binaries and backend build artifacts remain with their provider.
