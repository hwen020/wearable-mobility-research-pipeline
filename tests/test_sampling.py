import csv
import io
from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app.analytics import daily_summary
from app.db import build_engine
from app.main import create_app
from app.sampling import SamplingPolicy


def policy(start, end, interval):
    return SamplingPolicy(datetime.fromisoformat(start), datetime.fromisoformat(end), interval)


def point(stamp, latitude=34):
    return SimpleNamespace(timestamp_utc=datetime.fromisoformat(stamp), latitude=latitude,
                           longitude=-118, steps=0, heart_rate_bpm=None)


@pytest.mark.parametrize("interval, expected, occupied", [(300, 4, 2), (600, 2, 2), (900, 2, 1)])
def test_coverage_counts_distinct_valid_slots(interval, expected, occupied):
    points = [point(f"2026-11-16T00:{minute}") for minute in ("00", "01", "12", "18", "20")]
    points[3].latitude = 35
    points[4].latitude = 35
    sampling = policy("2026-11-16T00:00", "2026-11-16T00:20", interval)
    row, = daily_summary(points, sampling=sampling)
    assert row["observed_validity_rate"] == row["screened_gps_ratio"] == 0.8
    assert row["expected_sampling_slots"] == expected
    assert row["occupied_sampling_slots"] == occupied
    assert row["expected_sampling_coverage"] == occupied / expected


def test_cross_date_empty_day_and_unconfigured():
    points = [point("2026-11-16T23:58"), point("2026-11-19T00:00")]
    sampling = policy("2026-11-16T23:55", "2026-11-18T00:05", 300)
    rows = daily_summary(points, sampling=sampling)
    assert [row["expected_sampling_slots"] for row in rows] == [1, 288, 1, None]
    assert [row["expected_sampling_coverage"] for row in rows] == [1, 0, 0, None]
    assert rows[1]["observed_validity_rate"] is None
    assert daily_summary(points)[0]["expected_sampling_coverage"] is None


@pytest.mark.parametrize("start, end, expected", [
    ("2026-03-08T08:00", "2026-03-09T07:00", 23),
    ("2026-11-01T07:00", "2026-11-02T08:00", 25),
])
def test_elapsed_slots_on_dst_dates(start, end, expected):
    zone = ZoneInfo("America/Los_Angeles")
    row, = daily_summary([], zone, sampling=policy(start, end, 3600))
    assert row["expected_sampling_slots"] == expected
    assert row["expected_sampling_coverage"] == 0


def test_repeated_fall_back_hour_occupies_two_slots():
    zone = ZoneInfo("America/Los_Angeles")
    sampling = policy("2026-11-01T07:00", "2026-11-02T08:00", 3600)
    row, = daily_summary([point("2026-11-01T08:30"), point("2026-11-01T09:30")],
                         zone, sampling=sampling)
    assert row["occupied_sampling_slots"] == 2
    assert row["expected_sampling_coverage"] == 0.08


def test_partial_sampling_configuration_fails(monkeypatch):
    monkeypatch.setenv("GPS_WINDOW_START", "2026-11-16T00:00Z")
    with pytest.raises(ValueError, match="GPS_WINDOW_END"):
        SamplingPolicy.from_environment()


def test_daily_coverage_api_csv_and_version(monkeypatch, tmp_path):
    monkeypatch.setenv("GPS_WINDOW_START", "2026-11-16T00:00Z")
    monkeypatch.setenv("GPS_WINDOW_END", "2026-11-17T00:10Z")
    monkeypatch.setenv("GPS_EXPECTED_INTERVAL_SECONDS", "300")
    engine = build_engine(f"sqlite:///{tmp_path / 'coverage.db'}")
    try:
        with TestClient(create_app(engine)) as client:
            data = ("participant_id,timestamp_utc,latitude,longitude,steps\n"
                    "SYN-COVERAGE,2026-11-16T00:00:00Z,34,-118,1\n")
            assert client.post("/api/import", files={"file": ("coverage.csv", data)}).json()["accepted"] == 1
            root = "/api/participants/SYN-COVERAGE"
            assert client.get("/api/health").json()["version"] == "1.0.0"
            rows = client.get(root + "/daily").json()
            assert [r["expected_sampling_slots"] for r in rows] == [288, 2]
            assert client.get("/api/participants").json()[0]["dates"] == ["2026-11-16", "2026-11-17"]
            response = client.get(root + "/export.csv?dataset=daily&date=2026-11-17")
            exported, = csv.DictReader(io.StringIO(response.text))
            assert (exported["observed_validity_rate"], exported["expected_sampling_coverage"]) == ("", "0.0")
            metadata = client.get(root + "/geojson?metadata_only=true").json()
            assert metadata["parameters"]["expected_sampling"]["interval_seconds"] == 300
    finally:
        engine.dispose()


def test_read_only_mode_rejects_upload_and_disables_reset(monkeypatch, tmp_path):
    monkeypatch.setenv("DEMO_READ_ONLY", "1")
    monkeypatch.setenv("DEMO_RESET_ENABLED", "1")
    engine = build_engine(f"sqlite:///{tmp_path / 'readonly.db'}")
    try:
        with TestClient(create_app(engine)) as client:
            health = client.get("/api/health").json()
            assert health["read_only"] and not health["demo_restore_enabled"]
            assert client.post("/api/import", files={"file": ("example.csv", b"synthetic")}).status_code == 403
            assert client.post("/api/demo/restore", json={}).status_code == 404
    finally:
        engine.dispose()
