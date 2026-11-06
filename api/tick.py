import os, sys, json
from http.server import BaseHTTPRequestHandler
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _bot, _simpan, _auth


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if not _auth.sah(self.headers):
            return self._kirim(401, {"error": "tidak berwenang"})
        try:
            hasil = _bot.tick(_simpan.Redis())
            self._kirim(200 if hasil["status"] != "gagal" else 500, hasil)
        except Exception as e:
            self._kirim(500, {"error": type(e).__name__, "pesan": str(e)[:120]})

    do_POST = do_GET

    def _kirim(self, kode, obj):
        self.send_response(kode)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(obj).encode())
