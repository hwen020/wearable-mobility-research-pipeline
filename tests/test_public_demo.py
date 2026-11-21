import sqlite3
from contextlib import closing

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db import build_engine
from app.demo_seed import create_demo_csv
from app.main import create_app
from app.pipeline import import_csv_bytes


def test_public_demo_blocks_all_mutating_requests_before_parsing(monkeypatch, tmp_path):
    monkeypatch.setenv("DEMO_PUBLIC_READONLY", "true")
    monkeypatch.setenv("DEMO_RESET_ENABLED", "1")
    engine = build_engine(f"sqlite:///{tmp_path / 'public.db'}")
    app = create_app(engine)

    @app.patch("/api/future-write")
    def future_write():
        raise AssertionError("Public middleware allowed a future mutating endpoint")

    try:
        with TestClient(app) as client:
            health = client.get("/api/health").json()
            assert health["public_read_only"] and health["read_only"]
            assert not health["demo_restore_enabled"]
            assert "/api/import" not in client.get("/openapi.json").json()["paths"]
            for method, path in (
                ("POST", "/api/import"), ("POST", "/api/demo/restore"),
                ("DELETE", "/api/participants/SYN-P001"), ("PUT", "/"),
                ("PATCH", "/api/future-write"), ("POST", "/static/app.js"),
            ):
                response = client.request(method, path, content=b"malformed")
                assert response.status_code == 403
            assert client.get("/api/summary").json()["observations"] == 0
    finally:
        engine.dispose()


def test_public_get_routes_leave_database_unchanged(monkeypatch, tmp_path):
    monkeypatch.setenv("DEMO_PUBLIC_READONLY", "true")
    monkeypatch.setenv("DEMO_RESET_ENABLED", "1")
    database = tmp_path / "public-reads.db"
    engine = build_engine(f"sqlite:///{database}")

    def snapshot():
        with closing(sqlite3.connect(database)) as connection:
            return tuple(connection.iterdump())

    try:
        with TestClient(create_app(engine)) as client:
            demo = create_demo_csv(tmp_path / "synthetic-fixture.csv").read_bytes()
            with Session(engine) as session, session.begin():
                batch = import_csv_bytes(session, demo, "synthetic-fixture.csv")
                duplicate = import_csv_bytes(session, demo, "synthetic-fixture.csv")
            assert (batch["accepted"], duplicate["duplicates"]) == (366, 366)
            before = snapshot()
            base = "/api/participants/SYN-P001"
            for path in (
                "/", "/static/app.js", "/docs", "/openapi.json", "/api/health",
                "/api/summary", "/api/participants", base + "/daily",
                base + "/geojson?date=2026-11-16&download=true&layer=activity_area",
                base + "/geojson?metadata_only=true", base + "/stays?date=2026-11-16",
                base + "/observations?include_quality=true",
                base + "/export.csv?dataset=observations", base + "/export.csv?dataset=daily",
                "/api/imports", f"/api/imports?batch_id={duplicate['import_id']}&outcome=duplicate",
            ):
                assert client.get(path).status_code == 200, path
            assert client.get("/api/import").status_code == 405
            assert client.get("/api/demo/restore").status_code == 404
            assert client.get("/api/summary").json()["observations"] == 366
            assert snapshot() == before
    finally:
        engine.dispose()
