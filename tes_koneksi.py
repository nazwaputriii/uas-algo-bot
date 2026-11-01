"""
Tes koneksi (cicilan 3a): bisakah server GitHub mengambil harga publik Indodax
dan mengirim pesan ke Telegram? Tidak ada order. Token dibaca dari GitHub Secrets, tidak ada di kode.
"""
import os, requests

token = os.environ["TELEGRAM_TOKEN"]
chat = os.environ["TELEGRAM_CHAT_ID"]


def kirim(teks):
    r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage",
                      data={"chat_id": chat, "text": teks}, timeout=30)
    print("telegram:", r.status_code)


try:
    r = requests.get("https://indodax.com/api/depth/btc_idr", timeout=30)
    print("indodax status:", r.status_code)
    r.raise_for_status()
    d = r.json()
    bid = d["buy"][0][0]    # harga bid terbaik (orang mau beli)
    ask = d["sell"][0][0]   # harga ask terbaik (orang mau jual)
    kirim(f"Tes GitHub OK\nBTC/IDR bid {bid} | ask {ask}")
except Exception as e:
    print("GAGAL:", e)
    kirim(f"Tes GitHub: GAGAL ambil data Indodax\n{type(e).__name__}: {str(e)[:200]}")
    raise
