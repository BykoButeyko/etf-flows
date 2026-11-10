"""H1-H3 tests as fixed in PLAN.md. Writes results.txt.

python fetch.py && python analysis.py
"""
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm

import build
from thresholds import thresholds

ALPHA = 0.05
BONF = ALPHA / 3
OUT = []


def say(*a):
    s = " ".join(str(x) for x in a)
    print(s)
    OUT.append(s)


def ols(y, X, lags):
    X = sm.add_constant(X)
    ok = pd.concat([y, X], axis=1).dropna()
    return sm.OLS(ok.iloc[:, 0], ok.iloc[:, 1:]).fit(cov_type="HAC", cov_kwds={"maxlags": lags})


def one_sided(fit, name, sign=+1):
    p2 = fit.pvalues[name]
    return p2 / 2 if np.sign(fit.params[name]) == sign else 1 - p2 / 2


def block_boot_diff(flag, y, block, n=10_000, seed=0):
    """Moving-block bootstrap of mean(y | flag) - mean(y | not flag). Returns diff, CI, P(diff<=0)."""
    df = pd.DataFrame({"f": flag, "y": y}).dropna()
    f, v = df.f.to_numpy(bool), df.y.to_numpy(float)
    m = len(v)
    rng = np.random.default_rng(seed)
    starts_n = m - block + 1
    k = int(np.ceil(m / block))
    diffs = []
    for _ in range(n):
        idx = (rng.integers(0, starts_n, k)[:, None] + np.arange(block)).ravel()[:m]
        ff, vv = f[idx], v[idx]
        if ff.any() and (~ff).any():
            diffs.append(vv[ff].mean() - vv[~ff].mean())
    diffs = np.array(diffs)
    obs = v[f].mean() - v[~f].mean() if f.any() else np.nan
    return obs, np.percentile(diffs, [2.5, 97.5]), float((diffs <= 0).mean()), int(f.sum()), m


def verdict(p):
    return ("SUPPORTED" if p < ALPHA else "NOT SUPPORTED") + (" (also at Bonferroni 5%/3)" if p < BONF else "")


def h1(w, thr):
    say("\n=== H1: inflow weeks come with new leveraged-fund CME shorts ===")
    for label, part in (("calibration 2024", w[w.index < build.TEST_START]), ("TEST 2025-", w[w.index >= build.TEST_START])):
        f = ols(part.d_short, part[["flow_btc"]], 4)
        b, (lo, hi) = f.params.flow_btc, f.conf_int().loc["flow_btc"]
        say(f"{label}: n={int(f.nobs)} weeks, hedge ratio {b:.3f} (95% CI {lo:.3f} to {hi:.3f}), "
            f"one-sided p={one_sided(f, 'flow_btc'):.4f}, R2={f.rsquared:.3f}, "
            f"corr={part.flow_btc.corr(part.d_short):.3f}")
    t = w[w.index >= build.TEST_START]
    f = ols(t.d_short, t[["flow_btc"]], 4)
    p = one_sided(f, "flow_btc")
    say("H1 main test:", verdict(p))
    pred = 0.2 <= f.params.flow_btc <= 0.5
    say(f"Point prediction (hedge ratio 0.2-0.5 in test): {'HIT' if pred else 'MISSED'} ({f.params.flow_btc:.3f})")
    obs, ci, pb, nf, m = block_boot_diff(t.flow_btc > thr["h1_large_week_flow_btc"], t.d_short, 4)
    say(f"Large-week check (flow > {thr['h1_large_week_flow_btc']:.0f} BTC): {nf} of {m} test weeks; "
        f"mean d_short large minus other = {obs:.0f} BTC (95% CI {ci[0]:.0f} to {ci[1]:.0f}), p={pb:.4f}")
    # descriptive, not a test: asset managers
    fa = ols(t.d_am_long, t[["flow_btc"]], 4)
    say(f"(descriptive) asset-manager net long change per BTC of ETF flow, test: {fa.params.flow_btc:.3f}")
    return p


