import json
import os
from datetime import date as Date
from functools import lru_cache
from typing import Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from . import processing as P

CUTOFF_RE = r"^([01]\d|2[0-3]):[0-5]\d$"
ISO = "%Y-%m-%dT%H:%M:%SZ"

app = FastAPI(title="Wind Forecast Evaluation API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@lru_cache(maxsize=1)
def raw():
    return P.load_raw()


@lru_cache(maxsize=1)
def quality():
    return P.quality_report()


def snapshot():
    try:
        with open(os.path.join(P.DATA_DIR, "snapshot.json")) as f:
            return json.load(f)
    except Exception:
        return {}


@lru_cache(maxsize=32)
def selected(cutoff):
    return P.select_forecasts(raw()[1], cutoff)


@lru_cache(maxsize=32)
def joined(cutoff):
    return P.join_actuals(selected(cutoff), raw()[0])


def records(df):
    out = df.copy()
    for c in out.columns:
        if pd.api.types.is_datetime64_any_dtype(out[c]):
            out[c] = out[c].dt.strftime(ISO)
        elif out[c].dtype == object:
            out[c] = out[c].astype(str)
    out = out.astype(object).where(out.notna(), None)
    return out.to_dict(orient="records")


def _range(start, end):
    return start or P.JAN_START, end or P.JAN_END


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/meta")
def meta():
    return {
        "min_date": str(P.JAN_START),
        "max_date": str(P.JAN_END),
        "default_cutoff": P.DEFAULT_CUTOFF,
        "timezone": "Europe/London",
        "resolution": "hourly",
        "mode": "historical evaluation (not live)",
        "error_definition": "actual - forecast (negative bias = forecast too high)",
    }


@app.get("/api/forecast")
def forecast(date: Date = Query(...), cutoff: str = Query(P.DEFAULT_CUTOFF, pattern=CUTOFF_RE)):
    if not (P.JAN_START <= date <= P.JAN_END):
        raise HTTPException(400, "date must be within January 2026")
    d = selected(cutoff)
    d = d[d["delivery_date"] == date]
    if d.empty:
        raise HTTPException(404, "no forecast was published before that cutoff for this date")
    d = d.merge(raw()[0], on="startTime", how="left").sort_values("startTime")
    d["err"] = d["actual"] - d["forecast"]

    b = P.walk_forward_bands(joined(cutoff)).get(date)
    if b:
        lo, hi, n_hist = b
        d["lower"] = (d["forecast"] + lo).clip(lower=0)
        d["upper"] = d["forecast"] + hi
        band = {"available": True, "lo_err": round(lo, 1), "hi_err": round(hi, 1), "history_slots": n_hist,
                "method": "5th and 95th percentile of actual - forecast, from delivery days up to D-2"}
    else:
        d["lower"] = float("nan")
        d["upper"] = float("nan")
        band = {"available": False,
                "method": "needs at least 3 earlier delivery days (up to D-2) of history"}

    pts = d[["startTime", "forecast", "actual", "err", "publishTime", "horizon_h", "lower", "upper"]]
    return {
        "date": str(date),
        "cutoff_local": cutoff,
        "cutoff_timezone": "Europe/London",
        "cutoff_utc": P.cutoff_utc(date, cutoff).strftime(ISO),
        "publish_times_used": sorted(set(d["publishTime"].dt.strftime(ISO))),
        "hours_available": int(len(d)),
        "hours_missing": int(24 - len(d)),
        "band": band,
        "points": records(pts),
    }


@app.get("/api/metrics")
def get_metrics(start: Optional[Date] = None, end: Optional[Date] = None,
                cutoff: str = Query(P.DEFAULT_CUTOFF, pattern=CUTOFF_RE)):
    s, e = _range(start, end)
    m = P.filter_range(joined(cutoff), s, e)
    return {"cutoff": cutoff, "start": str(s), "end": str(e), "metrics": P.metrics(m)}


@app.get("/api/band-coverage")
def band_coverage(cutoff: str = Query(P.DEFAULT_CUTOFF, pattern=CUTOFF_RE)):
    return P.band_coverage(joined(cutoff))


@app.get("/api/data-quality")
def data_quality(cutoff: str = Query(P.DEFAULT_CUTOFF, pattern=CUTOFF_RE)):
    sel, m = selected(cutoff), joined(cutoff)
    expected = 31 * 24
    return {
        **quality(),
        "cutoff": cutoff,
        "expected_hourly_slots": expected,
        "hours_with_forecast": int(len(sel)),
        "hours_missing_forecast": expected - int(len(sel)),
        "pairs_used": int(len(m)),
        "pairs_excluded_no_actual": int(len(sel)) - int(len(m)),
        "snapshot": snapshot(),
    }


@app.get("/api/error-breakdown")
def error_breakdown(by: str = Query("hour", pattern="^(hour|horizon|day)$"),
                    start: Optional[Date] = None, end: Optional[Date] = None,
                    cutoff: str = Query(P.DEFAULT_CUTOFF, pattern=CUTOFF_RE)):
    s, e = _range(start, end)
    if by == "horizon":
        act, fc = raw()
        df = P.breakdown_by_horizon(fc, act, s, e)
    else:
        m = P.filter_range(joined(cutoff), s, e)
        df = P.breakdown_by_hour(m) if by == "hour" else P.breakdown_by_day(m)
    return {"by": by, "rows": records(df)}


@app.get("/api/actuals")
def actuals(start: Optional[Date] = None, end: Optional[Date] = None):
    s, e = _range(start, end)
    a = raw()[0]
    d = a[(a["startTime"].dt.date >= s) & (a["startTime"].dt.date <= e)]
    return {"rows": records(d)}
