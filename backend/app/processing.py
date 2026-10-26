"""Core logic: pick the latest forecast available at the D-1 cutoff,
join with actuals, and compute error metrics. error = actual - forecast."""
import os
from datetime import date, timedelta

import numpy as np
import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DEFAULT_CUTOFF = "09:00"  # UK local time on the day before delivery (D-1)
JAN_START = date(2026, 1, 1)
JAN_END = date(2026, 1, 31)


def load_raw(data_dir=DATA_DIR):
    act = pd.read_csv(os.path.join(data_dir, "actuals_raw.csv"), parse_dates=["startTime"])
    act = act[["startTime", "generation"]].rename(columns={"generation": "actual"})
    fc = pd.read_csv(os.path.join(data_dir, "forecasts_raw.csv"),
                     parse_dates=["startTime", "publishTime"])
    fc = fc[["publishTime", "startTime", "generation"]].rename(columns={"generation": "forecast"})
    fc["horizon_h"] = (fc["startTime"] - fc["publishTime"]).dt.total_seconds() / 3600
    # Publications also contain hours already in the past; they are not forecasts.
    return act, fc[fc["horizon_h"] > 0].copy()


def cutoff_utc(delivery_day, cutoff=DEFAULT_CUTOFF):
    """Cutoff = (delivery day - 1) at HH:MM UK local time, returned in UTC."""
    h, m = (int(x) for x in cutoff.split(":"))
    local = pd.Timestamp(delivery_day) - pd.Timedelta(days=1) + pd.Timedelta(hours=h, minutes=m)
    return local.tz_localize("Europe/London").tz_convert("UTC")


def select_forecasts(fc, cutoff=DEFAULT_CUTOFF, start=JAN_START, end=JAN_END):
    """For every target slot keep the latest forecast published at or before the cutoff."""
    fc = fc.copy()
    fc["delivery_date"] = fc["startTime"].dt.date
    fc = fc[(fc["delivery_date"] >= start) & (fc["delivery_date"] <= end)]
    if fc.empty:
        return fc.assign(cutoff=pd.NaT)
    cmap = {d: cutoff_utc(d, cutoff) for d in fc["delivery_date"].unique()}
    fc["cutoff"] = pd.to_datetime(fc["delivery_date"].map(cmap), utc=True)
    eligible = fc[fc["publishTime"] <= fc["cutoff"]]
    return (eligible.sort_values("publishTime")
            .groupby("startTime", as_index=False).last())


def join_actuals(sel, act):
    m = sel.merge(act, on="startTime", how="inner")
    m["err"] = m["actual"] - m["forecast"]
    m["abs_err"] = m["err"].abs()
    return m


def filter_range(m, start, end):
    return m[(m["delivery_date"] >= start) & (m["delivery_date"] <= end)]


def _f(x):
    x = float(x)
    return None if np.isnan(x) else round(x, 2)


def metrics(m):
    if m.empty:
        return {"n": 0}
    err, ae = m["err"], m["abs_err"]
    nonzero = m["actual"].replace(0, np.nan)
    return {
        "n": int(len(m)),
        "mae": _f(ae.mean()),
        "rmse": _f(np.sqrt((err ** 2).mean())),
        "bias": _f(err.mean()),
        "mape_pct": _f((ae / nonzero).mean() * 100),
        "nmae_pct": _f(ae.mean() / m["actual"].mean() * 100),
        "abs_error_p50": _f(ae.quantile(0.5)),
        "abs_error_p90": _f(ae.quantile(0.9)),
        "abs_error_p95": _f(ae.quantile(0.95)),
        "mean_actual": _f(m["actual"].mean()),
    }


def _agg(g):
    return g.agg(
        n=("err", "size"),
        mae=("abs_err", "mean"),
        bias=("err", "mean"),
        rmse=("err", lambda s: float(np.sqrt((s ** 2).mean()))),
        p90=("abs_err", lambda s: float(s.quantile(0.9))),
    ).round(1)


def breakdown_by_hour(m):
    return _agg(m.groupby(m["startTime"].dt.hour)).rename_axis("hour").reset_index()


def breakdown_by_day(m):
    return _agg(m.groupby("delivery_date")).rename_axis("date").reset_index()


def breakdown_by_horizon(fc, act, start=JAN_START, end=JAN_END, bin_h=6):
    """Accuracy vs lead time, using ALL forecasts (not only the cutoff-selected ones)."""
    d = fc.copy()
    d["delivery_date"] = d["startTime"].dt.date
    d = d[(d["delivery_date"] >= start) & (d["delivery_date"] <= end)]
    m = join_actuals(d, act)
    m["bucket"] = ((m["horizon_h"] // bin_h) * bin_h).astype(int)
    out = _agg(m.groupby("bucket")).reset_index()
    out["label"] = out["bucket"].astype(str) + "-" + (out["bucket"] + bin_h).astype(str) + "h"
    return out


# ---------- walk-forward uncertainty band, coverage and data quality ----------

def walk_forward_bands(m, min_days=3, lo_q=0.05, hi_q=0.95):
    """For delivery day D, 5th/95th percentile of the signed error (actual - forecast)
    using only delivery days <= D-2 (day D-1 is not fully known at the cutoff)."""
    out = {}
    for d in sorted(m["delivery_date"].unique()):
        hist = m[m["delivery_date"] <= d - timedelta(days=2)]
        if hist["delivery_date"].nunique() >= min_days:
            out[d] = (float(hist["err"].quantile(lo_q)), float(hist["err"].quantile(hi_q)), int(len(hist)))
    return out


def band_coverage(m):
    """Share of actual values that fell inside the walk-forward band (nominal 90%)."""
    bands = walk_forward_bands(m)
    slots = inside = 0
    for d, (lo, hi, _n) in bands.items():
        day = m[m["delivery_date"] == d]
        slots += len(day)
        inside += int(((day["err"] >= lo) & (day["err"] <= hi)).sum())
    return {
        "nominal_pct": 90.0,
        "days_with_band": len(bands),
        "slots": int(slots),
        "inside": int(inside),
        "coverage_pct": round(inside / slots * 100, 1) if slots else None,
        "min_history_days": 3,
    }


def quality_report(data_dir=DATA_DIR):
    act = pd.read_csv(os.path.join(data_dir, "actuals_raw.csv"), parse_dates=["startTime"])
    fc = pd.read_csv(os.path.join(data_dir, "forecasts_raw.csv"), parse_dates=["startTime", "publishTime"])
    horizon = (fc["startTime"] - fc["publishTime"]).dt.total_seconds() / 3600
    return {
        "actual_rows": int(len(act)),
        "actual_expected_half_hours": 1488,
        "actual_missing_half_hours": 1488 - int(act["startTime"].nunique()),
        "actual_duplicate_slots": int(act["startTime"].duplicated().sum()),
        "actual_used_on_the_hour": int((act["startTime"].dt.minute == 0).sum()),
        "forecast_rows": int(len(fc)),
        "forecast_publications": int(fc["publishTime"].nunique()),
        "forecast_duplicate_rows": int(fc.duplicated(["publishTime", "startTime"]).sum()),
        "forecast_rows_dropped_target_not_after_publish": int((horizon <= 0).sum()),
    }
