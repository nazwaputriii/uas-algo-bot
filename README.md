# Bot Dry Run Indodax - UAS Algoritma Trading
Nazwa Jaliyanti Putri - NIM 25120200010

Bot membaca harga dan order book publik Indodax, menghitung sinyal, dan **mensimulasikan** order (dry run) di harga bid/ask.
Tidak ada uang sungguhan dan tidak memakai API key. Long-only, tanpa short, margin, atau leverage.

## FREEZE (dicatat sebelum forward test)
- **Waktu freeze/mulai:** 08_November_2026 10.44 (WIB) - waktu commit ini adalah bukti freeze
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
- hitung_ulang.py dan dashboard_template.html: menghitung ulang semua angka dari log mentah dan membuat dashboard_offline.html

## Menjalankan
1. Vercel: import repo, hubungkan storage Upstash Redis, isi env `CRON_SECRET`.
2. GitHub Secrets: `VERCEL_APP_URL`, `CRON_SECRET`.
3. Backtest: `python tarik_data.py` lalu `python backtest.py`.
4. Rahasia hanya di environment variable / GitHub Secrets. `.env` tidak di-commit (lihat `.env.example`).
5. Hitung ulang dan dashboard offline: python tarik_data.py lalu python hitung_ulang.py

## Log perubahan setelah freeze
Tidak ada perubahan aturan, parameter, maupun universe sejak freeze. Hash konfigurasi tetap 39f0625b6391 pada seluruh panggilan di log.

