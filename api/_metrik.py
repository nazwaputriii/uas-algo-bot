"""Hitung semua angka dashboard dari log mentah (events). Dipakai oleh /api/data DAN skrip hitung_ulang.py."""


def hitung(events, cfg):
    modal, tf = cfg["modal"], cfg["tf_detik"]
    mulai = next((e["epoch"] for e in events if e["t"] == "mulai"), None)
    eqh = [(e["tanggal_wib"], e["equity"]) for e in events if e["t"] == "equity_harian"]
    ring = [e for e in events if e["t"] == "ringkas"]
    eq_skrg = ring[-1]["equity"] if ring else modal
    kurva = [modal] + [v for _, v in eqh] + [eq_skrg]
    puncak, mdd = kurva[0], 0.0
    for v in kurva:
        puncak = max(puncak, v)
        mdd = min(mdd, v / puncak - 1)
    orders = [e for e in events if e["t"] == "order"]
    jual = [o for o in orders if o["sisi"] == "JUAL"]
    pnl = [o["pnl"] for o in jual]
    mg = [x for x in pnl if x > 0]
    kl = [x for x in pnl if x <= 0]
    biaya = sum(o["fee_rp"] + o["qty"] * abs(o["harga_fill"] - (o["best_bid"] + o["best_ask"]) / 2) for o in orders)
    laba_kotor = sum(pnl) + biaya
    snaps = [e for e in events if e["t"] == "snapshot" and e["pair"] == "BTCIDR"]
    bh = None
    if len(snaps) >= 2:
        bh = snaps[-1]["best_bid"] * (1 - cfg["fee_jual"]) / (snaps[0]["best_ask"] * (1 + cfg["fee_beli"])) - 1
    # uptime: candle terproses oleh SEMUA pair sebelum candle berikutnya tutup
    bars = {}
    for e in events:
        if e["t"] == "bar":
            bars.setdefault(e["bar_time"], {})[e["pair"]] = e["epoch"]
    tepat = total = 0
    pan = [e for e in events if e["t"] == "panggilan"]
    if mulai and pan:
        akhir = max(e["epoch"] for e in pan)
        k = int(mulai // tf) + 1
        while (k + 1) * tf <= akhir:             # candle yang batas waktunya sudah lewat
            total += 1
            T = (k - 1) * tf
            d = bars.get(T, {})
            if len(d) == len(cfg["universe"]) and all(ep <= (k + 1) * tf for ep in d.values()):
                tepat += 1
            k += 1
    ok = [e for e in pan if e["status"] == "ok"]
    terjadwal = int((max(e["epoch"] for e in pan) - mulai) // 3600) + 1 if mulai and pan else 0
    return {
        "ekuitas_akhir": eq_skrg, "return_total": eq_skrg / modal - 1, "mdd": mdd, "n_trade": len(jual),
        "profit_factor": (sum(mg) / abs(sum(kl))) if kl and sum(kl) != 0 else None,
        "win_rate": len(mg) / len(jual) if jual else None,
        "rata_untung": sum(mg) / len(mg) if mg else None, "rata_rugi": sum(kl) / len(kl) if kl else None,
        "porsi_biaya": biaya / laba_kotor if laba_kotor > 0 else None, "biaya_total": biaya,
        "benchmark_btc_buy_hold": bh,
        "uptime": tepat / total if total else None, "candle_tepat": tepat, "candle_total": total,
        "panggilan_terjadwal": terjadwal, "panggilan_terlaksana": len(ok),
        "error_api": sum(1 for e in events if e["t"] == "error"),
        "kill_switch_dipakai": sum(1 for e in events if e["t"] == "kill"),
        "equity_harian": eqh, "n_order": len(orders),
        "posisi_terbuka": ring[-1]["posisi"] if ring else [],
    }
