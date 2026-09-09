# Project conventions

`pi-games-launcher` is the ARMv6 DietPi appliance layer. It owns the tty1 launcher, legacy BCM2708 framebuffer, HDMI audio, SDL fbcon build and release artifact; providers own games, assets, and game-specific backends.

- Keep the runtime small: Python standard library and direct Linux facilities; no desktop stack, X11, Wayland, KMS/FKMS, or generic hardware abstraction.
- Keep user-facing UI text Slovak. Keep docs and code comments English.
- Prefer short, readable shell/Python. Add comments only for non-obvious hardware, safety, or lifecycle constraints.
- `config/launcher.conf` and `.cache/` are host-local. Never commit game data or provider binaries.
- SDL 1.2 fbcon is pinned and patched here only. Build it off-Pi, publish a GitHub release artifact, and let DietPi fetch it.
- The appliance owns tty1. `Koniec` shuts down; Ctrl-C exits to tty1 for maintenance.
