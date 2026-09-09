"""Launcher-only keyboard and direct joystick discovery."""
import fcntl
import glob
import os
import struct
import time

JS_EVENT = struct.Struct("IhBB")
PAD_DEVICE_NAME = "WiseGroup.,Ltd X-PAD, Extreme Dance Pad"
JSIOCGNAME, JSIOCGAXES, JSIOCGBUTTONS = 0x80806A13, 0x80016A11, 0x80016A12
PAD_ACTIONS = {2: "UP", 1: "DOWN", 0: "LEFT", 3: "RIGHT", 8: "START", 9: "SELECT"}


def known_dance_pad(name, axes, buttons):
    return name == PAD_DEVICE_NAME or (axes == 2 and buttons == 10)


class DancePad:
    def __init__(self): self.devices, self.next_scan = {}, 0
    def open(self): self.scan(); return self
    def close(self):
        for fd in self.devices.values():
            try: os.close(fd)
            except OSError: pass
        self.devices.clear()
    @property
    def available(self): return bool(self.devices)
    def scan(self):
        current = set(glob.glob("/dev/input/js*"))
        for path, fd in list(self.devices.items()):
            if path not in current:
                os.close(fd); del self.devices[path]
        for path in current - set(self.devices):
            fd = None
            try:
                fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
                name = fcntl.ioctl(fd, JSIOCGNAME, b"\0" * 128).split(b"\0", 1)[0].decode("utf-8", "replace")
                if known_dance_pad(name, fcntl.ioctl(fd, JSIOCGAXES, b"\0")[0], fcntl.ioctl(fd, JSIOCGBUTTONS, b"\0")[0]):
                    self.devices[path] = fd; fd = None
            except OSError: pass
            finally:
                if fd is not None: os.close(fd)
        self.next_scan = time.monotonic() + 2
    def buttons(self):
        pressed = []
        for path, fd in list(self.devices.items()):
            try: raw = os.read(fd, JS_EVENT.size * 32)
            except BlockingIOError: continue
            except OSError: raw = b""
            if not raw:
                try: os.close(fd)
                except OSError: pass
                del self.devices[path]; continue
            for _, value, kind, number in JS_EVENT.iter_unpack(raw):
                if kind == 1 and value == 1: pressed.append(number)
        if time.monotonic() >= self.next_scan: self.scan()
        return pressed
