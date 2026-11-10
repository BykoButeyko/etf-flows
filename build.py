"""Turn raw files in data/ into the daily and weekly frames defined in PLAN.md."""
import io
import json
from datetime import datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from fetch import quarterly_expiries

DATA = Path(__file__).parent / "data"
NY = ZoneInfo("America/New_York")
TEST_START = pd.Timestamp("2025-01-01")


def _load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def parse_cell(s):
    """Farside cell -> float US$m. '(95.1)' is negative, '-' is missing."""
    if pd.isna(s):
        return np.nan
    s = str(s).strip().replace(",", "")
    if s in ("-", ""):
        return np.nan
    if s.startswith("(") and s.endswith(")"):
        return -float(s[1:-1])
    return float(s)


def parse_farside(html):
    t = max(pd.read_html(io.StringIO(html)), key=len)
    t["date"] = pd.to_datetime(t["Date"], format="%d %b %Y", errors="coerce")
    t = t[t["date"].notna()].set_index("date").drop(columns="Date")
    funds = t.drop(columns="Total").map(parse_cell)
    # holidays and the not-yet-reported current day: every fund is '-'
    keep = funds.notna().any(axis=1)
    total = funds[keep].sum(axis=1, min_count=1)
    return total.rename("flow_usdm")


def us_close_prices(spot_1h):
    """BTC price at 16:00 New York time for every calendar day, from Binance hourly."""
    h = pd.Series({pd.Timestamp(ms, unit="ms"): px for ms, px in spot_1h})
    out = {}
    for d in pd.date_range(h.index.min().normalize() + pd.Timedelta(days=1), h.index.max().normalize()):
        close_utc = datetime.combine(d.date(), time(16), NY).astimezone(ZoneInfo("UTC")).replace(tzinfo=None)
        candle = pd.Timestamp(close_utc) - pd.Timedelta(hours=1)  # candle that closes at 16:00 ET
        if candle in h.index:
            out[d] = h[candle]
    return pd.Series(out, name="px")


def basis_90d(spot_1d, cq_1d, nq_1d):
    """Annualised premium of Binance quarterlies over spot, interpolated to 90 days.

    Daily candles close at 24:00 UTC. The near contract for a day is the first
    expiry (Friday 08:00 UTC) after that close.
    """
    s = lambda rows: pd.Series({pd.Timestamp(ms, unit="ms"): px for ms, px in rows})
    df = pd.DataFrame({"spot": s(spot_1d), "cq": s(cq_1d), "nq": s(nq_1d)}).dropna()
    exps = [pd.Timestamp(e) + pd.Timedelta(hours=8) for e in quarterly_expiries()]
    rows = []
    for d, r in df.iterrows():
        close = d + pd.Timedelta(days=1)
        i = next(k for k, e in enumerate(exps) if e > close)
        tc = (exps[i] - close).total_seconds() / 86400
        tn = (exps[i + 1] - close).total_seconds() / 86400
        bc = (r.cq / r.spot - 1) * 365 / tc
        bn = (r.nq / r.spot - 1) * 365 / tn
        if tc < 7:
            b = bn
        else:
            b = bc + (bn - bc) * (90 - tc) / (tn - tc)
        rows.append((d, b, bc, bn, tc))
    return pd.DataFrame(rows, columns=["date", "basis", "basis_cq", "basis_nq", "tau_cq"]).set_index("date")


def lev_net_short(rows):
    """Leveraged funds net short in BTC: standard x5 + micro x0.1, by report date."""
    d = pd.DataFrame(rows)
    d["date"] = pd.to_datetime(d["report_date_as_yyyy_mm_dd"])
    mult = d["cftc_contract_market_code"].map({"133741": 5.0, "133742": 0.1})
    net = (d["lev_money_positions_short"].astype(float) - d["lev_money_positions_long"].astype(float)) * mult
    am = (d["asset_mgr_positions_long"].astype(float) - d["asset_mgr_positions_short"].astype(float)) * mult
    out = pd.DataFrame({"date": d["date"], "lev_net_short": net, "am_net_long": am,
                        "code": d["cftc_contract_market_code"]})
    piv = out.pivot_table(index="date", columns="code", values=["lev_net_short", "am_net_long"], aggfunc="sum")
    # keep only weeks where both contracts reported
    piv = piv.dropna()
    return pd.DataFrame({"lev_net_short": piv["lev_net_short"].sum(axis=1),
                         "am_net_long": piv["am_net_long"].sum(axis=1)})


def daily():
    flow = parse_farside((DATA / "farside.html").read_text(encoding="utf-8"))
    b = _load("binance.json")
    px = us_close_prices(b["spot_1h"])
    bas = basis_90d(b["spot_1d"], b["cq_1d"], b["nq_1d"])
    d = pd.DataFrame({"flow_usdm": flow}).join(px, how="left")
    d["flow_btc"] = d.flow_usdm * 1e6 / d.px
    d["ret"] = np.log(d.px).diff()  # between consecutive trading-day US closes
    d = d.join(bas["basis"], how="left")
    return d


def weekly(d=None):
    d = daily() if d is None else d
    cot = lev_net_short(_load("cftc.json"))
    cot = cot[cot.index >= "2024-01-01"]
    rows = []
    for t in cot.index:
        w = d[(d.index > t - pd.Timedelta(days=7)) & (d.index <= t)]
        rows.append((t, w.flow_btc.sum(), len(w)))
    w = pd.DataFrame(rows, columns=["date", "flow_btc", "n_days"]).set_index("date").join(cot)
    full = lev_net_short(_load("cftc.json"))
    w["d_short"] = full["lev_net_short"].diff().reindex(w.index)
    w["d_am_long"] = full["am_net_long"].diff().reindex(w.index)
    # a gap longer than 7 days would make the change span two weeks
    gap = full.index.to_series().diff().dt.days.reindex(w.index)
    w["gap_days"] = gap
    return w[w.n_days > 0]
