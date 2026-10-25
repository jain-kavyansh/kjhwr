import os
import pandas as pd

D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
act = pd.read_csv(os.path.join(D, "actuals_raw.csv"), parse_dates=["startTime"])
fc = pd.read_csv(os.path.join(D, "forecasts_raw.csv"), parse_dates=["startTime", "publishTime"])

print("\nACTUAL columns:", act.columns.tolist())
print(act.head(3).to_string())
print("\nFORECAST columns:", fc.columns.tolist())
print(fc.head(3).to_string())

print("\nActuals rows:", len(act), "(expected about 1488)")
print("Duplicate actual slots:", act.startTime.duplicated().sum())
print("Forecast publish range:", fc.publishTime.min(), "to", fc.publishTime.max())
print("Forecast target range:", fc.startTime.min(), "to", fc.startTime.max())

fc["horizon_h"] = (fc.startTime - fc.publishTime).dt.total_seconds() / 3600
print("\nHorizon (hours):")
print(fc.horizon_h.describe())
