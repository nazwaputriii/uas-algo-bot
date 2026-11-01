"""
UAS Algoritma Trading - BOT PAPER TRADING Indodax (cicilan 3b).
Tidak ada order asli dan tidak memakai API key. Hanya membaca data publik.
Strategi sama dengan backtest (Donchian breakout + keluar channel / trailing ATR, long-only, harian).
Dijalankan tiap jam oleh GitHub Actions. Aman dijalankan berulang: satu bar hanya diproses sekali.
Token Telegram dibaca dari GitHub Secrets (TELEGRAM_TOKEN, TELEGRAM_CHAT_ID), bukan dari kode.
Kill switch: buat file bernama KILL_SWITCH di repo -> bot berhenti membuka posisi baru (keluar posisi tetap jalan).
"""
import os, sys, json, csv, time, hashlib, datetime as dt
import requests
import pandas as pd

BASE = "https://indodax.com"
D_OUT = "data_bot"
F_STATE, F_TRADES, F_EQ = f"{D_OUT}/state.json", f"{D_OUT}/trades.csv", f"{D_OUT}/equity.csv"
F_RUNS, F_LOG = f"{D_OUT}/runs.csv", f"{D_OUT}/log.txt"
CFG_FILE = "freeze_config.json"
BATAS_RUGI_HARIAN = 0.05      # hentikan pembelian baru bila ekuitas turun 5% dari awal hari (UTC)
MAX_SPREAD = 0.02             # spread bid/ask > 2% dianggap tidak wajar -> order ditunda
ATR_N, ROC_N = 14, 126
ERRORS = []
NOW = time.time()


