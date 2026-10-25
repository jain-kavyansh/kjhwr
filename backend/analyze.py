import os
import numpy as np
import pandas as pd

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
CUTOFF_HOUR_UTC = 9  # January: UK time = UTC

act = pd.read_csv(os.path.join(D, "actuals_raw.csv"), parse_dates=["startTime"])
act = act[["startTime", "generation"]].rename(columns={"generation": "actual"})
fc = pd.read_csv(os.path.join(D, "forecasts_raw.csv"), parse_dates=["startTime", "publishTime"])
fc = fc[["publishTime", "startTime", "generation"]].rename(columns={"generation": "forecast"})

print("=== DIAGNOSTICS ===")
print("Unique publish times:", fc.publishTime.nunique())
print("Rows per publishTime:")
print(fc.groupby("publishTime").size().describe().to_string())
print("Minute-of-hour of forecast startTime:", fc.startTime.dt.minute.value_counts().to_dict())
print("Duplicate (publishTime,startTime):", fc.duplicated(["publishTime", "startTime"]).sum())
fc["horizon_h"] = (fc.startTime - fc.publishTime).dt.total_seconds() / 3600
print("Negative-horizon rows:", (fc.horizon_h < 0).sum(), "of", len(fc))

# Drop forecasts that target a time before they were published
fc = fc[fc.horizon_h > 0].copy()

# Delivery day D = UTC date of startTime. Cutoff = D-1 at 09:00.
fc["delivery_date"] = fc.startTime.dt.floor("D")
fc["cutoff"] = fc.delivery_date - pd.Timedelta(days=1) + pd.Timedelta(hours=CUTOFF_HOUR_UTC)

# Keep only January 2026 delivery days
fc = fc[(fc.delivery_date >= "2026-01-01") & (fc.delivery_date < "2026-02-01")]

# Core logic: latest forecast published at or before the cutoff, per target slot
eligible = fc[fc.publishTime <= fc.cutoff]
sel = (eligible.sort_values("publishTime")
       .groupby("startTime", as_index=False).last())

print("\n=== SELECTION ===")
print("Slots selected:", len(sel))
print("Slots per delivery day (min/max):",
      sel.groupby("delivery_date").size().min(), "/",
      sel.groupby("delivery_date").size().max())
print("Horizon used (hours) min/median/max:",
      sel.horizon_h.min(), sel.horizon_h.median(), sel.horizon_h.max())
print(sel[["delivery_date", "startTime", "publishTime", "forecast"]].head(5).to_string())

# Join with actuals and compute errors (error = actual - forecast)
m = sel.merge(act, on="startTime", how="inner")
m["err"] = m.actual - m.forecast
m["abs_err"] = m.err.abs()
m.to_csv(os.path.join(D, "joined.csv"), index=False)

print("\n=== METRICS (Jan 2026, cutoff 09:00 on D-1) ===")
print("Joined slots:", len(m))
print("MAE  (MW):", round(m.abs_err.mean(), 1))
print("RMSE (MW):", round(np.sqrt((m.err ** 2).mean()), 1))
print("Bias (MW, actual-forecast):", round(m.err.mean(), 1))
print("MAPE (%):", round((m.abs_err / m.actual.replace(0, np.nan)).mean() * 100, 1))
print("Abs error P50/P90/P95 (MW):", [round(m.abs_err.quantile(q), 1) for q in (0.5, 0.9, 0.95)])
print("Mean actual (MW):", round(m.actual.mean(), 1), " Max actual:", m.actual.max())
