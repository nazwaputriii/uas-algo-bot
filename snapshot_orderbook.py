"""
Pengumpul snapshot order book Indodax (API publik, tanpa API key, tanpa order).
Dipanggil tiap jam oleh GitHub Actions. Hasil: data_bot/snapshots.csv (ringkas) dan
data_bot/snapshots_mentah.jsonl (20 level teratas, mentah) untuk estimasi spread dan slippage backtest.
"""
import os, json, time, csv, datetime as dt
import requests

PAIRS = ["BTCIDR", "ETHIDR", "XRPIDR", "SOLIDR", "DOGEIDR", "ADAIDR", "BNBIDR", "TRXIDR", "LINKIDR", "LTCIDR", "DOTIDR"]
UKURAN_ORDER_RP = 100_000_000 / 6      # ukuran order referensi (modal / maks posisi) untuk ukur slippage
OUT = "data_bot"
os.makedirs(OUT, exist_ok=True)
now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def ambil(pair):
    for i in range(3):
        try:
            r = requests.get(f"https://indodax.com/api/depth/{pair.lower()}", timeout=20)
            r.raise_for_status()
            js = r.json()
            bids = sorted(([float(a), float(b)] for a, b in js["buy"]), reverse=True)
            asks = sorted([float(a), float(b)] for a, b in js["sell"])
            if bids and asks:
                return bids, asks
        except Exception as e:
            print(pair, "percobaan", i + 1, "gagal:", type(e).__name__, str(e)[:80])
            time.sleep(2)
    return None


def vwap_beli(asks, rp):
    sisa, qty = rp, 0.0
    for px, amt in asks:
        ambil_rp = min(sisa, px * amt)
        qty += ambil_rp / px
        sisa -= ambil_rp
        if sisa <= 0:
            break
    return (rp - sisa) / qty if qty and sisa <= 1 else None      # None = order book tidak cukup dalam


def vwap_jual(bids, rp):
    sisa, hasil = rp / bids[0][0], 0.0                           # kuantitas setara rp pada bid terbaik
    qty0 = sisa
    for px, amt in bids:
        j = min(sisa, amt)
        hasil += j * px
        sisa -= j
        if sisa <= 1e-12:
            break
    return hasil / qty0 if sisa <= 1e-9 else None


baru = not os.path.exists(f"{OUT}/snapshots.csv")
ok = 0
with open(f"{OUT}/snapshots.csv", "a", newline="") as f, open(f"{OUT}/snapshots_mentah.jsonl", "a") as g:
    w = csv.writer(f)
    if baru:
        w.writerow(["waktu_utc", "pair", "best_bid", "best_ask", "spread_pct", "slip_beli_pct", "slip_jual_pct"])
    for p in PAIRS:
        b = ambil(p)
        time.sleep(0.4)
        if not b:
            w.writerow([now, p, "", "", "", "", ""])             # kegagalan juga dicatat
            continue
        bids, asks = b
        sp = (asks[0][0] - bids[0][0]) / bids[0][0] * 100
        vb, vj = vwap_beli(asks, UKURAN_ORDER_RP), vwap_jual(bids, UKURAN_ORDER_RP)
        sb = (vb / asks[0][0] - 1) * 100 if vb else ""
        sj = (1 - vj / bids[0][0]) * 100 if vj else ""
        w.writerow([now, p, bids[0][0], asks[0][0], round(sp, 4), round(sb, 4) if sb != "" else "", round(sj, 4) if sj != "" else ""])
        g.write(json.dumps({"waktu_utc": now, "pair": p, "bids": bids[:20], "asks": asks[:20]}) + "\n")
        ok += 1
print(f"{now}: {ok}/{len(PAIRS)} pair berhasil")
