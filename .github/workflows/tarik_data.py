"""
Tarik data candle 4 jam Indodax (3 tahun lebih) di Colab/laptop. Satu request hanya memberi ~650 bar terakhir sebelum 'to',
jadi data ditarik MUNDUR bertahap. Berurutan (tidak paralel), jeda 0,4 detik (< 3 request/detik).
Hasil: folder data_4h/<PAIR>.csv  (kolom: time,open,high,low,close,volume)
"""
import os, sys, time, csv, datetime as dt
import requests
sys.path.insert(0, "api")
from _config import CFG

MULAI = "2023-01-01"
URL = "https://indodax.com/tradingview/history_v2"
os.makedirs("data_4h", exist_ok=True)
awal = int(dt.datetime.fromisoformat(MULAI).replace(tzinfo=dt.timezone.utc).timestamp())

for pair in CFG["universe"]:
    to, semua, req = int(time.time()), {}, 0
    while True:
        r = requests.get(URL, params={"symbol": pair, "tf": CFG["timeframe"], "from": awal, "to": to}, timeout=30)
        r.raise_for_status()
        js = r.json()
        req += 1
        if not isinstance(js, list) or not js:
            break
        for x in js:
            x = {k.lower(): v for k, v in x.items()}
            semua[int(float(x["time"]))] = x
        paling_awal = min(int(float({k.lower(): v for k, v in x.items()}["time"])) for x in js)
        if paling_awal <= awal or paling_awal >= to:
            break
        to = paling_awal - 1
        time.sleep(0.4)
    ts = sorted(t for t in semua if t >= awal)
    with open(f"data_4h/{pair}.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["time", "open", "high", "low", "close", "volume"])
        for t in ts:
            x = semua[t]
            w.writerow([t, x["open"], x["high"], x["low"], x["close"], x["volume"]])
    print(pair, len(ts), "bar,", req, "request, dari", dt.datetime.fromtimestamp(ts[0], dt.timezone.utc).date() if ts else "-")
    time.sleep(0.4)
