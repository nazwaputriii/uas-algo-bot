"""
hitung_ulang.py - menghasilkan ULANG semua angka dashboard dari log mentah, lalu membuat dashboard_offline.html.

Letakkan di folder utama repo (sejajar backtest.py). Butuh:
  data_bot/export_log_mentah.json   log mentah forward test (hasil /api/export)
  data_bot/snapshots.csv            snapshot order book (spread untuk backtest)
  data_4h/<PAIR>.csv                candle 4 jam dari tarik_data.py (tarik ulang agar mencakup seluruh jendela forward)
  dashboard_template.html           kerangka halaman (tanpa angka)

Jalankan:  python hitung_ulang.py
Hasil:     hasil_hitung.json dan dashboard_offline.html (bisa dibuka tanpa internet)

Angka forward test dihitung oleh api/_metrik.py, fungsi yang sama dengan /api/data di Vercel.
Backtest dijalankan ulang oleh backtest.py, yang memakai fungsi sinyal sama dengan bot (api/_strategi.py).
Candle yang belum tertutup pada saat log terakhir dibuang, sesuai aturan soal.
"""
import os, sys, re, json, statistics, datetime as dt

AKAR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(AKAR, "api"))
sys.path.insert(0, AKAR)
from _config import CFG
import _metrik
import backtest as B

WIB = dt.timezone(dt.timedelta(hours=7))


def wib(ts):
    return dt.datetime.fromtimestamp(ts, WIB).strftime("%d %b %Y %H.%M WIB")


def utc(ts):
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).strftime("%Y-%m-%d %H:%M")


def buy_hold(bars_btc, cfg):
    return bars_btc[-1]["close"] * (1 - cfg["fee_jual"]) / (bars_btc[0]["open"] * (1 + cfg["fee_beli"])) - 1


