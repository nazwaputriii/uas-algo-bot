import os, sys, json
from http.server import BaseHTTPRequestHandler
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _bot, _simpan, _metrik
from _config import CFG


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            ev = _simpan.Redis().semua(_bot.K_EVT)
            ringan = [{k: v for k, v in e.items() if k not in ("bids", "asks")} for e in ev if e["t"] != "snapshot"][-300:]
            out = {"cfg": CFG, "metrik": _metrik.hitung(ev, CFG), "events_terakhir": ringan}
            kode = 200
        except Exception as e:
            out, kode = {"error": type(e).__name__}, 500
        self.send_response(kode)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(json.dumps(out).encode())