def h2(d, thr):
    say("\n=== H2: a narrowing basis is followed by outflows ===")
    d = d.copy()
    d["d_basis_5"] = d.basis - d.basis.shift(5)
    d["ret_5"] = np.log(d.px) - np.log(d.px.shift(5))
    d["fwd_flow_5"] = sum(d.flow_btc.shift(-k) for k in range(1, 6))
    t = d[d.index >= build.TEST_START].dropna(subset=["d_basis_5", "ret_5", "fwd_flow_5"])
    f = ols(t.fwd_flow_5, t[["d_basis_5", "ret_5"]], 5)
    p = one_sided(f, "d_basis_5")
    say(f"TEST n={int(f.nobs)} days. next-5-day flow (BTC) on 5-day basis change (per 1.00 = 100 pp) "
        f"and 5-day return:")
    say(f"  basis coef {f.params.d_basis_5:.0f} (95% CI {f.conf_int().loc['d_basis_5'][0]:.0f} to "
        f"{f.conf_int().loc['d_basis_5'][1]:.0f}), one-sided p={p:.4f}; "
        f"per -1 pp of basis: {f.params.d_basis_5 * -0.01:.0f} BTC over 5 days")
    say(f"  return coef {f.params.ret_5:.0f}, two-sided p={f.pvalues.ret_5:.4f}")
    f0 = ols(t.fwd_flow_5, t[["d_basis_5"]], 5)
    say(f"  (without return control: basis coef {f0.params.d_basis_5:.0f}, one-sided p={one_sided(f0, 'd_basis_5'):.4f})")
    say("  corr(5d basis change, 5d return) in test:", round(t.d_basis_5.corr(t.ret_5), 3))
    say("H2 main test:", verdict(p))
    obs, ci, pb, nf, m = block_boot_diff(t.d_basis_5 < thr["h2_basis_drop_5d"], t.fwd_flow_5, 5)
    # predicted: events have LOWER flow, so the wrong sign is diff >= 0
    say(f"Event check (5d basis change < {thr['h2_basis_drop_5d'] * 100:.2f} pp): {nf} of {m} test days; "
        f"mean next-5d flow events minus other = {obs:.0f} BTC (95% CI {ci[0]:.0f} to {ci[1]:.0f}), "
        f"p={1 - pb:.4f}")
    return p


def h3(d):
    say("\n=== H3: flows follow price more than they lead it ===")
    d = d.copy()
    for c in ("flow_btc", "ret"):
        d[c + "_z"] = d[c] / d[c].rolling(60).std().shift(1)
    L = range(1, 6)
    for c in ("flow_btc_z", "ret_z"):
        for k in L:
            d[f"{c}_l{k}"] = d[c].shift(k)
    t = d[d.index >= build.TEST_START]
    rl = [f"ret_z_l{k}" for k in L]
    fl = [f"flow_btc_z_l{k}" for k in L]
    fa = ols(t.flow_btc_z, t[rl + fl], 5)
    fb = ols(t.ret_z, t[fl + rl], 5)
    wa = fa.wald_test(", ".join(f"{c} = 0" for c in rl), use_f=False, scalar=True)
    wb = fb.wald_test(", ".join(f"{c} = 0" for c in fl), use_f=False, scalar=True)
    pa, pb = float(wa.pvalue), float(wb.pvalue)
    sa, sb = fa.params[rl].sum(), fb.params[fl].sum()
    say(f"TEST n={int(fa.nobs)} days")
    say(f"  flow(t) on past returns: Wald p={pa:.4g}, sum of return-lag coefs {sa:.3f}, "
        f"lag-1 {fa.params.ret_z_l1:.3f} (p={fa.pvalues.ret_z_l1:.4g})")
    say(f"  return(t) on past flows: Wald p={pb:.4g}, sum of flow-lag coefs {sb:.3f}, "
        f"lag-1 {fb.params.flow_btc_z_l1:.3f} (p={fb.pvalues.flow_btc_z_l1:.4g})")
    if pa < ALPHA and pb >= ALPHA:
        v = "SUPPORTED" + (" (also at Bonferroni 5%/3)" if pa < BONF else "")
    elif pa < ALPHA and pb < ALPHA:
        v = f"BOTH DIRECTIONS (|sum| flow eq {abs(sa):.3f} vs return eq {abs(sb):.3f}), not support"
    else:
        v = "NOT SUPPORTED"
    say("H3:", v)
    # descriptive: same-day link
    say("  (descriptive) same-day corr(flow_z, ret_z):", round(t.flow_btc_z.corr(t.ret_z), 3))
    return pa, pb


