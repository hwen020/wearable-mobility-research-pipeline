import hashlib
from datetime import datetime, timedelta, timezone
from time import perf_counter

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.db import build_engine, upgrade_schema
from app.models import ImportDiagnostic
from app.pipeline import import_csv_bytes

HEADER = b"participant_id,timestamp_utc,latitude,longitude,steps,heart_rate_bpm,source\n"
ROW = b"SYN-TEST,2026-11-16T16:00:00Z,34,-118,4,80,synthetic\n"


def upload(client, data):
    return client.post("/api/import", files={"file": ("synthetic.csv", data, "text/csv")})


def test_import_audit_and_safe_diagnostics(client):
    data = HEADER + ROW + ROW.replace(b",34,", b",nan,") * 21
    response = upload(client, data)
    assert response.status_code == 200
    assert response.json()["rejected"] == 21
    assert len(response.json()["errors"]) == 20
    audit = client.get("/api/imports").json()[0]
    assert audit["sha256"] == hashlib.sha256(data).hexdigest()
    assert audit["total_rows"] == 22
    assert audit["duration_ms"] >= 0
    assert audit["source"] == "csv_upload"
    assert audit["schema_version"] == "1"


def test_diagnostics_are_persisted_beyond_response_limit(tmp_path):
    engine = build_engine(f"sqlite:///{tmp_path / 'audit.db'}")
    try:
        upgrade_schema(engine)
        with Session(engine) as session, session.begin():
            import_csv_bytes(session, HEADER + ROW.replace(b",34,", b",inf,") * 21)
        with Session(engine) as session:
            errors = session.scalars(select(ImportDiagnostic).order_by(ImportDiagnostic.row_number)).all()
            assert [error.row_number for error in errors] == list(range(2, 23))
            assert {error.reason for error in errors} == {"coordinates must be finite"}
    finally:
        engine.dispose()


def test_file_error_rolls_back_completed_chunks(client, monkeypatch):
    monkeypatch.setattr("app.pipeline.CHUNK_SIZE", 2)
    response = upload(client, HEADER + ROW + ROW.replace(b",34,", b",999,") + b'"unclosed\n')
    assert response.status_code == 422
    assert client.get("/api/imports").json() == []
    summary = client.get("/api/summary").json()
    assert summary["observations"] == 0
    assert summary["participants"] == 0


def test_header_and_row_shape_validation(client):
    for header in (HEADER.replace(b"source", b"steps"), HEADER.replace(b"source", b"unknown")):
        assert upload(client, header + ROW).status_code == 422
    response = upload(client, HEADER + ROW.rstrip() + b",extra\n")
    assert response.json()["errors"] == [
        {"row": 2, "reason": "CSV record does not match the number of columns"}
    ]


def test_dst_offsets_deduplicate_equivalent_instants(client):
    early = ROW.replace(b"2026-11-16T16:00:00Z", b"2026-11-01T01:30:00-07:00")
    late = ROW.replace(b"2026-11-16T16:00:00Z", b"2026-11-01T01:30:00-08:00")
    utc = ROW.replace(b"2026-11-16T16:00:00Z", b"2026-11-01T08:30:00Z")
    result = upload(client, HEADER + early + late + utc).json()
    assert (result["accepted"], result["duplicates"]) == (2, 1)
    points = client.get("/api/participants/SYN-TEST/observations").json()
    assert [point["timestamp_utc"] for point in points] == [
        "2026-11-01T08:30:00Z", "2026-11-01T09:30:00Z"
    ]


def test_upgrade_preserves_unversioned_v01_rows(tmp_path):
    engine = build_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql(
                "CREATE TABLE import_batches (id INTEGER PRIMARY KEY, filename VARCHAR(160) NOT NULL,"
                " created_at DATETIME NOT NULL, accepted INTEGER NOT NULL, duplicates INTEGER NOT NULL,"
                " rejected INTEGER NOT NULL)"
            )
            connection.exec_driver_sql(
                "INSERT INTO import_batches VALUES (7, 'demo.csv', '2026-11-16', 366, 0, 0)"
            )
        upgrade_schema(engine)
        upgrade_schema(engine)
        assert "import_diagnostics" in inspect(engine).get_table_names()
        with engine.connect() as connection:
            row = connection.exec_driver_sql(
                "SELECT id, filename, accepted, sha256 FROM import_batches"
            ).one()
            assert tuple(row) == (7, "demo.csv", 366, None)
    finally:
        engine.dispose()


@pytest.mark.parametrize("count", [10000, 50000])
def test_large_ingestion_and_replay(tmp_path, count):
    engine = build_engine(f"sqlite:///{tmp_path / 'scale.db'}")
    fixture = tmp_path / "scale.csv"
    epoch = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with fixture.open("wb") as file:
        file.write(HEADER)
        for i in range(count):
            stamp = (epoch + timedelta(seconds=i)).isoformat()
            file.write(f"SYN-SCALE,{stamp},34,-118,4,80,synthetic\n".encode())
    from app.pipeline import import_csv_stream
    try:
        upgrade_schema(engine)
        for replay in (False, True):
            start = perf_counter()
            with Session(engine) as session, session.begin(), fixture.open("rb") as file:
                result = import_csv_stream(session, file, fixture.name)
            elapsed = perf_counter() - start
            expected = (0, count) if replay else (count, 0)
            assert (result["accepted"], result["duplicates"]) == expected
            assert result["rejected"] == 0
            print(f"{count:,} rows, replay={replay}: {elapsed:.3f} s")
    finally:
        engine.dispose()


def test_future_outlier_is_a_record_rejection(client):
    result = upload(client, HEADER + ROW.replace(b"2026", b"9998")).json()
    assert result["accepted"] == 0
    assert "future" in result["errors"][0]["reason"]


def test_concurrent_sqlite_uploads_share_unique_identity(tmp_path):
    from concurrent.futures import ThreadPoolExecutor

    engine = build_engine(f"sqlite:///{tmp_path / 'concurrent.db'}")
    upgrade_schema(engine)

    def ingest():
        with Session(engine) as session, session.begin():
            result = import_csv_bytes(session, HEADER + ROW)
            return result["accepted"], result["duplicates"]

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: ingest(), range(2)))
        assert sorted(results) == [(0, 1), (1, 0)]
    finally:
        engine.dispose()
