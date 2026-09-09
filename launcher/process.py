"""Exclusive handoff between the launcher UI and one guest process."""
import fcntl
import os
import signal
import subprocess
import termios
from .display import restore_console

def _foreground(fd, group):
    previous = signal.signal(signal.SIGTTOU, signal.SIG_IGN)
    try: os.tcsetpgrp(fd, group)
    finally: signal.signal(signal.SIGTTOU, previous)

def run(command, terminal, release, reacquire):
    """Run a guest after completely releasing launcher-owned hardware."""
    fd, saved, group = terminal.fd, termios.tcgetattr(terminal.fd), os.tcgetpgrp(terminal.fd)
    process = None
    try:
        release()
        terminal.deactivate()
        restore_console()
        def claim_console():
            os.setpgrp(); _foreground(fd, os.getpgrp())
        process = subprocess.Popen(command, preexec_fn=claim_console)
        return process.wait()
    finally:
        if process is not None and process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try: process.wait(timeout=2)
            except subprocess.TimeoutExpired: os.killpg(process.pid, signal.SIGKILL)
        _foreground(fd, group)
        termios.tcsetattr(fd, termios.TCSAFLUSH, saved)
        restore_console()
        reacquire()
