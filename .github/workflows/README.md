# Bot Dry Run Indodax - UAS Algoritma Trading
Nazwa Jaliyanti Putri - NIM 25120200010

Bot membaca harga dan order book publik Indodax, menghitung sinyal, dan **mensimulasikan** order (dry run) di harga bid/ask.
Tidak ada uang sungguhan dan tidak memakai API key. Long-only, tanpa short, margin, atau leverage.

## FREEZE (dicatat sebelum forward test)
- **Waktu freeze/mulai:** ISI_SAAT_COMMIT (WIB) - waktu commit ini adalah bukti freeze
- **Exchange/pasar:** Indodax, pasangan IDR, order taker (beli di ask, jual di bid)
- **Timeframe:** 4 jam (candle tutup 00,04,08,12,16,20 UTC)
- **Universe (5):** BTC/IDR, ETH/IDR, XRP/IDR, DOGE/IDR, ADA/IDR
- **Kriteria universe:** median nilai transaksi harian >= Rp1 miliar pada 90 hari sebelum 1 Jan 2023 (awal periode backtest) **dan** pada 90 hari terakhir; stablecoin (USDT) dikeluarkan. Diukur dari data harian Indodax, bukan hanya kondisi hari ini, untuk mengurangi survivorship bias. Koin yang gagal kriteria awal periode (mis. SOL) tidak dipakai.
- **Aturan masuk:** close bar tertutup > close tertinggi 120 bar sebelumnya (20 hari). Bila sinyal beli bersamaan melebihi slot, urut berdasarkan momentum 120 bar.
- **Aturan keluar:** close < low terendah 60 bar sebelumnya (10 hari), **atau** close < (close tertinggi sejak entry - 3 x ATR84).
- **Sizing:** ekuitas / 5 per posisi; maksimum 5 posisi terbuka.
- **Parameter:** n_masuk=120, n_keluar=60, ATR 84 bar, pengali 3,0. Dipilih dari konvensi standar (Turtle System 1: 20/10 hari; Chandelier Exit 3x ATR) **sebelum melihat hasil backtest 4 jam**. Tidak dioptimasi.
- **Modal virtual:** Rp100.000.000
- **Fee (taker all-in):** beli 0,20555%, jual 0,41555% (aplikasi Indodax, IDR Market PRO, diakses 1 Nov 2026). Bot juga membaca `/api/pairs` dan memakai yang **lebih mahal**; kedua angka dicatat di setiap order.
- **Minimum order:** Rp25.000. **Batas spread bid-ask:** 2%.
- **Risk:** daily loss limit 5% (hari WIB, berganti 00.00 WIB), kill switch lewat storage tanpa deploy ulang, retry terbatas, idempotensi per candle.

### Perubahan dari strategi UTS (saham harian)
Kode UTS: Donchian Breakout 100 hari, keluar 20 hari, trailing 6,5 x ATR14 (saham BEI, harian). Untuk UAS: timeframe 4 jam, parameter standar di atas, universe kripto IDR, fee dan fill di order book Indodax. Semua perubahan dibuat **sebelum** commit freeze.

## Struktur
- `api/_config.py` konfigurasi beku; `api/_strategi.py` fungsi sinyal/fill **dipakai sama oleh bot dan backtest**
- `api/tick.py` endpoint bot (dilindungi `CRON_SECRET`); `api/data.py` data dashboard; `api/export.py` log mentah; `api/kill.py` kill switch
- `.github/workflows/tick.yml` penjadwal (GitHub Actions memanggil `/api/tick` tiap jam menit ke-7 UTC)
- `snapshot_orderbook.py` + workflow `snapshot.yml`: snapshot order book tiap jam untuk estimasi spread/slippage
- `tarik_data.py` (data 4 jam 3 tahun lebih, ditarik mundur), `backtest.py`
- `index.html` dashboard; storage: Upstash Redis (Vercel Marketplace)

## Menjalankan
1. Vercel: import repo, hubungkan storage Upstash Redis, isi env `CRON_SECRET`.
2. GitHub Secrets: `VERCEL_APP_URL`, `CRON_SECRET`.
3. Backtest: `python tarik_data.py` lalu `python backtest.py`.
4. Rahasia hanya di environment variable / GitHub Secrets. `.env` tidak di-commit (lihat `.env.example`).

## Log perubahan setelah freeze
(kosong; semua perbaikan bug dicatat di sini dengan tanggal dan alasan)
