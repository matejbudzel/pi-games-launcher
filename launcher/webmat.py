"""Small local-network virtual dance mat for the launcher menu."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from queue import Empty, Queue
from threading import Lock, Thread


ACTIONS = {
    "UP_LEFT": ("UP", "LEFT"), "UP": ("UP",), "UP_RIGHT": ("UP", "RIGHT"),
    "LEFT": ("LEFT",), "RIGHT": ("RIGHT",),
    "DOWN_LEFT": ("DOWN", "LEFT"), "DOWN": ("DOWN",), "DOWN_RIGHT": ("DOWN", "RIGHT"),
    "START": ("START",), "SELECT": ("SELECT",),
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
</div><div class="actions"><button class="pad select" data-action="SELECT">SELECT</button><button class="pad start" data-action="START">START</button></div><p>Ovládanie je dostupné iba v menu launchera.</p></main>
<script>document.querySelectorAll('[data-action]').forEach(b=>b.addEventListener('pointerdown',e=>{e.preventDefault();fetch('/input',{method:'POST',body:b.dataset.action})}))</script>"""


class VirtualDanceMat:
    def __init__(self, port):
        self.port, self.events, self.active = port, Queue(), False
        self.lock, self.server, self.thread = Lock(), None, None

    def open(self):
        mat = self
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path != "/": self.send_error(404); return
                body = PAGE.encode("utf-8")
                self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)
            def do_POST(self):
                if self.path != "/input" or int(self.headers.get("Content-Length", "0")) > 32:
                    self.send_error(404); return
                action = self.rfile.read(int(self.headers.get("Content-Length", "0"))).decode("ascii", "ignore")
                mat.feed(action)
                self.send_response(204); self.end_headers()
            def log_message(self, *_): pass
        self.server = ThreadingHTTPServer(("0.0.0.0", self.port), Handler)
        self.thread = Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self.server.server_address[1]

    def close(self):
        if self.server:
            self.server.shutdown(); self.server.server_close(); self.server = None

    def set_active(self, active):
        with self.lock:
            self.active = active
            if not active: self.clear()

    def clear(self):
        while True:
            try: self.events.get_nowait()
            except Empty: return

    def feed(self, action):
        with self.lock:
            if self.active:
                for key in ACTIONS.get(action, ()): self.events.put(key)

    def action(self):
        try: return self.events.get_nowait()
        except Empty: return None
