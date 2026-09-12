"""Local-network dance mat backed by a Linux uinput joystick."""
import fcntl
import os
import struct
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Event, Lock, Thread
from urllib.parse import parse_qs

EV_SYN, EV_KEY, EV_ABS = 0, 1, 3
SYN_REPORT, ABS_X, ABS_Y = 0, 0, 1
BTN_0 = 0x100
UI_SET_EVBIT, UI_SET_KEYBIT, UI_SET_ABSBIT = 0x40045564, 0x40045565, 0x40045567
UI_DEV_CREATE, UI_DEV_DESTROY = 0x5501, 0x5502
EVENT = struct.Struct("llHHI")
ACTIONS = {
    "UP_LEFT": (2, 0), "UP": (2,), "UP_RIGHT": (2, 3),
    "LEFT": (0,), "RIGHT": (3,),
    "DOWN_LEFT": (1, 0), "DOWN": (1,), "DOWN_RIGHT": (1, 3),
    "START": (8,), "SELECT": (9,),
}

PAGE = """<!doctype html>
<html lang="sk"><meta name="viewport" content="width=device-width,initial-scale=1,user-scalable=no">
<title>Tanečná podložka</title><style>
*{box-sizing:border-box}body{margin:0;background:#15151b;color:#fff;font:18px system-ui,sans-serif;text-align:center;touch-action:manipulation}
main{max-width:480px;margin:auto;padding:20px}h1{font-size:1.35rem}.mat{display:grid;grid-template-columns:repeat(3,1fr);gap:9px;background:#292935;padding:14px;border-radius:22px}.pad{min-height:78px;border:0;border-radius:16px;background:#43435a;color:#fff;font-weight:bold;font-size:1rem;box-shadow:0 4px #21212c}.pad:active{background:#00a6a6;transform:translateY(3px);box-shadow:0 1px #21212c}.empty{visibility:hidden}.actions{display:flex;gap:14px;margin-top:18px}.actions .pad{flex:1;min-height:88px}.start{background:#287e54}.select{background:#7d4a8f}p{color:#bfc0ce;font-size:.85rem}
</style><main><h1>Virtuálna tanečná podložka</h1><div class="mat">
<button class="pad" data-action="UP_LEFT">↖<br>HORE VĽAVO</button><button class="pad" data-action="UP">↑<br>HORE</button><button class="pad" data-action="UP_RIGHT">↗<br>HORE VPRAVO</button>
<button class="pad" data-action="LEFT">←<br>VĽAVO</button><span class="empty"></span><button class="pad" data-action="RIGHT">→<br>VPRAVO</button>
<button class="pad" data-action="DOWN_LEFT">↙<br>DOLE VĽAVO</button><button class="pad" data-action="DOWN">↓<br>DOLE</button><button class="pad" data-action="DOWN_RIGHT">↘<br>DOLE VPRAVO</button>
</div><div class="actions"><button class="pad select" data-action="SELECT">SELECT</button><button class="pad start" data-action="START">START</button></div><p>Virtuálny ovládač je pripravený.</p></main>
<script>const send=(a,p)=>fetch('/input',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:'action='+a+'&pressed='+(p?1:0)});document.querySelectorAll('[data-action]').forEach(b=>{let a=b.dataset.action;b.addEventListener('pointerdown',e=>{e.preventDefault();b.setPointerCapture(e.pointerId);send(a,1)});for(let e of ['pointerup','pointercancel'])b.addEventListener(e,()=>send(a,0))});setInterval(()=>send('KEEPALIVE',1),1000);addEventListener('pagehide',()=>document.querySelectorAll('[data-action]').forEach(b=>send(b.dataset.action,0)))</script>"""


class VirtualJoystick:
    def __init__(self, path="/dev/uinput"):
        self.path, self.fd, self.actions, self.created = path, None, set(), False
        self.lock, self.stop, self.last_seen = Lock(), Event(), 0

    def open(self):
        self.fd = os.open(self.path, os.O_WRONLY | os.O_NONBLOCK)
        for event in (EV_SYN, EV_KEY, EV_ABS): fcntl.ioctl(self.fd, UI_SET_EVBIT, event)
        for button in range(10): fcntl.ioctl(self.fd, UI_SET_KEYBIT, BTN_0 + button)
        for axis in (ABS_X, ABS_Y): fcntl.ioctl(self.fd, UI_SET_ABSBIT, axis)
        name = b"WiseGroup.,Ltd X-PAD, Extreme Dance Pad"
        device = struct.pack("80sHHHHI", name, 0x03, 0x1, 0x1, 1, 0) + b"\0" * (64 * 4 * 4)
        os.write(self.fd, device)
        fcntl.ioctl(self.fd, UI_DEV_CREATE)
        self.created = True
        Thread(target=self._watchdog, daemon=True).start()

    def close(self):
        self.stop.set()
        if self.fd is not None:
            if self.created:
                self.release_all()
                fcntl.ioctl(self.fd, UI_DEV_DESTROY)
            os.close(self.fd); self.fd = None

    def set_action(self, action, pressed):
        with self.lock:
            if action == "KEEPALIVE": self.last_seen = time.monotonic(); return
            if action not in ACTIONS: return
            self.last_seen = time.monotonic()
            before = {button for item in self.actions for button in ACTIONS[item]}
            if pressed: self.actions.add(action)
            else: self.actions.discard(action)
            after = {button for item in self.actions for button in ACTIONS[item]}
            for button in before - after: self._event(EV_KEY, BTN_0 + button, 0)
            for button in after - before: self._event(EV_KEY, BTN_0 + button, 1)
            if before != after: self._event(EV_SYN, SYN_REPORT, 0)

    def release_all(self):
        with self.lock:
            for button in {button for item in self.actions for button in ACTIONS[item]}:
                self._event(EV_KEY, BTN_0 + button, 0)
            if self.actions: self._event(EV_SYN, SYN_REPORT, 0)
            self.actions.clear()

    def _event(self, kind, code, value):
        os.write(self.fd, EVENT.pack(0, 0, kind, code, value))

    def _watchdog(self):
        while not self.stop.wait(.25):
            with self.lock:
                expired = self.actions and time.monotonic() - self.last_seen > 2
            if expired: self.release_all()


class VirtualDanceMat:
    def __init__(self, port):
        self.port, self.joystick, self.server, self.thread = port, VirtualJoystick(), None, None

    def open(self):
        self.joystick.open()
        mat = self
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path != "/": self.send_error(404); return
                body = PAGE.encode("utf-8")
                self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
            def do_POST(self):
                try: length = int(self.headers.get("Content-Length", "0"))
                except ValueError: self.send_error(400); return
                if self.path != "/input" or length > 64: self.send_error(404); return
                values = parse_qs(self.rfile.read(length).decode("ascii", "ignore"))
                mat.joystick.set_action(values.get("action", [""])[0], values.get("pressed", ["0"])[0] == "1")
                self.send_response(204); self.end_headers()
            def log_message(self, *_): pass
        self.server = ThreadingHTTPServer(("0.0.0.0", self.port), Handler)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self.server.server_address[1]

    def close(self):
        if self.server:
            self.server.shutdown(); self.server.server_close(); self.server = None
        self.joystick.close()
