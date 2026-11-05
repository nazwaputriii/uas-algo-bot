"""Inti bot dry run Indodax. Satu panggilan tick(): baca state -> ambil data -> sinyal -> eksekusi simulasi -> simpan state dan log.
Hanya API publik Indodax. Tidak ada API key, tidak ada order sungguhan."""
import time, json, hashlib, datetime as dt
import requests
from _config import CFG
import _strategi as S

K_STATE, K_EVT, K_KILL, K_LOCK = "bot:state", "bot:events", "bot:kill", "bot:lock"


def iso(ts):
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def hash_cfg(cfg):
    return hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest()[:12]


class Api:
    BASE = "https://indodax.com"

    def __init__(self, ev):
        self.ev = ev

    def _get(self, path, params=None, tries=3):
        for i in range(tries):                                   # retry terbatas
            try:
                r = requests.get(self.BASE + path, params=params, timeout=15)
                r.raise_for_status()
                return r.json()
            except Exception as e:
                self.ev("error", sumber=path, percobaan=i + 1, jenis=type(e).__name__, pesan=str(e)[:80])
                time.sleep(1.5 * (i + 1))
        return None

    def server_time(self):
        js = self._get("/api/server_time", tries=2)
        try:
            t = float(js["server_time"])
            return t / 1000 if t > 1e12 else t
        except Exception:
            return None

    def candles(self, pair, now, cfg):
        js = self._get("/tradingview/history_v2", {"symbol": pair, "tf": cfg["timeframe"], "from": int(now - 70 * 86400), "to": int(now)})
        if not isinstance(js, list) or not js:
            return None
        out = {}
        for r in js:
            r = {k.lower(): v for k, v in r.items()}
            try:
                t = int(float(r["time"]))
                out[t] = {"time": t, "open": float(r["open"]), "high": float(r["high"]), "low": float(r["low"]),
                          "close": float(r["close"]), "volume": float(r["volume"])}
            except Exception:
                continue
        return [out[k] for k in sorted(out)]

    def book(self, pair):
        js = self._get(f"/api/depth/{pair.lower()}", tries=2)
        try:
            bids = sorted(([float(a), float(b)] for a, b in js["buy"]), reverse=True)
            asks = sorted([float(a), float(b)] for a, b in js["sell"])
            return (bids, asks) if bids and asks else None
        except Exception:
            return None

    def pairs(self):
        js = self._get("/api/pairs", tries=2)
        out = {}
        if isinstance(js, list):
            for p in js:
                k = str(p.get("id") or p.get("ticker_id") or "").replace("_", "").lower()
                if k:
                    out[k] = p
        return out


def tick(store, api_cls=Api, cfg=CFG, now_lokal=None):
    ctx = {"now": now_lokal or time.time()}
    t0 = time.time()
    events = []

    def ev(t, **kw):
        events.append({"t": t, "waktu": iso(ctx["now"]), "epoch": int(ctx["now"]), **kw})

    api = api_cls(ev)
    if not store.kunci(K_LOCK, 240):
        ev("panggilan", status="dilewati", alasan="panggilan lain masih berjalan")
        store.push(K_EVT, events)
        return {"status": "dilewati"}
    status = "ok"
    try:
        _inti(store, api, cfg, ev, ctx)
    except Exception as e:
        status = "gagal"
        ev("error", sumber="tick", jenis=type(e).__name__, pesan=str(e)[:150])
    finally:
        ev("panggilan", status=status, durasi_detik=round(time.time() - t0, 2),
           jumlah_error=sum(1 for e in events if e["t"] == "error"), cfg_hash=hash_cfg(cfg))
        store.push(K_EVT, events)
        store.hapus(K_LOCK)
    return {"status": status, "events": len(events)}


