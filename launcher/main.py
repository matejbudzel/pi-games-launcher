#!/usr/bin/env python3
"""Text-only console UI. It knows providers only through their manifests."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import logging
import os
import select
import subprocess
import sys
import termios
import time
import tty
from pathlib import Path
from .config import load
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


def highlight_color(name):
    return HIGHLIGHT_COLORS[sum((index + 1) * ord(letter) for index, letter in enumerate(name)) % len(HIGHLIGHT_COLORS)]

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
        return {b"\x03":"CTRL_C", b"\x1b":"ESC", b"\x1b[A":"UP", b"\x1bOA":"UP", b"\x1b[B":"DOWN", b"\x1bOB":"DOWN", b" ":"SPACE", b"\r":"ENTER"}.get(data, data.decode("utf-8", "ignore").upper())
    def draw(self, lines):
        size = os.get_terminal_size(sys.stdout.fileno())
        out = ["\x1b[2J\x1b[H", "\r\n" * max(0, (size.lines - len(lines)) // 2)]
        for line in lines:
            text, selected = line[:2]
            dim = len(line) > 2 and line[2]
            prefix, suffix = ("> ", " <") if selected else ("", "")
            text = text[:max(0, size.columns - len(prefix) - len(suffix))]
            tone = highlight_color(text) if selected else "\x1b[2;37m" if dim else "\x1b[37m"
            out.append(tone + " " * max(0, (size.columns-len(text)-len(prefix)-len(suffix)) // 2) + prefix + text + suffix + "\x1b[0m\r\n")
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

def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "config" / "launcher.conf")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args(argv)
    logging.basicConfig(level=getattr(logging, args.log_level.upper(), logging.INFO), format="%(levelname)s: %(message)s")
    selected = 0
    redraw = True
    display = Display()
    with Terminal() as terminal:
        settings = wait_for_config(terminal, args.config)
        if settings is None:
            return 0
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
                entries = [("game", game.title, game) for game in games]
                entries += [("video", "Test obrazu framebufferu", smoke.framebuffer), ("audio", "Test HDMI zvuku", smoke.audio), ("shutdown", "Koniec", None)]
                selected %= len(entries)
                while True:
                    if redraw:
                        suffix = " (displej nie je dostupný)" if not display.available() else ""
                        lines = [(title, index == selected, kind != "game") for index, (kind, title, _) in enumerate(entries[:len(games)])]
                        if games:
                            lines.append(("", False))
                        lines += [(title, index + len(games) == selected, True) for index, (_, title, _) in enumerate(entries[len(games):2 + len(games)])]
                        lines.append(("", False))
                        kind, title, _ = entries[-1]
                        lines.append((title, selected == len(entries) - 1, True))
                        if not games:
                            lines.insert(0, ("Žiadne hry nie sú dostupné", False, True))
                        lines += [("", False), ("SPACE / START - vybrať" + suffix, False)]
                        terminal.draw(lines)
                        redraw = False
                    key = next_input(terminal, pad)
                    now_pad, now_display = pad.available, display.available()
                    if now_pad != previous_pad:
                        notify(settings.providers, "input-added" if now_pad else "input-removed"); previous_pad = now_pad
                    if now_display != previous_display:
                        notify(settings.providers, "display-on" if now_display else "display-off"); previous_display = now_display; redraw = True
                    if key is None: continue
                    if key == "CTRL_C": return 0
                    if key == settings.up_key: selected = (selected - 1) % len(entries); redraw = True
                    elif key == settings.down_key: selected = (selected + 1) % len(entries); redraw = True
                    elif key in (settings.confirm_key, "START", "ENTER"):
                        kind, _, value = entries[selected]
                        if kind == "shutdown":
                            confirmed = confirm_shutdown(terminal, pad, settings.confirm_key)
                            if confirmed is None:
                                return 0
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
