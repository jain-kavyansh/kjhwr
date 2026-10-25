import pandas as pd
import pytest

from app import processing as P


def make_fc(rows):
    df = pd.DataFrame(rows, columns=["publishTime", "startTime", "forecast"])
    df["publishTime"] = pd.to_datetime(df["publishTime"], utc=True)
    df["startTime"] = pd.to_datetime(df["startTime"], utc=True)
    df["horizon_h"] = (df["startTime"] - df["publishTime"]).dt.total_seconds() / 3600
    return df


# Same target slot (10 Jan 12:00), three forecasts published at different times
ROWS = [
    ("2026-01-09 06:00", "2026-01-10 12:00", 100),
    ("2026-01-09 08:00", "2026-01-10 12:00", 200),
    ("2026-01-09 10:00", "2026-01-10 12:00", 300),  # after the 09:00 cutoff
]


def test_picks_latest_forecast_before_cutoff():
    sel = P.select_forecasts(make_fc(ROWS), "09:00")
    assert len(sel) == 1
    assert sel.iloc[0]["forecast"] == 200


def test_ignores_forecasts_published_after_cutoff():
    assert P.select_forecasts(make_fc([ROWS[2]]), "09:00").empty


def test_cutoff_is_configurable():
    assert P.select_forecasts(make_fc(ROWS), "07:00").iloc[0]["forecast"] == 100
    assert P.select_forecasts(make_fc(ROWS), "11:00").iloc[0]["forecast"] == 300


def test_error_sign_is_actual_minus_forecast():
    sel = P.select_forecasts(make_fc(ROWS), "09:00")
    act = pd.DataFrame({"startTime": [pd.Timestamp("2026-01-10 12:00", tz="UTC")], "actual": [250]})
    m = P.join_actuals(sel, act)
    assert m.iloc[0]["err"] == 50


def test_metrics_on_known_data():
    m = pd.DataFrame({"actual": [1000, 1000, 1000], "err": [100.0, -100.0, 300.0]})
    m["abs_err"] = m["err"].abs()
    r = P.metrics(m)
    assert r["mae"] == pytest.approx(166.67, abs=0.01)
    assert r["bias"] == pytest.approx(100.0, abs=0.01)
    assert r["rmse"] == pytest.approx(191.49, abs=0.01)
