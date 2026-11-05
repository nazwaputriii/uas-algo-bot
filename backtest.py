"""
Backtest strategi UAS (dipakai juga oleh hitung_ulang.py). Memakai FUNGSI SINYAL YANG SAMA dengan bot (api/_strategi.py).
Jalankan di Colab/laptop:  python backtest.py   (butuh folder data_4h/ dari tarik_data.py)
"""
import os, sys, csv, json, statistics
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "api"))
from _config import CFG
import _strategi as S


def muat(folder, universe):
    out = {}
    for p in universe:
        with open(f"{folder}/{p}.csv") as f:
            out[p] = [{k: (int(float(v)) if k == "time" else float(v)) for k, v in r.items()} for r in csv.DictReader(f)]
    return out


def spread_dari_snapshot(path, universe):
    """Median spread (setengah) dan slippage per sisi dari snapshots.csv hasil pengumpul snapshot. Return dict pair->(spread_pct, slip_pct)."""
    rows = {}
    if os.path.exists(path):
        for r in csv.DictReader(open(path)):
            if r["pair"] in universe and r["spread_pct"]:
                rows.setdefault(r["pair"], []).append((float(r["spread_pct"]),
                                                       float(r["slip_beli_pct"] or 0), float(r["slip_jual_pct"] or 0)))
    return {p: (statistics.median(x[0] for x in v) / 100, statistics.median((x[1] + x[2]) / 2 for x in v) / 100)
            for p, v in rows.items()}


def jalankan(bars, cfg=CFG, biaya_exec=None, default_exec=(0.0005, 0.0), mulai=None, akhir=None):
    """bars: {pair: [bar,...]} urut waktu. biaya_exec: {pair: (spread_pct, slippage_pct)} (spread penuh bid-ask; dibagi dua per sisi).
    mulai/akhir: batas waktu epoch (jendela evaluasi). Return dict hasil."""
    tf, maxpos = cfg["tf_detik"], cfg["maks_posisi"]
    fb, fj = cfg["fee_beli"], cfg["fee_jual"]
    idx = {p: {b["time"]: i for i, b in enumerate(bs)} for p, bs in bars.items()}
    atr = {p: S.atr_seri(bs, cfg["atr_n"]) for p, bs in bars.items()}
    waktu = sorted({b["time"] for bs in bars.values() for b in bs})
    if mulai:
        waktu = [t for t in waktu if t >= mulai]
    if akhir:
        waktu = [t for t in waktu if t <= akhir]

    def eks(p):
        sp, sl = (biaya_exec or {}).get(p, default_exec)
        return sp / 2 + sl
    cash, pos, pend, trades, sinyal_log, eq = float(cfg["modal"]), {}, {}, [], [], []
    for t in waktu:
        # 1) eksekusi order dari bar sebelumnya di harga buka bar ini
        for p in [q for q, o in pend.items() if o["sisi"] == "JUAL"]:
            if p in pos and t in idx[p]:
                b = bars[p][idx[p][t]]
                px = b["open"] * (1 - eks(p))
                q = pos[p]["qty"]
                nilai = q * px
                fee = nilai * fj
                cash += nilai - fee
                biaya = pos[p]["biaya_beli"] + fee + q * b["open"] * eks(p)
                trades.append({"pair": p, "masuk": pos[p]["ts"], "keluar": t, "harga_masuk": pos[p]["px"], "harga_keluar": px, "qty": q,
                               "pnl": nilai - fee - pos[p]["modal"], "alasan": pend[p]["alasan"], "biaya": biaya})
                del pos[p], pend[p]
        eq_buka = cash + sum(ps["qty"] * bars[p][idx[p][t]]["open"] if t in idx[p] else ps["qty"] * ps["px"] for p, ps in pos.items())
        for p in [q for q, o in pend.items() if o["sisi"] == "BELI"]:
            if p in pos or len(pos) >= maxpos or t not in idx[p]:
                pend.pop(p, None)
                continue
            b = bars[p][idx[p][t]]
            px = b["open"] * (1 + eks(p))
            ang = min(cash, eq_buka / maxpos)
            if ang < cfg["min_order_rp"]:
                pend.pop(p)
                continue
            q = ang / (px * (1 + fb))
            cash -= ang
            pos[p] = {"qty": q, "px": px, "ts": t, "modal": ang, "biaya_beli": q * px * fb + q * b["open"] * eks(p)}
            del pend[p]
        # 2) evaluasi bar yang tutup (bar t) -> sinyal untuk bar berikutnya
        cand = []
        for p, bs in bars.items():
            if t not in idx[p]:
                continue
            i = idx[p][t]
            if S.validasi(bs, i, cfg):
                continue
            if p in pos:
                a = S.sinyal_keluar(bs, i, atr[p], cfg, pos[p]["px"], pos[p]["ts"])
                if a:
                    pend[p] = {"sisi": "JUAL", "alasan": a}
                    sinyal_log.append((t, p, "JUAL"))
            else:
                m = S.sinyal_masuk(bs, i, atr[p], cfg)
                if m:
                    cand.append((m["roc"], p))
        slot = maxpos - len(pos)
        for k, (_, p) in enumerate(sorted(cand, reverse=True)):
            if k < slot:
                pend[p] = {"sisi": "BELI", "alasan": "breakout"}
                sinyal_log.append((t, p, "BELI"))
        eq.append((t + tf, cash + sum(ps["qty"] * (bars[p][idx[p][t]]["close"] if t in idx[p] else ps["px"]) for p, ps in pos.items())))
    return {"equity": eq, "trades": trades, "sinyal": sinyal_log, "posisi_terbuka": list(pos)}


def metrik(h, cfg=CFG):
    eq = [v for _, v in h["equity"]]
    tr = h["trades"]
    modal = cfg["modal"]
    thn = (h["equity"][-1][0] - h["equity"][0][0]) / (365.25 * 86400) if len(eq) > 1 else 0
    puncak, mdd = eq[0], 0.0
    for v in eq:
        puncak = max(puncak, v)
        mdd = min(mdd, v / puncak - 1)
    mg = [t["pnl"] for t in tr if t["pnl"] > 0]
    kl = [t["pnl"] for t in tr if t["pnl"] <= 0]
    bt = sum(t["biaya"] for t in tr)
    kotor = sum(t["pnl"] for t in tr) + bt
    return {"return_total": eq[-1] / modal - 1, "cagr": (eq[-1] / modal) ** (1 / thn) - 1 if thn > 0.5 else None, "mdd": mdd,
            "n_trade": len(tr), "win_rate": len(mg) / len(tr) if tr else None,
            "profit_factor": sum(mg) / abs(sum(kl)) if kl and sum(kl) else None,
            "rata_untung": sum(mg) / len(mg) if mg else None, "rata_rugi": sum(kl) / len(kl) if kl else None,
            "porsi_biaya": bt / kotor if kotor > 0 else None, "ekuitas_akhir": eq[-1], "tahun": thn}


if __name__ == "__main__":
    bars = muat("data_4h", CFG["universe"])
    be = spread_dari_snapshot("data_bot/snapshots.csv", CFG["universe"])
    print("spread/slippage dari snapshot:", be or "BELUM ADA, pakai default 0,05%")
    h = jalankan(bars, CFG, be)
    m = metrik(h)
    json.dump({"metrik": m, "trades": h["trades"], "sinyal": h["sinyal"], "equity": h["equity"]}, open("hasil_backtest.json", "w"))
    for k, v in m.items():
        print(k, round(v, 4) if isinstance(v, float) else v)
