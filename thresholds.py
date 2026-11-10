"""Thresholds fixed from 2024 (calibration) data only. Prints them and nothing else."""
import build


def thresholds(d=None, w=None):
    d = build.daily() if d is None else d
    w = build.weekly(d) if w is None else w
    cal_w = w[w.index < build.TEST_START]
    cal_d = d.copy()
    cal_d["d_basis_5"] = cal_d.basis - cal_d.basis.shift(5)
    cal_d = cal_d[cal_d.index < build.TEST_START]
    return {
        "h1_large_week_flow_btc": float(cal_w.flow_btc.quantile(0.80)),
        "h2_basis_drop_5d": float(cal_d.d_basis_5.quantile(0.10)),
        "n_cal_weeks": len(cal_w),
        "n_cal_days": int(cal_d.d_basis_5.notna().sum()),
    }


if __name__ == "__main__":
    for k, v in thresholds().items():
        print(k, round(v, 4) if isinstance(v, float) else v)
