import os, sys, json, time
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _bot, _simpan, _auth


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if not _auth.sah(self.headers):
            self.send_response(401); self.end_headers(); return
        on = parse_qs(urlparse(self.path).query).get("on", ["1"])[0] == "1"
        r = _simpan.Redis()
        r.set(_bot.K_KILL, on)
        now = time.time()
        r.push(_bot.K_EVT, [{"t": "kill", "waktu": _bot.iso(now), "epoch": int(now), "aktif": on}])
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"kill_switch": on}).encode())
