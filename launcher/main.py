#!/usr/bin/env python3
"""Text-only console UI. It knows providers only through their manifests."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import fcntl
import logging
import os
import select
import socket
import struct
import subprocess
import sys
import termios
import time
import tty
from pathlib import Path
from .config import load, save_launcher_value
from .display import Display, restore_console
from .input import DancePad, PAD_ACTIONS
from .hooks import notify
from .manifests import collect
from .process import run
from . import smoke

LOG = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[1]
SPLASH_SECONDS = 4.0
SPLASH_ART = (
    "                                                                       ▄█╗",
    "                                                                       ╚═╝",
    "██╗  ██╗ ██████╗  ██████╗██╗  ██╗ ██████╗ ██╗   ██╗ █████╗ ███╗   ██╗███████╗",
    "██║ ██╔╝██╔═══██╗██╔════╝██║ ██╔╝██╔═══██╗██║   ██║██╔══██╗████╗  ██║██╔════╝",
    "█████╔╝ ██║   ██║██║     █████╔╝ ██║   ██║██║   ██║███████║██╔██╗ ██║█████╗  ",
    "██╔═██╗ ██║   ██║██║     ██╔═██╗ ██║   ██║╚██╗ ██╔╝██╔══██║██║╚██╗██║██╔══╝  ",
    "██║  ██╗╚██████╔╝╚██████╗██║  ██╗╚██████╔╝ ╚████╔╝ ██║  ██║██║ ╚████║███████╗",
    "╚═╝  ╚═╝ ╚═════╝  ╚═════╝╚═╝  ╚═╝ ╚═════╝   ╚═══╝  ╚═╝  ╚═╝╚═╝  ╚═══╝╚══════╝",
    "",
    "",
    "██╗  ██╗██████╗ ██╗   ██╗",
    "██║  ██║██╔══██╗╚██╗ ██╔╝",
    "███████║██████╔╝ ╚████╔╝ ",
    "██╔══██║██╔══██╗  ╚██╔╝  ",
    "██║  ██║██║  ██║   ██║   ",
    "╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝   ",
)
SPLASH_COLORS = ("\x1b[91m", "\x1b[93m", "\x1b[92m", "\x1b[96m", "\x1b[94m", "\x1b[95m")
HIGHLIGHT_COLORS = ("\x1b[91m", "\x1b[92m", "\x1b[93m", "\x1b[94m", "\x1b[95m", "\x1b[96m")
MAINTENANCE_EXIT = 42


def highlight_color(name):
    return HIGHLIGHT_COLORS[sum((index + 1) * ord(letter) for index, letter in enumerate(name)) % len(HIGHLIGHT_COLORS)]


def hdmi_card_index(cards_path="/proc/asound/cards"):
    try:
        for line in Path(cards_path).read_text().splitlines():
            if "bcm2835 HDMI" in line:
                return line.split("[", 1)[0].strip()
    except OSError:
        pass
    return "0"


def set_audio_volume(percent):
    try:
        return subprocess.run(["amixer", "-c", hdmi_card_index(), "sset", "PCM", "%d%%" % percent],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
    except OSError:
        return False


def volume_status(percent):
    filled = max(0, min(10, (percent + 5) // 10))
    return "Zvuk: [%s%s] %d%%" % ("#" * filled, "." * (10 - filled), percent)


def network_address():
    """Return the first usable Ethernet/Wi-Fi IPv4 address without a shell tool."""
    names = sorted(socket.if_nameindex(), key=lambda item: (not item[1].startswith(("eth", "en")), item[1]))
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        for _, name in names:
            if not name.startswith(("eth", "en", "wlan", "wl")):
                continue
            try:
                reply = fcntl.ioctl(probe.fileno(), 0x8915, struct.pack("256s", name.encode()[:15]))
                return socket.inet_ntoa(reply[20:24])
            except OSError:
                pass
    return "offline"

class Terminal:
    def __enter__(self):
        self.fd = sys.stdin.fileno()
        if not os.isatty(self.fd): raise RuntimeError("Launcher needs an interactive Linux console.")
        self.old = termios.tcgetattr(self.fd); self.active = False; self.activate(); return self
    def __exit__(self, *_): self.deactivate()
    def activate(self):
        if not self.active:
            tty.setraw(self.fd); sys.stdout.write("\x1b[?1049h\x1b[?25l"); sys.stdout.flush(); self.active = True
    def deactivate(self):
        if self.active:
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old); sys.stdout.write("\x1b[?25h\x1b[?1049l"); sys.stdout.flush(); self.active = False
    def key(self, timeout=.1):
        if not select.select([self.fd], [], [], timeout)[0]: return None
        data = os.read(self.fd, 8)
        return {b"\x03":"CTRL_C", b"\x1b":"ESC", b"\x1b[A":"UP", b"\x1bOA":"UP", b"\x1b[B":"DOWN", b"\x1bOB":"DOWN", b"\x1b[C":"RIGHT", b"\x1bOC":"RIGHT", b"\x1b[D":"LEFT", b"\x1bOD":"LEFT", b"\x1bOP":"F1", b"\x1bOQ":"F2", b"\x1b[12~":"F2", b" ":"SPACE", b"\r":"ENTER"}.get(data, data.decode("utf-8", "ignore").upper())
    def draw(self, lines, top_corner="", bottom_corner=""):
        size = os.get_terminal_size(sys.stdout.fileno())
        out = ["\x1b[2J\x1b[H", "\r\n" * max(0, (size.lines - len(lines)) // 2)]
        for line in lines:
            text, selected = line[:2]
            dim = len(line) > 2 and line[2]
            prefix, suffix = ("> ", " <") if selected else ("", "")
            text = text[:max(0, size.columns - len(prefix) - len(suffix))]
            tone = highlight_color(text) if selected else "\x1b[2;37m" if dim else "\x1b[37m"
            out.append(tone + " " * max(0, (size.columns-len(text)-len(prefix)-len(suffix)) // 2) + prefix + text + suffix + "\x1b[0m\r\n")
        if top_corner:
            out.append("\x1b[1;%dH\x1b[2;37m%s\x1b[0m" % (max(1, size.columns - len(top_corner) + 1), top_corner[:size.columns]))
        if bottom_corner:
            out.append("\x1b[%d;%dH\x1b[2;37m%s\x1b[0m" % (size.lines, max(1, size.columns - len(bottom_corner) + 1), bottom_corner[:size.columns]))
        sys.stdout.write("".join(out)); sys.stdout.flush()
    def splash(self, seconds=SPLASH_SECONDS):
        size = os.get_terminal_size(sys.stdout.fileno())
        lines = SPLASH_ART if size.columns >= 80 else ("KOCKOVANÉ HRY",)
        out = ["\x1b[2J\x1b[H", "\r\n" * max(0, (size.lines - len(lines)) // 2)]
        for row, text in enumerate(lines):
            if not text:
                out.append("\r\n")
                continue
            left = " " * max(0, (size.columns - len(text)) // 2)
            rainbow = "".join(SPLASH_COLORS[((index + row * 4) * len(SPLASH_COLORS) // max(1, size.columns)) % len(SPLASH_COLORS)] + character for index, character in enumerate(text))
            out.append(left + rainbow + "\x1b[0m\r\n")
        sys.stdout.write("".join(out)); sys.stdout.flush()
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            self.key(min(.1, deadline - time.monotonic()))

def next_input(term, pad):
    key = term.key()
    if key: return key
    for button in pad.buttons():
        if button in PAD_ACTIONS: return PAD_ACTIONS[button]
    return None


def run_smoke_test(test, terminal, pad):
    """Give a diagnostic exclusive console/input ownership like a guest."""
    try:
        pad.close()
        terminal.deactivate()
        restore_console()
        test()
    except RuntimeError as error:
        print(f"Test zlyhal: {error}", file=sys.stderr)
        print("Stlač ľubovoľnú klávesu pre návrat.", flush=True)
        sys.stdin.read(1)
    finally:
        terminal.activate()
        pad.open()


def wait_for_config(terminal, path):
    """Keep a broken local configuration from restarting the tty service."""
    previous_error = None
    while True:
        try:
            return load(path)
        except ValueError as error:
            if str(error) != previous_error:
                LOG.error("launcher configuration unavailable: %s", error)
                previous_error = str(error)
            terminal.draw([
                ("Chyba konfigurácie launchera", True),
                ("", False),
                (str(error), False, True),
                ("", False),
                ("Oprav súbor a obrazovka sa obnoví automaticky.", False),
                ("Ctrl-C - údržba na tty1", False, True),
            ])
            if terminal.key(.5) == "CTRL_C":
                return None


def confirm_shutdown(terminal, pad, confirm_key):
    terminal.draw([
        ("Naozaj chceš vypnúť Raspberry Pi?", True),
        ("", False),
        ("%s / START - vypnúť" % confirm_key, False),
        ("ESC / SELECT - späť", False, True),
    ])
    while True:
        key = next_input(terminal, pad)
        if key == "CTRL_C":
            return None
        if key in (confirm_key, "START", "ENTER"):
            return True
        if key in ("ESC", "SELECT"):
            return False


def entry_key(kind, value):
    """Return a stable menu identifier that survives manifest refreshes."""
    return value.key if kind in ("game", "testing") else kind


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "config" / "launcher.conf")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args(argv)
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO), format="%(levelname)s: %(message)s")
    selected = 0
    selected_key = ""
    saved_selected_key = ""
    tools_open = False
    tool_selected = 0
    tool_selected_key = ""
    redraw = True
    network = ""
    display = Display()
    with Terminal() as terminal:
        settings = wait_for_config(terminal, args.config)
        if settings is None:
            return MAINTENANCE_EXIT
        selected_key = settings.last_selected_item
        saved_selected_key = selected_key
        volume = settings.audio_volume_percent
        if not set_audio_volume(volume):
            LOG.warning("could not set HDMI PCM volume")
        pad = DancePad().open()
        previous_pad, previous_display = pad.available, display.available()
        notify(settings.providers, "input-added" if previous_pad else "input-removed")
        notify(settings.providers, "display-on" if previous_display else "display-off")
        try:
            # Providers can answer while the boot splash holds the screen.
            with ThreadPoolExecutor(max_workers=1) as executor:
                initial_catalog = executor.submit(collect, settings.providers)
                terminal.splash()
                games, problems = initial_catalog.result()
            while True:
                regular_games = [game for game in games if not game.testing_tool]
                testing_games = [game for game in games if game.testing_tool]
                entries = [("game", game.title, game) for game in regular_games]
                entries += [("tools", "Nástroje", None), ("shutdown", "Koniec", None)]
                tools = [("testing", game.title, game) for game in testing_games]
                tools += [("video", "Test obrazu framebufferu", smoke.framebuffer),
                          ("audio", "Test HDMI zvuku", smoke.audio)]
                # Older versions stored a tool itself as the main-menu choice.
                if selected_key in {entry_key(kind, value) for kind, _, value in tools}:
                    selected_key = "tools"
                selected = next((index for index, (kind, _, value) in enumerate(entries)
                                 if entry_key(kind, value) == selected_key), 0)
                selected_key = entry_key(entries[selected][0], entries[selected][2])
                tool_selected = next((index for index, (kind, _, value) in enumerate(tools)
                                      if entry_key(kind, value) == tool_selected_key), 0)
                tool_selected_key = entry_key(tools[tool_selected][0], tools[tool_selected][2])
                if selected_key != saved_selected_key:
                    save_launcher_value(args.config, "last_selected_item", selected_key)
                    saved_selected_key = selected_key
                while True:
                    if redraw:
                        suffix = " (displej nie je dostupný)" if not display.available() else ""
                        if tools_open:
                            lines = [("╔══════ Nástroje ══════╗", False, True), ("", False)]
                            lines += [(title, index == tool_selected, False) for index, (_, title, _) in enumerate(tools)]
                            lines += [("", False), ("F2 - obnoviť | ESC / SELECT - späť" + suffix, False, True),
                                      ("╚══════════════════════╝", False, True)]
                        else:
                            lines = [(title, index == selected, False) for index, (_, title, _) in enumerate(entries[:len(regular_games)])]
                            if regular_games:
                                lines.append(("", False))
                            lines += [(title, index + len(regular_games) == selected, True)
                                      for index, (_, title, _) in enumerate(entries[len(regular_games):-1])]
                            lines.append(("", False))
                            kind, title, _ = entries[-1]
                            lines.append((title, selected == len(entries) - 1, True))
                            if not regular_games:
                                lines.insert(0, ("Žiadne hry nie sú dostupné", False, True))
                            lines += [("", False), ("SPACE / START - vybrať | F2 - obnoviť" + suffix, False)]
                        terminal.draw(lines, volume_status(volume), network)
                        redraw = False
                    key = next_input(terminal, pad)
                    now_pad, now_display = pad.available, display.available()
                    if now_pad != previous_pad:
                        notify(settings.providers, "input-added" if now_pad else "input-removed"); previous_pad = now_pad
                    if now_display != previous_display:
                        notify(settings.providers, "display-on" if now_display else "display-off"); previous_display = now_display; redraw = True
                    if key is None: continue
                    if key == "CTRL_C": return MAINTENANCE_EXIT
                    if tools_open and key in ("ESC", "SELECT"):
                        tools_open = False
                        redraw = True
                        continue
                    if key == "F1": network = network_address(); redraw = True
                    elif key == "F2":
                        terminal.draw([("Obnovujem obsah…", True)])
                        redraw = True
                        break
                    elif key in ("LEFT", "RIGHT"):
                        changed = max(0, min(100, volume + (10 if key == "RIGHT" else -10)))
                        if changed != volume and set_audio_volume(changed):
                            volume = changed
                            save_launcher_value(args.config, "audio_volume_percent", volume)
                            redraw = True
                    elif key in (settings.up_key, settings.down_key):
                        offset = -1 if key == settings.up_key else 1
                        if tools_open:
                            tool_selected = (tool_selected + offset) % len(tools)
                            tool_selected_key = entry_key(tools[tool_selected][0], tools[tool_selected][2])
                        else:
                            selected = (selected + offset) % len(entries)
                            selected_key = entry_key(entries[selected][0], entries[selected][2])
                            if selected_key != saved_selected_key:
                                save_launcher_value(args.config, "last_selected_item", selected_key)
                                saved_selected_key = selected_key
                        redraw = True
                    elif key in (settings.confirm_key, "START", "ENTER"):
                        kind, _, value = tools[tool_selected] if tools_open else entries[selected]
                        if kind == "tools":
                            tools_open = True
                            redraw = True
                            continue
                        if kind == "shutdown":
                            confirmed = confirm_shutdown(terminal, pad, settings.confirm_key)
                            if confirmed is None:
                                return MAINTENANCE_EXIT
                            if not confirmed:
                                redraw = True
                                continue
                            try:
                                if not subprocess.run(["sudo", "-n", "/sbin/shutdown", "-h", "now"]).returncode:
                                    return 0
                            except OSError as error:
                                LOG.error("shutdown failed: %s", error)
                            redraw = True
                            continue
                        if kind in ("video", "audio"):
                            run_smoke_test(value, terminal, pad)
                            redraw = True
                            continue
                        game = value
                        # Close every launcher device before the child starts; it owns hardware now.
                        def reacquire():
                            terminal.activate()
                            pad.open()
                        code = run(game.command, terminal, pad.close, reacquire)
                        if code:
                            LOG.warning("guest %s exited with status %d", game.key, code)
                        redraw = True
                        break # Refresh all provider manifests after every guest.
                games, problems = collect(settings.providers)
        finally: pad.close()

if __name__ == "__main__": raise SystemExit(main())