- 9 Nov 2026: merapikan repositori tanpa menyentuh kode bot. Menghapus 9 salinan file di folder .github/workflows (backtest.py, tarik_data.py, snapshot_orderbook.py, index.html, requirements.txt, vercel.json, README.md, .env.example, .gitignore). Salinan itu tidak dipakai workflow mana pun, dan README di dalamnya adalah versi lama. Hanya tick.yml, kontrol.yml, dan snapshot.yml yang dipertahankan.
- 9 Nov 2026: menghapus sisa data uji bot lama (1 Nov 2026) di folder data_bot: state.json, log.txt, runs.csv, equity.csv. Hash konfigurasi bot lama berbeda dan bukan bagian forward test. Data forward test yang sah adalah data_bot/export_log_mentah.json dan data_bot/snapshots.csv beserta snapshots_mentah.jsonl.
- 9 Nov 2026: menambahkan hitung_ulang.py dan dashboard_template.html. Keduanya hanya membaca log dan menghitung ulang angka, tidak mengubah bot.
- Penjadwal: selain GitHub Actions (tick.yml, tiap jam menit ke-7), bot dipanggil cron-job.org tiap 30 menit sejak 8 Nov 2026. Idempotensi per candle membuat panggilan ganda tidak membeli dua kali. Angka "panggilan terjadwal" di dashboard dihitung per jam, sehingga panggilan terlaksana bisa lebih besar. Uptime dihitung dari candle yang terproses tepat waktu, bukan dari jumlah panggilan.
- 9 Nov 2026: baris waktu freeze sempat diubah ke 10.55 lalu dikembalikan ke 10.44 sesuai waktu commit freeze. Pukul 10.55 WIB adalah waktu forward test mulai (event mulai di log).
- Tes kill switch terencana pada 9 Nov 2026, diaktifkan lalu dimatikan lagi. Setelah itu workflow kontrol dinonaktifkan.
- 9 Nov 2026: menambah dua baris dokumentasi di Struktur dan Menjalankan, tanpa mengubah kode
- 9 Nov 2026: memperbaiki catatan penyebab kegagalan uji koneksi (HTTP 401 dan 308), tanpa mengubah kode.
- 10 Nov 2026: memperbarui tampilan dashboard_template.html (hanya tampilan, perhitungan tidak berubah), tanpa mengubah kode bot.
- 11 Nov 2026: memperbarui hitung_ulang.py agar spread backtest memakai snapshot sampai freeze (8 Nov 2026 10.44 WIB) sehingga hasil backtest tidak bergeser; tidak mengubah kode bot.
- 11 Nov 2026: menambah BUKTI_FREEZE.txt berisi hash dan waktu commit freeze, tanpa mengubah kode bot.
- 12 Nov 2026: menambah bagian Sumber fee dan minimum order, Bukti risk management, dan Catatan data backtest di README (hanya dokumentasi), tanpa mengubah kode bot.
- 14 Nov 2026: penjadwal dihentikan setelah forward test selesai. Job cron-job.org dinonaktifkan (eksekusi terakhir 13.30 WIB), satu tick manual terakhir (#57) dijalankan sekitar 13.46 WIB, lalu workflow tick dan snapshot-orderbook dinonaktifkan.
- 14 Nov 2026: CRON_SECRET diganti dengan nilai baru sebagai rotasi keamanan sebelum repositori dipublikasikan. Tidak berdampak pada forward test.
- 14 Nov 2026: index.html (dashboard Vercel) diganti dengan versi baru yang hanya mengubah tampilan, data tetap dari /api/data. Tidak ada perubahan pada kode bot, strategi, parameter, maupun universe.
  
Catatan: 1-8 Nov 2026 adalah uji coba (bot lama harian di GitHub Actions dan uji koneksi), bukan bagian forward test. Pada uji koneksi sebelum forward test, panggilan ke Vercel gagal HTTP 401 karena CRON_SECRET di GitHub tidak sama dengan di Vercel, lalu HTTP 308 karena alamat URL; keduanya baru teratasi pada 8 Nov. Jadwal GitHub Actions juga sering terlewat, sehingga ditambahkan penjadwal cron-job.org.
8 Nov 2026 10.41 WIB: kill switch terpicu tidak sengaja saat uji (workflow kontrol), tanpa order. Data uji dihapus dengan reset. Forward test tercatat mulai dari event mulai setelah reset.

## Sumber fee dan minimum order
Fee taker all-in (sudah termasuk pajak dan CFX fee), tarif berlaku sejak 1 Oktober 2026, pasar IDR mode PRO:
- Halaman resmi Rincian Biaya Transaksi di INDODAX, https://help.indodax.com/hc/id/articles/4416646599705-Rincian-Biaya-Transaksi-di-INDODAX, diakses 12 Nov 2026: beli 0,20555% (service fee 0,20%, pajak 0%, CFX fee 0,00555%) dan jual 0,41555% (service fee 0,20%, pajak 0,21%, CFX fee 0,00555%). Angka ini dipakai bot sebagai fee_beli dan fee_jual di api/_config.py.
- API publik https://indodax.com/api/pairs, diakses 12 Nov 2026: trade_fee_percent_taker = 0,2% untuk BTC/IDR, ETH/IDR, XRP/IDR, DOGE/IDR, dan ADA/IDR. Angka ini hanya service fee, belum termasuk pajak dan CFX fee, sehingga lebih murah daripada angka halaman resmi.
- Aplikasi Indodax, IDR Market PRO, diakses 1 Nov 2026: angka sama dengan halaman resmi.

Bot memakai tarif yang lebih mahal antara fee di api/_config.py dan trade_fee_percent_taker dari /api/pairs yang dibaca setiap panggilan, dan kedua angka dicatat di setiap order. Karena angka halaman resmi lebih mahal, itulah yang berlaku.

Minimum order: trade_min_base_currency di /api/pairs = Rp10.000 (diakses 12 Nov 2026). Halaman resmi yang sama menyebut order langsung di mode Pro minimal Rp25.000, dan order Pro Rp10.000 sampai Rp24.999 diproses lewat INDODAX Lite. Bot memakai yang lebih ketat, yaitu Rp25.000 (min_order_rp di api/_config.py).

## Bukti risk management di kode dan log
Semua ada di api/_bot.py (nomor baris sekitar):
- Batas jumlah posisi dan ukuran per posisi: maks_posisi 5 dan sizing ekuitas dibagi 5 (api/_config.py).
- Daily loss limit 5% pada hari WIB: baris 209. Bot berhenti membuka posisi baru sampai hari berikutnya. Belum terpicu karena belum ada posisi.
- Kill switch tanpa deploy ulang: baris 122 dan 246-247. Terbukti di log: dua event kill pada 9 Nov 2026 (aktif 04.01 UTC, nonaktif 04.02 UTC).
- Retry terbatas dan penanganan error API: baris 26-32, setiap kegagalan dicatat sebagai event error. Belum terpicu karena error_api 0.
- Idempotency per candle: baris 154, dan kunci panggilan di baris 88. Terbukti di log: dua penjadwal memanggil bot pada candle yang sama, hanya satu panggilan yang memproses (bar_diproses 5, panggilan lain 0).
- Validasi data (candle usang lebih dari 2 kali timeframe, spread bid-ask lebih dari 2%, minimum order): baris 150, 218, dan 262.

## Catatan data backtest
tarik_data.py mengambil candle yang sedang berjalan sebagai elemen terakhir. hitung_ulang.py membuang candle yang belum tertutup sebelum menghitung backtest, sesuai aturan soal. Spread dan slippage backtest dibekukan pada snapshot sampai freeze (8 Nov 2026 10.44 WIB).
