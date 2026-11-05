import os


def sah(headers):
    s = os.environ.get("CRON_SECRET")
    return bool(s) and headers.get("Authorization") == "Bearer " + s
