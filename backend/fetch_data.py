import os
import requests
import pandas as pd
from datetime import datetime, timedelta

BASE = "https://data.elexon.co.uk/bmrs/api/v1/datasets"
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(DATA_DIR, exist_ok=True)


def get_json(url, params):
    r = requests.get(url, params=params, timeout=60)
    if not r.ok:
        print("ERROR", r.status_code, r.url)
        print(r.text[:500])
        r.raise_for_status()
    return r.json()


# 1) Actuals: wind only, all of January 2026
actuals = get_json(f"{BASE}/FUELHH/stream", {
    "settlementDateFrom": "2026-01-01",
    "settlementDateTo": "2026-01-31",
    "fuelType": "WIND",
})
df_act = pd.DataFrame(actuals)
df_act.to_csv(os.path.join(DATA_DIR, "actuals_raw.csv"), index=False)
print("Actuals rows:", len(df_act))

# 2) Forecasts: fetched in 2-day chunks
start = datetime(2025, 12, 31)
end = datetime(2026, 2, 1)
step = timedelta(days=2)
frames = []
t = start
while t < end:
    t2 = min(t + step, end)
    rows = get_json(f"{BASE}/WINDFOR/stream", {
        "publishDateTimeFrom": t.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "publishDateTimeTo": t2.strftime("%Y-%m-%dT%H:%M:%SZ"),
    })
    print(t.date(), "->", t2.date(), ":", len(rows), "rows")
    frames.append(pd.DataFrame(rows))
    t = t2

df_for = pd.concat(frames, ignore_index=True)
df_for.to_csv(os.path.join(DATA_DIR, "forecasts_raw.csv"), index=False)
print("Forecast rows:", len(df_for))

import json
from datetime import timezone
snap = {
    "retrieved_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "source": "Elexon BMRS open data API",
    "actuals": {"dataset": "FUELHH", "fuelType": "WIND", "unit": "MW", "resolution": "30 minutes",
                "settlement_dates": "2026-01-01 to 2026-01-31", "rows": int(len(df_act))},
    "forecasts": {"dataset": "WINDFOR", "unit": "MW", "resolution": "60 minutes",
                  "publish_window_utc": "2025-12-31T00:00Z to 2026-02-01T00:00Z", "rows": int(len(df_for))},
}
with open(os.path.join(DATA_DIR, "snapshot.json"), "w") as f:
    json.dump(snap, f, indent=2)
print("Snapshot written")
