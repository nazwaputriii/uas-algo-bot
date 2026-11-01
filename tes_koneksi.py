"""
Tes koneksi (cicilan 3a): bisakah server GitHub mengambil harga publik Indodax
dan mengirim pesan ke Telegram? Tidak ada order. Token dari GitHub Secrets, bukan dari kode.
"""
import os, requests

token = os.environ["TELEGRAM_TOKEN"]
chat = os.environ["TELEGRAM_CHAT_ID"]


def kirim(teks):
    r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      data={"chat_id": chat, "text": teks}, timeout=30)
    print("telegram:", r.status_code)


def bid_ask(js):
    """Coba beberapa bentuk data yang mungkin dipakai Indodax."""
    if "buy" in js and "sell" in js and isinstance(js["buy"], list):      # order book: buy=bid, sell=ask
        return js["buy"][0][0], js["sell"][0][0]
    if "bids" in js and "asks" in js:
        return js["bids"][0][0], js["asks"][0][0]
    if "ticker" in js:                                                     # ticker: buy=bid, sell=ask
        return js["ticker"]["buy"], js["ticker"]["sell"]
    return None


URLS = ["https://indodax.com/api/btc_idr/depth",
        "https://indodax.com/api/depth/btc_idr",
        "https://indodax.com/api/btc_idr/ticker"]
hasil = None
for u in URLS:
    try:
        r = requests.get(u, timeout=30)
        print(u, "status", r.status_code, "|", r.text[:150].replace("\n", " "))
        js = r.json()
        ba = bid_ask(js)
        if ba:
            hasil = (u, ba)
            break
    except Exception as e:
        print(u, "GAGAL:", type(e).__name__, str(e)[:100])

if hasil:
    kirim(f"Tes GitHub OK\nBTC/IDR bid {hasil[1][0]} | ask {hasil[1][1]}\nsumber: {hasil[0]}")
else:
    kirim("Tes GitHub: server tersambung ke Indodax tapi bentuk datanya belum cocok. Lihat log Actions.")
    raise SystemExit(1)
