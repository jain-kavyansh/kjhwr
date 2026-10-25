"""Core logic: pick the latest forecast available at the D-1 cutoff,
join with actuals, and compute error metrics. error = actual - forecast."""
import os
from datetime import date

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
