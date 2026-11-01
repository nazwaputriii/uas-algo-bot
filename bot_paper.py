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
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
