"""Small on-device checks for the two appliance hardware paths."""
import os
import subprocess
import sys


def _wait():
    print("\nStlač ľubovoľnú klávesu pre návrat.", flush=True)
    sys.stdin.read(1)


def framebuffer():
    """Exercise the active fbcon console and verify that fb0 is readable."""
    if not os.access("/dev/fb0", os.R_OK):
        raise RuntimeError("/dev/fb0 nie je dostupný")
    result = subprocess.run(["fbset", "-fb", "/dev/fb0"], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "fbset zlyhal")
    # ANSI colour blocks travel through the same legacy console framebuffer as the menu.
    print("\033[2J\033[H\033[41m                \033[42m                \033[44m                \033[0m")
    print("\033[97m\033[45m          TEST FRAMEBUFFERU /dev/fb0          \033[0m")
    _wait()


def audio():
    """Play a short ALSA sine tone through the configured HDMI default."""
    result = subprocess.run(["speaker-test", "-t", "sine", "-f", "440", "-c", "2", "-l", "1"], stderr=subprocess.PIPE, text=True)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "speaker-test zlyhal")
    print("HDMI zvukový test bol prehratý.")
    _wait()
