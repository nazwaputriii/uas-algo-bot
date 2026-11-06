"""Fungsi sinyal, validasi, dan fill order. DIPAKAI SAMA oleh backtest dan bot (rubrik: fungsi sinyal harus sama)."""
import math


def atr_seri(bars, n):
    tr = [None] * len(bars)
    for i in range(1, len(bars)):
        h, l, pc = bars[i]["high"], bars[i]["low"], bars[i - 1]["close"]
        tr[i] = max(h - l, abs(h - pc), abs(l - pc))
    atr = [None] * len(bars)
    for i in range(n, len(bars)):
        atr[i] = sum(tr[i - n + 1:i + 1]) / n
    return atr


def sinyal_masuk(bars, i, atr, cfg):
    n, r = cfg["n_masuk"], cfg["roc_n"]
    if i < max(n, r) or atr[i] is None:
        return None
    hh = max(b["close"] for b in bars[i - n:i])            # hanya bar SEBELUM bar i
    c = bars[i]["close"]
    if c > hh:
        return {"roc": c / bars[i - r]["close"] - 1, "hh": hh}
    return None


def sinyal_keluar(bars, i, atr, cfg, entry_px, entry_ts):
    m = cfg["n_keluar"]
    if i < m or atr[i] is None:
        return None
    ll = min(b["low"] for b in bars[i - m:i])
    c = bars[i]["close"]
    if c < ll:
        return "keluar channel"
    pk = entry_px
    for b in reversed(bars[:i + 1]):                        # close sejak entry (bar yang tutup setelah entry)
        if b["time"] + cfg["tf_detik"] <= entry_ts:
            break
        pk = max(pk, b["close"])
    if c < pk - cfg["atr_k"] * atr[i]:
        return "trailing stop ATR"
    return None


def validasi(bars, i, cfg):
    """Alasan data tidak valid, atau None bila valid."""
    w = max(cfg["n_masuk"], cfg["roc_n"], cfg["atr_n"]) + 1
    if i < w:
        return "data historis kurang"
    for k in range(i - w + 1, i + 1):
        if bars[k]["time"] - bars[k - 1]["time"] != cfg["tf_detik"]:
            return "candle hilang di jendela indikator"
    b = bars[i]
    if min(b["open"], b["high"], b["low"], b["close"]) <= 0 or b["volume"] <= 0:
        return "harga atau volume nol"
    return None


def turun(x, prec):
    f = 10 ** prec
    return math.floor(x * f + 1e-9) / f


def telusuri(levels, qty):
    """Habiskan level order book sampai qty terpenuhi. Return (qty_terisi, nilai_rp)."""
    sisa, nilai = qty, 0.0
    for px, amt in levels:
        j = min(sisa, amt)
        if j <= 0:
            break
        nilai += j * px
        sisa -= j
        if sisa <= 1e-15:
            break
    return qty - sisa, nilai


def qty_dari_anggaran(asks, rp):
    sisa, qty = rp, 0.0
    for px, amt in asks:
        ambil = min(sisa, px * amt)
        if ambil <= 0:
            break
        qty += ambil / px
        sisa -= ambil
        if sisa <= 1e-9:
            break
    return qty


def fill_beli(asks, anggaran, fee, prec):
    """Beli di ask. Return (qty, nilai_tanpa_fee). Tidak pernah memakai mid/close."""
    q = turun(qty_dari_anggaran(asks, anggaran / (1 + fee)), prec)
    if q <= 0:
        return 0.0, 0.0
    return telusuri(asks, q)


def fill_jual(bids, qty, prec):
    q = turun(qty, prec)
    if q <= 0:
        return 0.0, 0.0
    return telusuri(bids, q)