def stamp():
    return dt.datetime.fromtimestamp(NOW, dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def log(msg, level="INFO"):
    line = f"{stamp()} [{level}] {msg}"
    print(line, flush=True)
    os.makedirs(D_OUT, exist_ok=True)
    with open(F_LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    if level == "ERROR":
        ERRORS.append(msg)


def tg(text):
    t, c = os.environ.get("TELEGRAM_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not t or not c:
        print("[telegram dilewati]", text.replace("\n", " | "))
        return
    try:
        requests.post(f"https://api.telegram.org/bot{t}/sendMessage", data={"chat_id": c, "text": text}, timeout=20)
    except Exception as e:                      # JANGAN cetak isi error: bisa memuat token di URL
        log(f"Telegram gagal terkirim ({type(e).__name__})", "WARN")


def http_get(url, params=None, tries=3):
    for i in range(tries):
        try:
            r = requests.get(url, params=params, timeout=20)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            log(f"API error {url.replace(BASE, '')} percobaan {i + 1}: {type(e).__name__} {str(e)[:80]}", "ERROR")
            time.sleep(2 * (i + 1))
    return None


# ---------------- data ----------------
def candles(pair, now_ts):
    """Candle harian. Hanya bar yang SUDAH LENGKAP (bar yang masih berjalan dibuang)."""
    js = http_get(BASE + "/tradingview/history_v2",
                  {"symbol": pair, "tf": "1D", "from": int(now_ts - 420 * 86400), "to": int(now_ts)})
    if not isinstance(js, list) or not js:
        return None
    df = pd.DataFrame(js)
    df.columns = [c.lower() for c in df.columns]
    for c in ["time", "open", "high", "low", "close", "volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["time", "close"]).drop_duplicates("time").sort_values("time").reset_index(drop=True)
    return df[df["time"] + 86400 <= now_ts].reset_index(drop=True)


def book(pair):
    """Order book: (bids terbaik dulu, asks terbaik dulu)."""
    p = pair.lower()[:-3] + "_idr"
    for url in (f"{BASE}/api/{p}/depth", f"{BASE}/api/depth/{p}"):
        js = http_get(url, tries=2)
        if isinstance(js, dict):
            b, a = js.get("buy") or js.get("bids"), js.get("sell") or js.get("asks")
            if b and a:
                bids = sorted(([float(x), float(y)] for x, y in b), reverse=True)
                asks = sorted([float(x), float(y)] for x, y in a)
                return bids, asks
    return None


def indikator(df, pr):
    C, H, L = df["close"], df["high"], df["low"]
    pc = C.shift(1)
    tr = pd.concat([H - L, (H - pc).abs(), (L - pc).abs()], axis=1).max(axis=1)
    df["hh"] = C.shift(1).rolling(pr["n_masuk"]).max()      # hanya data SEBELUM bar ini
    df["ll"] = L.shift(1).rolling(pr["n_keluar"]).min()
    df["atr"] = tr.rolling(ATR_N).mean()
    df["roc"] = C / C.shift(ROC_N) - 1
    return df


# ---------------- eksekusi paper (jalan di order book) ----------------
def fill_beli(asks, anggaran, fee):
    """Beli dengan menelusuri ask. Mengembalikan (qty, biaya_tanpa_fee). Tidak pernah memakai harga tengah."""
    sisa, qty, biaya = anggaran / (1 + fee), 0.0, 0.0
    for px, amt in asks:
        ambil = min(sisa - biaya, px * amt)
        if ambil <= 0:
            break
        qty += ambil / px
        biaya += ambil
    return qty, biaya


def fill_jual(bids, qty):
    """Jual dengan menelusuri bid. Mengembalikan (qty_terjual, hasil_kotor)."""
    sisa, terjual, hasil = qty, 0.0, 0.0
    for px, amt in bids:
        j = min(sisa, amt)
        if j <= 0:
            break
        terjual += j
        hasil += j * px
        sisa -= j
    return terjual, hasil


# ---------------- state ----------------
def hash_cfg(cfg):
    inti = {k: cfg[k] for k in ("universe", "params", "maks_posisi", "fee_beli", "fee_jual", "modal", "min_order_rp")}
    inti["batas_rugi_harian"] = BATAS_RUGI_HARIAN
    return hashlib.sha256(json.dumps(inti, sort_keys=True).encode()).hexdigest()[:12]


def simpan(state):
    os.makedirs(D_OUT, exist_ok=True)
    tmp = F_STATE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=1)
    os.replace(tmp, F_STATE)          # tulis atomik: state tidak rusak kalau proses mati di tengah


def catat_trade(row):
    baru = not os.path.exists(F_TRADES)
    with open(F_TRADES, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if baru:
            w.writerow(["waktu_utc", "pair", "sisi", "qty", "harga_vwap", "nilai_rp", "fee_rp", "alasan", "pnl_rp"])
        w.writerow(row)


def rp(x):
    return f"Rp{x:,.0f}".replace(",", ".")


# ---------------- inti ----------------
def jalankan(cfg):
    pr, maxpos = cfg["params"], cfg["maks_posisi"]
    fb, fs = cfg["fee_beli"], cfg["fee_jual"]
    today = dt.datetime.fromtimestamp(NOW, dt.timezone.utc).strftime("%Y-%m-%d")
    os.makedirs(D_OUT, exist_ok=True)

    if os.path.exists(F_STATE):
        S = json.load(open(F_STATE))
    else:
        S = {"cash": float(cfg["modal"]), "pos": {}, "pend_beli": [], "pend_jual": {}, "last_bar": 0, "hash": hash_cfg(cfg),
             "freeze": today, "day": {"date": today, "awal": float(cfg["modal"]), "stop": False}, "eq_harian": {}, "perubahan": []}
        log(f"Run pertama. Parameter DIBEKUKAN tanggal {today}, kode {S['hash']}")
        tg(f"Bot aktif. Parameter dibekukan {today} (kode {S['hash']}).\nModal virtual {rp(cfg['modal'])}. Mode: paper trading.")
        simpan(S)          # simpan segera supaya tanggal freeze tidak berubah walau data gagal diambil
    h = hash_cfg(cfg)
    if h != S["hash"]:
        S["perubahan"].append({"tanggal": today, "dari": S["hash"], "ke": h})
        log(f"PERUBAHAN SETELAH FREEZE: kode {S['hash']} -> {h}", "WARN")
        tg(f"PERINGATAN: konfigurasi berubah setelah freeze ({S['hash']} -> {h}). Catat di laporan.")
        S["hash"] = h

    # 1) data
    D = {}
    for p in cfg["universe"]:
        df = candles(p, NOW)
        if df is None or len(df) < ROC_N + 5:
            log(f"{p}: data tidak cukup/gagal diambil, dilewati", "ERROR")
            continue
        D[p] = indikator(df, pr)
    if not D:
        return S, False
    T = max(int(d["time"].iloc[-1]) for d in D.values())      # bar lengkap terbaru
    bar_baru = T > S["last_bar"]

    # 2) sinyal dari bar lengkap terbaru (hanya sekali per bar)
    if bar_baru:
        if S["last_bar"] and T - S["last_bar"] > 86400:
            log(f"Ada {(T - S['last_bar']) // 86400 - 1} bar terlewat (bot sempat tidak jalan)", "WARN")
        S["pend_beli"], S["pend_jual"], cand = [], {}, []
        for p, d in D.items():
            if int(d["time"].iloc[-1]) != T:
                log(f"{p}: data basi (bar terakhir bukan yang terbaru), tidak dipakai untuk sinyal", "WARN")
                continue
            r = d.iloc[-1]
            if p in S["pos"]:
                ps = S["pos"][p]
                pk = max([ps["entry_px"]] + d[d["time"] + 86400 > ps["entry_ts"]]["close"].tolist())
                if pd.notna(r["ll"]) and r["close"] < r["ll"]:
                    S["pend_jual"][p] = "keluar channel"
                elif pd.notna(r["atr"]) and r["close"] < pk - pr["atr_k"] * r["atr"]:
                    S["pend_jual"][p] = "trailing stop ATR"
            elif all(pd.notna(r[k]) for k in ("hh", "atr", "roc")) and r["close"] > r["hh"]:
                cand.append((r["roc"], p))
        slots = max(maxpos - len(S["pos"]), 0)
        S["pend_beli"] = [p for _, p in sorted(cand, reverse=True)[:slots]]
        S["last_bar"] = T
        log(f"Bar {dt.datetime.fromtimestamp(T, dt.timezone.utc):%Y-%m-%d} diproses. Sinyal beli: {S['pend_beli']} jual: {S['pend_jual']}")
        simpan(S)

    # 3) ekuitas saat ini (nilai posisi di harga bid)
    buku, def_harga = {}, {p: D[p]["close"].iloc[-1] for p in D}

    def ambil_buku(p):
        if p not in buku:
            buku[p] = book(p)
            if buku[p] is None:
                log(f"{p}: order book gagal diambil", "ERROR")
        return buku[p]

    def nilai_pos():
        tot = 0.0
        for p, ps in S["pos"].items():
            b = ambil_buku(p)
            tot += ps["qty"] * (b[0][0][0] if b else def_harga.get(p, ps["entry_px"]))
        return tot

    eq = S["cash"] + nilai_pos()
    if S["day"]["date"] != today:
        S["day"] = {"date": today, "awal": eq, "stop": False}
    if not S["day"]["stop"] and eq < S["day"]["awal"] * (1 - BATAS_RUGI_HARIAN):
        S["day"]["stop"] = True
        log(f"DAILY LOSS LIMIT tercapai ({eq / S['day']['awal'] - 1:.1%}). Tidak ada pembelian baru hari ini.", "WARN")
        tg(f"Daily loss limit tercapai: pembelian baru dihentikan sampai besok (UTC).")

    pesan = []
    # 4) eksekusi: jual dulu, lalu beli
    for p, alasan in list(S["pend_jual"].items()):
        ps = S["pos"].get(p)
        b = ambil_buku(p)
        if not ps or not b:
            continue
        bids, asks = b
        if (asks[0][0] - bids[0][0]) / bids[0][0] > MAX_SPREAD:
            log(f"{p}: spread tidak wajar, jual ditunda", "WARN")
            continue
        qj, kotor = fill_jual(bids, ps["qty"])
        if qj <= 0:
            continue
        fee = kotor * fs
        bersih = kotor - fee
        porsi = qj / ps["qty"]
        pnl = bersih - ps["modal"] * porsi
        S["cash"] += bersih
        catat_trade([stamp(), p, "JUAL", qj, kotor / qj, kotor, fee, alasan, pnl])
        pesan.append(f"JUAL {p} {kotor / qj:,.0f} ({alasan}) PnL {rp(pnl)}")
        if porsi >= 0.999999:
            del S["pos"][p]
            S["pend_jual"].pop(p)
        else:
            ps["qty"] -= qj
            ps["modal"] -= ps["modal"] * porsi
            log(f"{p}: hanya terjual sebagian (likuiditas order book kurang)", "WARN")
        simpan(S)

    kill = os.path.exists("KILL_SWITCH")
    if S["pend_beli"] and (kill or S["day"]["stop"]):
        log("Pembelian baru DITAHAN (" + ("kill switch" if kill else "daily loss limit") + ")", "WARN")
        if kill:
            tg("Kill switch aktif: pembelian baru ditahan.")
        S["pend_beli"] = []
    eq_buka = S["cash"] + nilai_pos()
    for p in list(S["pend_beli"]):
        b = ambil_buku(p)
        if p in S["pos"] or len(S["pos"]) >= maxpos or not b:
            S["pend_beli"].remove(p)
            continue
        bids, asks = b
        if (asks[0][0] - bids[0][0]) / bids[0][0] > MAX_SPREAD:
            log(f"{p}: spread tidak wajar, beli ditunda", "WARN")
            continue
        anggaran = min(S["cash"], eq_buka / maxpos)
        qty, biaya = fill_beli(asks, anggaran, fb)
        if biaya < cfg["min_order_rp"]:
            log(f"{p}: order di bawah minimum Rp{cfg['min_order_rp']} atau likuiditas kurang, dilewati", "WARN")
            S["pend_beli"].remove(p)
            continue
        fee = biaya * fb
        S["cash"] -= biaya + fee
        S["pos"][p] = {"qty": qty, "entry_px": biaya / qty, "entry_ts": NOW, "modal": biaya + fee}
        catat_trade([stamp(), p, "BELI", qty, biaya / qty, biaya, fee, "breakout", ""])
        pesan.append(f"BELI {p} {biaya / qty:,.0f} senilai {rp(biaya)}")
        S["pend_beli"].remove(p)
        simpan(S)

    # 5) ekuitas akhir, laporan
    eq = S["cash"] + nilai_pos()
    S["eq_harian"][today] = eq
    pd.Series(S["eq_harian"], name="ekuitas_rp").rename_axis("tanggal").to_csv(F_EQ)
    if pesan or bar_baru:
        s = pd.Series(S["eq_harian"])
        mdd = (s / s.cummax() - 1).min()
        isi = [f"Laporan {today}", f"Ekuitas {rp(eq)} ({eq / cfg['modal'] - 1:+.2%} dari modal)", f"MDD {mdd:.1%}",
               "Posisi: " + (", ".join(S["pos"]) or "tidak ada")] + pesan
        tg("\n".join(isi))
    simpan(S)
    return S, True


def main():
    global NOW
    NOW = time.time()
    cfg = json.load(open(CFG_FILE))
    if os.path.exists("KILL_SWITCH"):
        log("KILL_SWITCH ada: tidak ada pembelian baru", "WARN")
    try:
        S, ok = jalankan(cfg)
    except Exception as e:
        log(f"Error tak terduga: {type(e).__name__}: {str(e)[:150]}", "ERROR")
        tg(f"Bot error: {type(e).__name__}. Lihat log Actions.")
        S, ok = None, False
    baru = not os.path.exists(F_RUNS)
    with open(F_RUNS, "a", newline="") as f:
        w = csv.writer(f)
        if baru:
            w.writerow(["waktu_utc", "status", "jumlah_error", "ekuitas_rp"])
        eq = list(S["eq_harian"].values())[-1] if S and S["eq_harian"] else ""
        w.writerow([stamp(), "OK" if ok else "GAGAL", len(ERRORS), eq])
    if ERRORS:
        tg(f"Bot: {len(ERRORS)} error API pada run ini (lihat data_bot/log.txt).")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