def main():
    log = json.load(open(os.path.join(AKAR, "data_bot", "export_log_mentah.json")))
    ev = log["events"]
    akhir_log = max(e["epoch"] for e in ev)
    tf = CFG["tf_detik"]

    # 1) angka forward test, fungsi yang sama dengan /api/data
    fw = _metrik.hitung(ev, CFG)

    # 2) backtest penuh dari candle CSV (hanya candle yang sudah tertutup saat log terakhir)
    bars = B.muat(os.path.join(AKAR, "data_4h"), CFG["universe"])
    bars = {p: [b for b in bs if b["time"] + tf <= akhir_log] for p, bs in bars.items()}
    be = B.spread_dari_snapshot(os.path.join(AKAR, "data_bot", "snapshots.csv"), CFG["universe"])
    h = B.jalankan(bars, CFG, be)
    bt = B.metrik(h)
    eq = h["equity"]
    langkah = max(1, len(eq) // 400)
    eq_kecil = eq[::langkah] + ([eq[-1]] if (len(eq) - 1) % langkah else [])

    # 3) backtest pada jendela candle yang sama dengan forward test
    bar_ev = [e for e in ev if e["t"] == "bar"]
    jend = {"dari": "-", "sampai": "-", "bar_forward": 0, "close_total": 0, "close_cocok": 0, "sinyal_forward": 0,
            "sinyal_backtest": 0, "sinyal_identik": 0, "bar_terlewat": 0, "selisih": [], "metrik_backtest": {}, "btc_buy_hold": None}
    if bar_ev:
        t0, t1 = min(e["bar_time"] for e in bar_ev), max(e["bar_time"] for e in bar_ev)
        hw = B.jalankan(bars, CFG, be, mulai=t0, akhir=t1)
        mw = B.metrik(hw) if len(hw["equity"]) > 1 else {}
        sf = {(e["bar_time"], e["pair"], "BELI" if e["sinyal"] == "BELI" else "JUAL") for e in bar_ev if e["sinyal"]}
        sb = set(hw["sinyal"])
        idx = {p: {b["time"]: b for b in bs} for p, bs in bars.items()}
        cocok = total = 0
        selisih = []
        for e in bar_ev:
            c = idx[e["pair"]].get(e["bar_time"])
            if not c:
                continue
            total += 1
            if abs(c["close"] - e["close"]) <= 1e-9 * max(1.0, abs(c["close"])):
                cocok += 1
            else:
                selisih.append(f'{e["pair"]} {utc(e["bar_time"])} UTC: log {e["close"]} vs CSV {c["close"]}')
        for s in sorted(sf ^ sb):
            selisih.append(("hanya di forward: " if s in sf else "hanya di backtest: ") + f"{s[1]} {s[2]} {utc(s[0])} UTC")
        btc = [b for b in bars["BTCIDR"] if t0 <= b["time"] <= t1]
        jend = {"dari": utc(t0), "sampai": utc(t1), "bar_forward": len(bar_ev), "close_total": total, "close_cocok": cocok,
                "sinyal_forward": len(sf), "sinyal_backtest": len(sb), "sinyal_identik": len(sf & sb),
                "bar_terlewat": sum(e.get("jumlah", 0) for e in ev if e["t"] == "bar_terlewat"), "selisih": selisih[:20],
                "metrik_backtest": mw, "btc_buy_hold": buy_hold(btc, CFG) if len(btc) > 1 else None}

    # 4) spread: yang dipakai backtest vs median seluruh snapshot di log forward
    spread = {}
    for p in CFG["universe"]:
        v = [e["spread_pct"] for e in ev if e["t"] == "snapshot" and e["pair"] == p]
        spread[p] = {"backtest_pct": round(be[p][0] * 100, 5) if p in be else None,
                     "snapshot_median_pct": round(statistics.median(v), 5) if v else None, "n_snapshot": len(v)}

    orders = [{k: e.get(k) for k in ("waktu", "pair", "sisi", "qty", "best_bid", "best_ask", "harga_fill",
                                       "selisih_vs_sinyal_pct", "fee_rp")} for e in ev if e["t"] == "order"]
    mulai = next((e["epoch"] for e in ev if e["t"] == "mulai"), None)
    readme = open(os.path.join(AKAR, "README.md"), encoding="utf-8").read() if os.path.exists(os.path.join(AKAR, "README.md")) else ""
    m = re.search(r"Waktu freeze/mulai:\*\*\s*(.+)", readme)

    data = {
        "dibuat": dt.datetime.now(WIB).strftime("%d %b %Y %H.%M WIB"),
        "cfg_hash": next((e["cfg_hash"] for e in reversed(ev) if e.get("cfg_hash")), "-"),
        "freeze": m.group(1).split(" - ")[0].replace("_", " ").strip() if m else "lihat README",
        "forward_mulai": wib(mulai) if mulai else "-", "forward_akhir": wib(akhir_log),
        "backtest": {"metrik": bt, "equity": eq_kecil, "btc_buy_hold": buy_hold(bars["BTCIDR"], CFG),
                     "periode": [utc(eq[0][0] - tf), utc(eq[-1][0] - tf)]},
        "forward": {"metrik": fw, "equity_harian": fw["equity_harian"], "orders": orders},
        "jendela": jend, "spread": spread,
    }
    json.dump(data, open(os.path.join(AKAR, "hasil_hitung.json"), "w"), indent=1, ensure_ascii=False)
    html = open(os.path.join(AKAR, "dashboard_template.html"), encoding="utf-8").read()
    isi = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    open(os.path.join(AKAR, "dashboard_offline.html"), "w", encoding="utf-8").write(html.replace("/*DATA*/null", isi))

    print("Backtest penuh :", {k: (round(v, 4) if isinstance(v, float) else v) for k, v in bt.items()})
    print("Forward test   :", {k: (round(v, 4) if isinstance(v, float) else v) for k, v in fw.items() if k not in ("equity_harian",)})
    print("Jendela forward:", {k: v for k, v in jend.items() if k not in ("metrik_backtest",)})
    print("Selesai: hasil_hitung.json dan dashboard_offline.html dibuat.")


if __name__ == "__main__":
    main()
