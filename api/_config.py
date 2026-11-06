"""KONFIGURASI STRATEGI (dibekukan saat freeze). Jangan diubah setelah commit freeze."""
CFG = {
    "versi": "uas-v1",
    "universe": ["BTCIDR", "ETHIDR", "XRPIDR", "DOGEIDR", "ADAIDR"],   # median nilai transaksi harian >= Rp1 miliar pada 90 hari sebelum 1 Jan 2023 DAN 90 hari terakhir
    "timeframe": "240",            # 4 jam (parameter tf di history_v2)
    "tf_detik": 14400,
    "n_masuk": 120,                # 20 hari x 6 bar: beli bila close > close tertinggi 120 bar sebelumnya (Turtle System 1: 20 hari)
    "n_keluar": 60,                # 10 hari x 6 bar: keluar bila close < low terendah 60 bar sebelumnya (Turtle System 1: 10 hari)
    "atr_n": 84,                   # ATR 14 hari x 6 bar
    "atr_k": 3.0,                  # trailing stop = puncak close - 3 x ATR (Chandelier Exit standar)
    "roc_n": 120,                  # urutan prioritas bila sinyal beli bersamaan: momentum 120 bar
    "modal": 100_000_000,
    "maks_posisi": 5,              # ukuran per posisi = ekuitas / 5 (maks 20% ekuitas)
    "fee_beli": 0.0020555,         # taker IDR PRO (aplikasi Indodax, 1 Nov 2026); dipakai yang lebih mahal vs /api/pairs
    "fee_jual": 0.0041555,
    "min_order_rp": 25000,
    "batas_rugi_harian": 0.05,     # hari WIB (UTC+7), berganti 00.00 WIB
    "max_spread": 0.02,
    "stale_faktor": 2,
    "wib_jam": 7,
}
