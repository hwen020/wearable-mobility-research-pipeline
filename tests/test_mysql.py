"""Opt-in acceptance against an empty, disposable MySQL database."""
import os
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import inspect

from app.db import build_engine
from app.demo_seed import create_demo_csv
from app.main import create_app


@pytest.mark.skipif(not os.getenv("MOBILITY_MYSQL_TEST_URL"), reason="requires a disposable MySQL database")
def test_mysql_migrations_and_ingestion(tmp_path):
    engine = build_engine(os.environ["MOBILITY_MYSQL_TEST_URL"])
    try:
        assert engine.url.database.startswith("mobility_test"), "use a disposable mobility_test database"
        assert inspect(engine).get_table_names() == [], "the MySQL test database must be empty"
        with TestClient(create_app(engine)) as client:
            demo = create_demo_csv(tmp_path / "mysql_demo.csv").read_bytes()
            assert client.post("/api/import", files={"file": ("demo.csv", demo)}).json()["accepted"] == 366
            assert client.post("/api/import", files={"file": ("demo.csv", demo)}).json()["duplicates"] == 366
            assert client.get("/api/summary").json()["observations"] == 366
            batches = client.get("/api/imports").json()
            assert client.get("/api/imports", params={"batch_id": batches[0]["id"],
                                                      "outcome": "duplicate"}).json()["total"] == 366
            geojson = client.get("/api/participants/SYN-P001/geojson?date=2026-11-16").json()
            assert "activity_area" in {feature["properties"]["kind"] for feature in geojson["features"]}
            data = ("participant_id,timestamp_utc,latitude,longitude,steps\n"
                    "SYN-MYSQL,2026-11-16T12:00:00.123456Z,34,-118,0\n"
                    "SYN-MYSQL,2026-11-16T12:00:00.123457Z,34,-118,0\n")

            def submit():
                response = client.post("/api/import", files={"file": ("timestamps.csv", data)})
                assert response.status_code == 200
                return response.json()["accepted"], response.json()["duplicates"]

            with ThreadPoolExecutor(max_workers=2) as pool:
                first, second = pool.submit(submit), pool.submit(submit)
                assert sorted((first.result(), second.result())) == [(0, 2), (2, 0)]
            points = client.get("/api/participants/SYN-MYSQL/observations").json()
            assert len(points) == 2 and points[0]["timestamp_utc"].endswith(".123456Z")
    finally:
        engine.dispose()
