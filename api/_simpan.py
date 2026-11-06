"""Penyimpanan state dan log di Redis (Upstash, dari Vercel Marketplace) lewat REST. Kredensial dari environment variable."""
import os, json
import requests


class Redis:
    def __init__(self):
        self.url = os.environ.get("UPSTASH_REDIS_REST_URL") or os.environ.get("KV_REST_API_URL")
        self.token = os.environ.get("UPSTASH_REDIS_REST_TOKEN") or os.environ.get("KV_REST_API_TOKEN")
        if not self.url or not self.token:
            raise RuntimeError("Storage belum dihubungkan (env UPSTASH_REDIS_REST_URL / _TOKEN kosong)")

    def _cmd(self, *args):
        r = requests.post(self.url, headers={"Authorization": f"Bearer {self.token}"}, json=list(args), timeout=15)
        r.raise_for_status()
        return r.json().get("result")

    def get(self, key):
        v = self._cmd("GET", key)
        return json.loads(v) if v else None

    def set(self, key, val):
        self._cmd("SET", key, json.dumps(val))

    def push(self, key, items):
        if items:
            self._cmd("RPUSH", key, *[json.dumps(x) for x in items])

    def semua(self, key):
        return [json.loads(x) for x in (self._cmd("LRANGE", key, 0, -1) or [])]

    def kunci(self, key, detik):
        return self._cmd("SET", key, "1", "NX", "EX", detik) == "OK"

    def hapus(self, key):
        self._cmd("DEL", key)


class Memori:
    """Pengganti Redis untuk uji lokal."""
    def __init__(self):
        self.d, self.l = {}, {}

    def get(self, k):
        return json.loads(json.dumps(self.d[k])) if k in self.d else None

    def set(self, k, v):
        self.d[k] = json.loads(json.dumps(v))

    def push(self, k, items):
        self.l.setdefault(k, []).extend(json.loads(json.dumps(items)))

    def semua(self, k):
        return list(self.l.get(k, []))

    def kunci(self, k, s):
        if k in self.d:
            return False
        self.d[k] = 1
        return True

    def hapus(self, k):
        self.d.pop(k, None)
