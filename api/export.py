import os, sys, json
from http.server import BaseHTTPRequestHandler
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _bot, _simpan, _auth


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if not _auth.sah(self.headers):
            self.send_response(401); self.end_headers(); return
        r = _simpan.Redis()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"events": r.semua(_bot.K_EVT), "state": r.get(_bot.K_STATE)}).encode())