def cross_checks(d):
    say("\n=== Basis proxy cross-checks ===")
    B = build._load("binance.json")
    h = pd.Series({pd.Timestamp(ms, unit="ms"): px for ms, px in B["spot_1h"]})
    D = build._load("deribit.json")
    rows = []
    for exp, series in D.items():
        e = pd.Timestamp(exp) + pd.Timedelta(hours=8)
        for ms, px in series:
            ts = pd.Timestamp(ms, unit="ms") + pd.Timedelta(days=1)  # candle close
            if ts < e - pd.Timedelta(hours=1) and ts - pd.Timedelta(hours=1) in h.index:
                s = h[ts - pd.Timedelta(hours=1)]
                tau = (e - ts).total_seconds() / 86400
                rows.append((ts.normalize(), exp, tau, (px / s - 1) * 365 / tau))
    x = pd.DataFrame(rows, columns=["date", "exp", "tau", "b"])
    cm = {}
    for dt, g in x.groupby("date"):
        g = g.sort_values("tau")
        g = g[g.tau >= 7]
        lo, hi = g[g.tau <= 90].tail(1), g[g.tau > 90].head(1)
        if len(lo) and len(hi):
            t0, b0, t1, b1 = lo.tau.iloc[0], lo.b.iloc[0], hi.tau.iloc[0], hi.b.iloc[0]
            cm[dt] = b0 + (b1 - b0) * (90 - t0) / (t1 - t0)
    der = pd.Series(cm)
    bas = build.basis_90d(B["spot_1d"], B["cq_1d"], B["nq_1d"]).basis
    bas.index = bas.index + pd.Timedelta(days=1)  # label by close time, like Deribit
    j = pd.DataFrame({"binance": bas, "deribit": der}).dropna()
    jt = j[j.index >= build.TEST_START]
    say(f"Deribit vs Binance 90d basis, test: n={len(jt)}, level corr {jt.binance.corr(jt.deribit):.3f}, "
        f"5d-change corr {jt.binance.diff(5).corr(jt.deribit.diff(5)):.3f}, "
        f"mean {jt.binance.mean() * 100:.2f}% vs {jt.deribit.mean() * 100:.2f}%")
    # Yahoo CME front month: premium over Binance daily spot, annualised to the
    # last Friday of the month (assumes Yahoo holds the current-month contract).
    Y = build._load("yahoo.json")
    # Yahoo labels each session by its date; the close is 16:00 Chicago time,
    # so compare with Binance hourly spot at that moment.
    y = pd.Series({pd.Timestamp(t, unit="s").normalize(): p for t, p in Y if p})
    chi = "America/Chicago"
    rows = []
    for dt, p in y.items():
        close = pd.Timestamp(dt.date()).tz_localize(chi) + pd.Timedelta(hours=16)
        candle = close.tz_convert("UTC").tz_localize(None) - pd.Timedelta(hours=1)
        last = (dt + pd.offsets.MonthEnd(0))
        while last.weekday() != 4:
            last -= pd.Timedelta(days=1)
        tau = (last - dt).days
        if tau >= 10 and candle in h.index:  # skip the roll window
            rows.append((dt, (p / h[candle] - 1) * 365 / tau))
    cme = pd.Series(dict(rows))
    mon = pd.DataFrame({"binance": build.basis_90d(B["spot_1d"], B["cq_1d"], B["nq_1d"]).basis,
                        "cme_yahoo": cme}).dropna().resample("QE").mean()
    mt = mon[mon.index >= build.TEST_START]
    say("Quarterly mean annualised basis, Binance 90d vs Yahoo CME front month (rough):")
    for i, r in mon.iterrows():
        say(f"  {i.date()}  binance {r.binance * 100:5.1f}%  cme {r.cme_yahoo * 100:5.1f}%")
    same = np.sign(mt.binance.iloc[-1] - mt.binance.iloc[0]) == np.sign(mt.cme_yahoo.iloc[-1] - mt.cme_yahoo.iloc[0])
    say(f"Direction over test period agrees: {bool(same)}; quarterly corr {mt.binance.corr(mt.cme_yahoo):.3f}")


def main():
    d = build.daily()
    w = build.weekly(d)
    thr = thresholds(d, w)
    say(f"Data through {d.index.max().date()} (flows), last COT {w.index.max().date()}")
    say(f"Thresholds (from 2024): {thr}")
    p1 = h1(w, thr)
    p2 = h2(d, thr)
    h3(d)
    cross_checks(d)
    Path(__file__).with_name("results.txt").write_text("\n".join(OUT) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
