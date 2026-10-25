from datetime import date as Date
from functools import lru_cache
from typing import Optional

import pandas as pd
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from . import processing as P

CUTOFF_RE = r"^([01]\d|2[0-3]):[0-5]\d$"
ISO = "%Y-%m-%dT%H:%M:%SZ"

app = FastAPI(title="Wind Forecast Portal API")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@lru_cache(maxsize=1)
def raw():
    return P.load_raw()


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
        "error_definition": "actual - forecast (negative bias = forecast too high)",
    }


@app.get("/api/forecast")
def forecast(date: Date = Query(...), cutoff: str = Query(P.DEFAULT_CUTOFF, pattern=CUTOFF_RE)):
    if not (P.JAN_START <= date <= P.JAN_END):
        raise HTTPException(400, "date must be within January 2026")
    d = selected(cutoff)
    d = d[d["delivery_date"] == date]
    if d.empty:
        raise HTTPException(404, "no forecast available for that date and cutoff")
    d = d.merge(raw()[0], on="startTime", how="left").sort_values("startTime")
    p90 = P.metrics(joined(cutoff)).get("abs_error_p90") or 0.0
    d["lower"] = (d["forecast"] - p90).clip(lower=0)
    d["upper"] = d["forecast"] + p90
    pts = d[["startTime", "forecast", "actual", "publishTime", "horizon_h", "lower", "upper"]]
    return {
        "date": str(date),
        "cutoff_local": cutoff,
        "cutoff_utc": P.cutoff_utc(date, cutoff).strftime(ISO),
        "publish_times_used": sorted(set(d["publishTime"].dt.strftime(ISO))),
        "p90_abs_error": p90,
        "points": records(pts),
    }


@app.get("/api/metrics")
def get_metrics(start: Optional[Date] = None, end: Optional[Date] = None,
                cutoff: str = Query(P.DEFAULT_CUTOFF, pattern=CUTOFF_RE)):
    s, e = _range(start, end)
    m = P.filter_range(joined(cutoff), s, e)
    return {"cutoff": cutoff, "start": str(s), "end": str(e), "metrics": P.metrics(m)}


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
