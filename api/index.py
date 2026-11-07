"""Pintu masuk tunggal: meneruskan permintaan ke tick/data/export/kill/reset dan menyajikan dashboard (/)."""
import os, sys, json
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tick, data, export, kill, reset

RUTE = {"/api/tick": tick.handler, "/api/data": data.handler, "/api/export": export.handler,
        "/api/kill": kill.handler, "/api/reset": reset.handler}
HALAMAN = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "index.html")


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlparse(self.path).path.rstrip("/") or "/"
        kelas = RUTE.get(path)
        if kelas:
            self.__class__ = kelas          # serahkan ke handler asli (auth tetap berlaku di sana)
            return kelas.do_GET(self)
        if path in ("/", "/index.html", "/api"):
            try:
                isi, tipe = open(HALAMAN, "rb").read(), "text/html; charset=utf-8"
            except Exception:
                isi, tipe = "Bot dry run Indodax aktif. Data: /api/data".encode(), "text/plain; charset=utf-8"
            self.send_response(200)
            self.send_header("Content-Type", tipe)
            self.end_headers()
            self.wfile.write(isi)
            return
        self.send_response(404)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"error": "tidak ditemukan"}).encode())

    do_POST = do_GET
