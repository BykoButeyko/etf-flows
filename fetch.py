"""Download raw data into data/. Run once per analysis run.

python fetch.py
"""
import json
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

DATA = Path(__file__).parent / "data"
UA = {"User-Agent": "Mozilla/5.0 (research script)"}
START = datetime(2023, 12, 1, tzinfo=timezone.utc)
START_MS = int(START.timestamp() * 1000)


def get(url, **params):
    for attempt in range(4):
        r = requests.get(url, params=params, headers=UA, timeout=60)
        if r.status_code == 200:
            return r
        time.sleep(2 * (attempt + 1))
    r.raise_for_status()


def save(name, obj):
    DATA.mkdir(exist_ok=True)
    (DATA / name).write_text(json.dumps(obj), encoding="utf-8")


def farside():
    r = get("https://farside.co.uk/bitcoin-etf-flow-all-data/")
    DATA.mkdir(exist_ok=True)
    (DATA / "farside.html").write_text(r.text, encoding="utf-8")


def cftc():
    rows = []
    for code in ("133741", "133742"):
        rows += get(
            "https://publicreporting.cftc.gov/resource/gpe5-46if.json",
            cftc_contract_market_code=code,
            **{"$where": "report_date_as_yyyy_mm_dd>='2023-11-01'",
               "$order": "report_date_as_yyyy_mm_dd", "$limit": 5000},
        ).json()
    save("cftc.json", rows)


def binance_klines(base, path, interval, **params):
    out, t = [], START_MS
    step = {"1d": 86_400_000, "1h": 3_600_000}[interval]
    while True:
        x = get(base + path, interval=interval, startTime=t, limit=1000, **params).json()
        if not x:
            break
        out += x
        t = x[-1][0] + step
        if len(x) < 1000:
            break
    return [[k[0], float(k[4])] for k in out]  # open time ms, close


def binance():
    spot = "https://api.binance.com"
    fut = "https://fapi.binance.com"
    save("binance.json", {
        "spot_1d": binance_klines(spot, "/api/v3/klines", "1d", symbol="BTCUSDT"),
        "spot_1h": binance_klines(spot, "/api/v3/klines", "1h", symbol="BTCUSDT"),
        "cq_1d": binance_klines(fut, "/fapi/v1/continuousKlines", "1d",
                                pair="BTCUSDT", contractType="CURRENT_QUARTER"),
        "nq_1d": binance_klines(fut, "/fapi/v1/continuousKlines", "1d",
                                pair="BTCUSDT", contractType="NEXT_QUARTER"),
    })


def quarterly_expiries(first=date(2024, 1, 1), last=None):
    """Last Friday of Mar/Jun/Sep/Dec (Binance and Deribit quarterly expiry)."""
    last = last or date.today() + timedelta(days=200)
    out = []
    for y in range(first.year, last.year + 1):
        for m in (3, 6, 9, 12):
            d = date(y + (m == 12), (m % 12) + 1, 1) - timedelta(days=1)
            while d.weekday() != 4:
                d -= timedelta(days=1)
            if first <= d <= last:
                out.append(d)
    return out


def deribit():
    out = {}
    end = int(time.time() * 1000)
    for exp in quarterly_expiries():
        name = "BTC-" + exp.strftime("%d%b%y").upper().lstrip("0")
        x = get("https://www.deribit.com/api/v2/public/get_tradingview_chart_data",
                instrument_name=name, resolution="1D",
                start_timestamp=START_MS, end_timestamp=end).json()["result"]
        if x.get("status") == "ok":
            out[exp.isoformat()] = list(zip(x["ticks"], x["close"]))
    save("deribit.json", out)


def yahoo():
    r = get("https://query1.finance.yahoo.com/v8/finance/chart/BTC=F",
            period1=int(START.timestamp()), period2=int(time.time()), interval="1d")
    res = r.json()["chart"]["result"][0]
    save("yahoo.json", list(zip(res["timestamp"], res["indicators"]["quote"][0]["close"])))


if __name__ == "__main__":
    for f in (farside, cftc, binance, deribit, yahoo):
        f()
        print("ok", f.__name__)
