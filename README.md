# Wind forecast evaluation viewer for day-ahead buying

A web app that helps a UK energy utility's day-ahead buying team (1) see the latest wind forecast available at their decision time and (2) quantify how accurate those forecasts have been. It uses GB national wind data from Elexon BMRS for January 2026 only.

## Scope: what this is and is not

This is a **historical forecast evaluation prototype** for January 2026. It replays the Elexon wind forecasts that were available before each day-ahead cutoff and compares them with actual generation. It is not a live forecast, it does not produce its own forecast, and it does not estimate demand or recommend how much power to buy.

Data provenance (also shown in the app, on the "Data and method" tab): actuals are Elexon FUELHH (fuel type WIND, MW, 30-minute resolution, settlement dates 1 to 31 January 2026); forecasts are Elexon WINDFOR (MW, hourly, published 31 December 2025 to 1 February 2026). A snapshot of both was downloaded once and stored in `backend/data`; `backend/data/snapshot.json` records when. The app serves this snapshot and does not call Elexon live.

Uncertainty band: for delivery day D, the band is the forecast plus the 5th to 95th percentile of the signed error (actual minus forecast) from delivery days up to D-2 only. Its measured coverage on later days is reported in the app. It is an empirical guide, not a validated prediction interval, and one month of data is indicative only.

## Live app

- Frontend: https://kjhwr-web.vercel.app
- Backend API: https://kjhwr-api.vercel.app (try `/health`, `/api/metrics`, `/docs`)

Both are hosted on Vercel's free plan. The first request after a quiet period can take a few seconds.

## Key idea

Many forecasts exist for each target hour, published at different times. The buyer can only use forecasts published before their cutoff on the day before delivery (D-1). For every target hour the app picks the latest forecast published at or before the cutoff, joins it with the actual generation, and measures the error.

## Assumptions

- Cutoff: configurable in the UI, default 09:00 UK time on D-1. In January UK time equals UTC.
- Error is defined as actual minus forecast. A negative bias means the forecast was too high.
- Forecasts (WINDFOR) are hourly and actuals (FUELHH) are half-hourly, so the comparison uses the on-the-hour slots only: 24 per day, 744 for January.
- Forecast rows whose target time is before their publish time are not forecasts and are dropped.
- Data covers delivery days 1 to 31 January 2026. Forecasts published from 31 December 2025 are included.
- The lead-time chart uses every forecast version, not only the one chosen at the cutoff.

## Results (cutoff 09:00, January 2026)

| Metric | Value |
|---|---|
| MAE | about 2,127 MW (18.4% of mean output of 11,581 MW) |
| RMSE | about 2,606 MW |
| Bias (actual - forecast) | about -1,852 MW |
| Median / P90 / P95 absolute error | 1,759 / 4,306 / 5,351 MW |

The forecasts were systematically too high in January, so the main risk for the buyer is under-buying.

## Repository layout

```
.
├── README.md
├── docker-compose.yml          # starts backend (8000) and frontend (8080)
├── backend/
│   ├── app/
│   │   ├── main.py             # FastAPI app and endpoints
│   │   └── processing.py       # cutoff selection, join, metrics, breakdowns
│   ├── tests/                  # pytest unit and API tests
│   ├── data/                   # downloaded Elexon data (CSV)
│   ├── fetch_data.py           # downloads the data from the Elexon API
│   ├── check_data.py           # data sanity checks
│   ├── analyze.py              # exploratory run of the core logic
│   ├── index.py                # entry point used by Vercel
│   ├── Dockerfile
│   ├── pytest.ini
│   └── requirements.txt
└── frontend/
    ├── src/
    │   ├── App.jsx             # layout and tabs
    │   ├── api.js              # API client and formatters
    │   ├── pages/Forecast.jsx  # latest forecast page
    │   ├── pages/Accuracy.jsx  # accuracy page
    │   ├── index.css
    │   └── main.jsx
    ├── nginx.conf              # serves the build and proxies /api in Docker
    ├── Dockerfile
    ├── vite.config.js          # dev proxy to the backend
    ├── vercel.json
    └── package.json
```

## How to start the app

### Option 1: Docker (one command)

Install and open Docker Desktop, then from the repo root:

```
docker compose up --build
```

Open http://localhost:8080. The API is at http://localhost:8000/docs. Stop with `docker compose down`.

### Option 2: run locally

Backend (Python 3.9 or newer):

```
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8000
```

Frontend (Node 18 or newer), in a second terminal:

```
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. In development, calls to `/api` are proxied to port 8000. For a separately hosted backend, set `VITE_API_URL` at build time.

### Refresh the data (optional)

```
cd backend
python fetch_data.py
```

### Run the tests

```
cd backend
python -m pytest -q
```

## API endpoints

| Endpoint | Purpose |
|---|---|
| `GET /health` | health check |
| `GET /api/meta` | date range, default cutoff, definitions |
| `GET /api/forecast?date=&cutoff=` | forecast used at the cutoff for one delivery day, with the P90 band |
| `GET /api/metrics?start=&end=&cutoff=` | MAE, RMSE, bias, MAPE, percentiles |
| `GET /api/error-breakdown?by=hour\|day\|horizon` | error breakdowns |
| `GET /api/actuals?start=&end=` | actual generation |
| `GET /api/band-coverage` | measured hit rate of the walk-forward band |
| `GET /api/data-quality` | provenance, missing and duplicate checks |

## Limitations and next steps

- One month of data, so the error statistics are indicative and not stable estimates.
- The cutoff is a single assumed time, not the exchange's exact gate closure.
- Possible extensions: live data refresh, demand data to compute the residual purchase need, confidence bands by hour of day, a bias correction.

## AI tools

An AI chat assistant was used to help with planning and code. All code was run, tested and reviewed by the author.