def _inti(store, api, cfg, ev, ctx):
    tf = cfg["tf_detik"]
    st_ = api.server_time()
    if st_:
        ctx["now"] = st_
    else:
        ev("error", sumber="server_time", jenis="fallback", pesan="memakai waktu lokal")
    now = ctx["now"]
    s = store.get(K_STATE)
    if s is None:
        s = {"cash": float(cfg["modal"]), "pos": {}, "last_bar": {}, "pend": {}, "cfg_hash": hash_cfg(cfg),
             "hari": {"tanggal": None, "awal": float(cfg["modal"]), "stop": False}, "mulai": now}
        ev("mulai", modal=cfg["modal"], universe=cfg["universe"], cfg_hash=s["cfg_hash"])
    if s["cfg_hash"] != hash_cfg(cfg):
        ev("perubahan_config", dari=s["cfg_hash"], ke=hash_cfg(cfg))
        s["cfg_hash"] = hash_cfg(cfg)
    kill = bool(store.get(K_KILL))
    info = api.pairs()

    def fee_dan_presisi(p):
        i = info.get(p.lower(), {})
        try:
            fa = float(i.get("trade_fee_percent_taker")) / 100
        except Exception:
            fa = 0.0
        try:
            prec = int(i.get("volume_precision", 8))
        except Exception:
            prec = 8
        return max(cfg["fee_beli"], fa), max(cfg["fee_jual"], fa), fa, prec

    # 1) data candle -> sinyal (hanya bar tertutup, satu kali per candle)
    cand, diproses = [], 0
    for p in cfg["universe"]:
        bars = api.candles(p, now, cfg)
        if not bars:
            ev("data_tidak_valid", pair=p, alasan="candle kosong atau gagal diambil")
            continue
        bars = [b for b in bars if b["time"] + tf <= now]            # buang candle yang masih berjalan
        if not bars:
            ev("data_tidak_valid", pair=p, alasan="tidak ada candle tertutup")
            continue
        i = len(bars) - 1
        T = bars[i]["time"]
        if now - T > cfg["stale_faktor"] * tf:
            ev("data_tidak_valid", pair=p, alasan="candle tertutup terakhir terlalu lama (basi)", bar=T)
            continue
        if T <= s["last_bar"].get(p, 0):
            continue                                                  # sudah diproses (idempotensi)
        alasan = S.validasi(bars, i, cfg)
        if alasan:
            ev("data_tidak_valid", pair=p, alasan=alasan, bar=T)
            continue
        atr = S.atr_seri(bars, cfg["atr_n"])
        lb = s["last_bar"].get(p, 0)
        if lb and T - lb > tf:
            ev("bar_terlewat", pair=p, jumlah=(T - lb) // tf - 1)
        sinyal = None
        if p in s["pos"]:
            ps = s["pos"][p]
            a = S.sinyal_keluar(bars, i, atr, cfg, ps["entry_px"], ps["entry_ts"])
            if a:
                s["pend"][p] = {"sisi": "JUAL", "alasan": a, "harga_sinyal": bars[i]["close"], "bar": T}
                sinyal = "JUAL: " + a
        else:
            m = S.sinyal_masuk(bars, i, atr, cfg)
            if m:
                cand.append((m["roc"], p, bars[i]["close"], T))
                sinyal = "BELI"
        ev("bar", pair=p, bar_time=T, close=bars[i]["close"], atr=atr[i], sinyal=sinyal)
        s["last_bar"][p] = T
        diproses += 1
    slot = cfg["maks_posisi"] - len(s["pos"]) - sum(1 for o in s["pend"].values() if o["sisi"] == "BELI")
    for k, (roc, p, c, T) in enumerate(sorted(cand, reverse=True)):
        if k < slot:
            s["pend"][p] = {"sisi": "BELI", "alasan": "breakout", "harga_sinyal": c, "bar": T}
        else:
            ev("sinyal_ditolak", pair=p, alasan="slot posisi penuh")
    for p in list(s["pend"]):                                         # pending kedaluwarsa
        if now > s["pend"][p]["bar"] + 2 * tf:
            ev("pending_kedaluwarsa", pair=p, **s["pend"][p])
            del s["pend"][p]

    # 2) order book + snapshot, ekuitas
    books = {}
    for p in cfg["universe"]:
        b = api.book(p)
        books[p] = b
        if b:
            bid, ask = b[0][0][0], b[1][0][0]
            ev("snapshot", pair=p, best_bid=bid, best_ask=ask, spread_pct=round((ask - bid) / bid * 100, 4),
               bids=b[0][:10], asks=b[1][:10])
        else:
            ev("data_tidak_valid", pair=p, alasan="order book kosong atau gagal diambil")

    def nilai_pos():
        return sum(ps["qty"] * (books[p][0][0][0] if books.get(p) else ps["entry_px"]) for p, ps in s["pos"].items())

    eq = s["cash"] + nilai_pos()
    tgl = dt.datetime.fromtimestamp(now + cfg["wib_jam"] * 3600, dt.timezone.utc).strftime("%Y-%m-%d")   # hari WIB
    if s["hari"]["tanggal"] != tgl:
        s["hari"] = {"tanggal": tgl, "awal": eq, "stop": False}
        ev("equity_harian", tanggal_wib=tgl, equity=eq, cash=s["cash"], posisi=list(s["pos"]))
    if not s["hari"]["stop"] and eq < s["hari"]["awal"] * (1 - cfg["batas_rugi_harian"]):
        s["hari"]["stop"] = True
        ev("daily_loss_limit", equity=eq, awal_hari=s["hari"]["awal"])

    # 3) eksekusi simulasi di order book live: jual dulu, lalu beli
    def book_ok(p):
        b = books.get(p)
        if not b:
            return None
        if (b[1][0][0] - b[0][0][0]) / b[0][0][0] > cfg["max_spread"]:
            ev("data_tidak_valid", pair=p, alasan="spread bid-ask lebih dari 2%, order ditunda")
            return None
        return b

    for p in [q for q, o in s["pend"].items() if o["sisi"] == "JUAL"]:
        o, ps, b = s["pend"][p], s["pos"].get(p), book_ok(p)
        if not ps or not b:
            continue
        _, fj, fa, prec = fee_dan_presisi(p)
        q, nilai = S.fill_jual(b[0], ps["qty"], prec)
        if q <= 0:
            continue
        fee = nilai * fj
        porsi = q / ps["qty"]
        pnl = nilai - fee - ps["modal"] * porsi
        s["cash"] += nilai - fee
        fill = nilai / q
        ev("order", pair=p, sisi="JUAL", qty=q, best_bid=b[0][0][0], best_ask=b[1][0][0], harga_fill=fill,
           harga_sinyal=o["harga_sinyal"], selisih_vs_sinyal_pct=round((fill / o["harga_sinyal"] - 1) * 100, 4),
           nilai_rp=nilai, fee_rp=fee, fee_pakai=fj, fee_api=fa, alasan=o["alasan"], pnl=pnl)
        if porsi >= 1 - 10 ** -prec / max(ps["qty"], 1e-12) - 1e-9:
            del s["pos"][p]
            del s["pend"][p]
        else:
            ps["qty"] -= q
            ps["modal"] *= 1 - porsi

    if kill and any(o["sisi"] == "BELI" for o in s["pend"].values()):
        ev("kill_switch_tahan", alasan="pembelian baru ditahan karena kill switch aktif")
    elif s["hari"]["stop"] and any(o["sisi"] == "BELI" for o in s["pend"].values()):
        ev("loss_limit_tahan", alasan="pembelian baru ditahan sampai hari WIB berikutnya")
    else:
        for p in [q for q, o in s["pend"].items() if o["sisi"] == "BELI"]:
            o, b = s["pend"][p], book_ok(p)
            if p in s["pos"] or len(s["pos"]) >= cfg["maks_posisi"]:
                del s["pend"][p]
                continue
            if not b:
                continue
            fb, _, fa, prec = fee_dan_presisi(p)
            eq_buka = s["cash"] + nilai_pos()
            anggaran = min(s["cash"], eq_buka / cfg["maks_posisi"])
            q, nilai = S.fill_beli(b[1], anggaran, fb, prec)
            if nilai < cfg["min_order_rp"]:
                ev("order_dilewati", pair=p, alasan="di bawah minimum order atau likuiditas kurang", nilai_rp=nilai)
                del s["pend"][p]
                continue
            fee = nilai * fb
            s["cash"] -= nilai + fee
            fill = nilai / q
            s["pos"][p] = {"qty": q, "entry_px": fill, "entry_ts": now, "modal": nilai + fee}
            ev("order", pair=p, sisi="BELI", qty=q, best_bid=b[0][0][0], best_ask=b[1][0][0], harga_fill=fill,
               harga_sinyal=o["harga_sinyal"], selisih_vs_sinyal_pct=round((fill / o["harga_sinyal"] - 1) * 100, 4),
               nilai_rp=nilai, fee_rp=fee, fee_pakai=fb, fee_api=fa, alasan=o["alasan"], pnl=None)
            del s["pend"][p]

    s["ekuitas_terakhir"] = s["cash"] + nilai_pos()
    store.set(K_STATE, s)
    ev("ringkas", equity=s["ekuitas_terakhir"], cash=s["cash"], posisi=list(s["pos"]), pending=s["pend"], bar_diproses=diproses)
