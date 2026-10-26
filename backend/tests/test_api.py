from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_forecast_endpoint():
    r = client.get("/api/forecast", params={"date": "2026-01-15", "cutoff": "09:00"})
    assert r.status_code == 200
    body = r.json()
    assert len(body["points"]) == 24
    assert all(p["publishTime"] <= body["cutoff_utc"] for p in body["points"])


def test_metrics_endpoint():
    r = client.get("/api/metrics")
    assert r.status_code == 200
    assert r.json()["metrics"]["n"] == 744


def test_breakdowns():
    assert len(client.get("/api/error-breakdown", params={"by": "hour"}).json()["rows"]) == 24
    assert len(client.get("/api/error-breakdown", params={"by": "day"}).json()["rows"]) == 31
    assert len(client.get("/api/error-breakdown", params={"by": "horizon"}).json()["rows"]) > 0


def test_bad_inputs_rejected():
    assert client.get("/api/forecast", params={"date": "2026-03-01"}).status_code == 400
    assert client.get("/api/metrics", params={"cutoff": "25:99"}).status_code == 422


def test_band_coverage_endpoint():
    body = client.get("/api/band-coverage").json()
    assert body["days_with_band"] == 27
    assert 0 <= body["coverage_pct"] <= 100


def test_data_quality_endpoint():
    body = client.get("/api/data-quality").json()
    assert body["hours_with_forecast"] == 744
    assert body["pairs_used"] == 744
    assert body["actual_duplicate_slots"] == 0
