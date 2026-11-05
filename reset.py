import os, sys, json
from http.server import BaseHTTPRequestHandler
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _bot, _simpan, _auth


class handler(BaseHTTPRequestHandler):
    """Hanya untuk membersihkan data UJI sebelum freeze. Jangan dipakai setelah freeze."""
    def do_GET(self):
        if not _auth.sah(self.headers):
            self.send_response(401); self.end_headers(); return
        r = _simpan.Redis()
        for k in (_bot.K_STATE, _bot.K_KILL, _bot.K_LOCK):
            r.hapus(k)
        r._cmd("DEL", _bot.K_EVT)
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"reset": True}).encode())
