"""Best-effort legacy Pi display state and clean console recovery."""
import fcntl
import logging
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

LOG = logging.getLogger(__name__)
KDSETMODE, KD_TEXT = 0x4B3A, 0x00

def restore_console():
    try: fcntl.ioctl(sys.stdout.fileno(), KDSETMODE, KD_TEXT)
    except OSError: pass
    sys.stdout.write("\x1bc"); sys.stdout.flush()

def tvservice_status(output):
    match = re.search(r"state 0x[0-9a-f]+ \[([^]]+)\]", output, re.I)
    if not match: return None
    mode = match.group(1).upper()
    return True if "HDMI" in mode or "DVI" in mode else False if "OFF" in mode or "UNPLUGGED" in mode else None

class Display:
    def __init__(self):
        self.tvservice = shutil.which("tvservice") or ("/opt/vc/bin/tvservice" if Path("/opt/vc/bin/tvservice").is_file() else None)
        self._next_check, self._state = 0, True
    def available(self):
        if time.monotonic() < self._next_check: return self._state
        self._next_check = time.monotonic() + 2
        if not self.tvservice: return True
        try:
            result = subprocess.run([self.tvservice, "-s"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, timeout=3)
            self._state = tvservice_status(result.stdout) is not False
        except (OSError, subprocess.TimeoutExpired): self._state = True
        return self._state
