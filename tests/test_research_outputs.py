import csv
import io
import json
from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlalchemy import create_engine

from app.analytics import activity_area, daily_summary, geojson_features, stays
from app.demo_seed import create_demo_csv
from app.main import create_app
from app.models import Observation


def point(timestamp, latitude=34, longitude=-118):
    return Observation(timestamp_utc=datetime.fromisoformat(timestamp), latitude=latitude,
                       longitude=longitude, steps=5, heart_rate_bpm=80)


def test_routes_and_stays_split_at_study_midnight_and_gaps():
    points = [point(t) for t in ("2026-11-16T23:40", "2026-11-16T23:55",
                                "2026-11-17T00:05", "2026-11-17T04:05")]
    visits = stays(points)
    assert len(visits) == 1 and visits[0]["visit_index"] == 1
    routes = [f for f in geojson_features(points, include_area=False)["features"]
              if f["properties"]["kind"] == "route"]
    assert len(routes) == 1 and len(routes[0]["geometry"]["coordinates"]) == 2
    days = daily_summary(points)
    assert days[0]["repeated_coordinates"] == 1
    assert days[1]["sampling_gaps"] == 1


def test_projected_area_at_equator_and_pole():
    for latitude in (0, 90):
        feature = activity_area([point("2026-11-16T23:40", latitude, 0)])
        assert feature["properties"]["area_km2"] == 0.031
        assert feature["properties"]["crs"] == "EPSG:4326"
        assert feature["geometry"]["type"] == "Polygon"


def test_study_date_filters_share_fall_back_window(monkeypatch):
    monkeypatch.setenv("STUDY_TIMEZONE", "America/Los_Angeles")
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    try:
        with TestClient(create_app(engine)) as client:
            data = ["participant_id,timestamp_utc,latitude,longitude,steps"]
            for stamp in ("2026-11-01T06:59:00Z", "2026-11-01T07:00:00Z", "2026-11-01T01:30:00-07:00",
                          "2026-11-01T01:30:00-08:00", "2026-11-02T07:59:00Z", "2026-11-02T08:00:00Z"):
                data.append(f"SYN-DST,{stamp},34,-118,5")
            response = client.post("/api/import", files={"file": ("dst.csv", "\n".join(data))})
            assert response.json()["accepted"] == 6
            base = "/api/participants/SYN-DST"
            assert [row["samples"] for row in client.get(base + "/daily").json()] == [1, 4, 1]
            assert len(client.get(base + "/observations?date=2026-11-01").json()) == 4
            assert client.get("/api/health").json()["study_timezone"] == "America/Los_Angeles"
    finally:
        engine.dispose()


def test_filtered_exports_and_metadata(client, tmp_path):
    data = create_demo_csv(tmp_path / "sample.csv").read_bytes()
    assert client.post("/api/import", files={"file": ("sample.csv", data)}).json()["accepted"] == 366
    base = "/api/participants/SYN-P001"
    date = "2026-11-16"
    csv_response = client.get(f"{base}/export.csv?dataset=daily&date={date}")
    records = list(csv.DictReader(io.StringIO(csv_response.text)))
    assert records[0]["date"] == date and records[0]["samples"] == "61" and len(records) == 1
    metadata = json.loads(csv_response.headers["x-research-metadata"])
    assert metadata["synthetic"] and metadata["crs"] == "EPSG:4326"
    for layer in ("route", "stay", "activity_area"):
        response = client.get(f"{base}/geojson?date={date}&layer={layer}&download=true")
        assert response.headers["content-type"] == "application/geo+json"
        assert {f["properties"]["kind"] for f in response.json()["features"]} == {layer}
    manifest = client.get(f"{base}/geojson?date={date}&metadata_only=true").json()
    assert manifest["parameters"] == metadata["parameters"]
    assert manifest["study_date"] == date


def test_import_diagnostics_page_and_filter(client):
    data = ("participant_id,timestamp_utc,latitude,longitude,steps\n"
            "SYN-P001,2026-11-16T00:00:00Z,inf,-118,2\n"
            "SYN-P001,2026-11-16T00:05:00Z,34,-118,-1\n")
    batch = client.post("/api/import", files={"file": ("bad.csv", data)}).json()["import_id"]
    response = client.get("/api/imports", params={"batch_id": batch, "limit": 1, "offset": 1}).json()
    assert response["total"] == 2 and response["records"][0]["row"] == 3
    filtered = client.get("/api/imports", params={"batch_id": batch, "reason": "coordinates must be finite"}).json()
    assert filtered["total"] == 1 and filtered["records"][0]["row"] == 2
    duplicate_data = ("participant_id,timestamp_utc,latitude,longitude,steps\n"
                      "SYN-DUP,2026-11-16T01:00:00Z,34,-118,2\n") + "SYN-DUP,2026-11-16T01:00:00Z,34,-118,2\n"
    dup = client.post("/api/import", files={"file": ("duplicate.csv", duplicate_data)}).json()
    assert (dup["accepted"], dup["duplicates"], dup["rejected"]) == (1, 1, 0)
    details = client.get("/api/imports", params={"batch_id": dup["import_id"], "outcome": "duplicate"}).json()
    assert details["total"] == 1 and details["records"][0]["row"] == 3


def test_restore_requires_enablement_marker_confirmation_and_loopback(monkeypatch, tmp_path):
    from sqlalchemy.orm import Session
    from app.db import build_engine, upgrade_schema
    from app.demo_restore import mark_empty_database

    monkeypatch.setenv("DEMO_RESET_ENABLED", "1")
    engine = build_engine(f"sqlite:///{tmp_path / 'restore.db'}")
    content = {"confirmation": "RESTORE SYNTHETIC DEMO"}
    path = "/api/demo/restore"
    try:
        upgrade_schema(engine)
        app = create_app(engine)
        with TestClient(app, base_url="http://localhost", client=("127.0.0.1", 50000)) as client:
            assert client.post(path, json=content).status_code == 409
            with Session(engine) as session, session.begin():
                mark_empty_database(session)
            assert client.get("/api/health").json()["demo_restore_enabled"]
            assert client.post(path, json={}).status_code == 422
            assert client.post(path, json=content, headers={"Origin": "https://example.invalid"}).status_code == 403
            extra = b"participant_id,timestamp_utc,latitude,longitude,steps\nSYN-EXTRA,2026-11-16T00:00:00Z,34,-118,2\n"
            assert client.post("/api/import", files={"file": ("extra.csv", extra)}).json()["accepted"] == 1
            assert client.post(path, json=content).json()["accepted"] == 366
            summary = client.get("/api/summary").json()
            assert (summary["participants"], summary["observations"]) == (3, 366)
        with TestClient(app, client=("192.0.2.1", 50000), base_url="http://localhost") as remote:
            assert remote.post(path, json=content).status_code == 403
        monkeypatch.delenv("DEMO_RESET_ENABLED")
        with TestClient(create_app(engine)) as disabled:
            assert disabled.post(path, json=content).status_code == 404
    finally:
        engine.dispose()


def test_provenance_and_repeatable_analysis(tmp_path):
    from zoneinfo import ZoneInfo
    from sqlalchemy import func, select
    from sqlalchemy.orm import Session
    from app.analysis_run import record_daily_run
    from app.db import build_engine, upgrade_schema
    from app.models import AnalysisRun, Device, ObservationProvenance, StudyParticipant
    from app.pipeline import import_csv_stream

    engine = build_engine(f"sqlite:///{tmp_path / 'runs.db'}")
    try:
        upgrade_schema(engine)
        sample = create_demo_csv(tmp_path / "run_source.csv")
        for _ in range(2):
            with Session(engine) as session, session.begin(), sample.open("rb") as source:
                import_csv_stream(session, source, sample.name)
        with Session(engine) as session, session.begin():
            assert session.scalar(select(func.count()).select_from(StudyParticipant)) == 3
            assert session.scalar(select(func.count()).select_from(Device)) == 3
            assert session.scalar(select(func.count()).select_from(ObservationProvenance)) == 366
            provenance = session.scalars(select(ObservationProvenance)
                                         .order_by(ObservationProvenance.row_number)).first()
            assert (provenance.batch_id, provenance.row_number) == (1, 2)
            assert provenance.raw_fields["timestamp_utc"].endswith("Z")
            assert isinstance(provenance.raw_fields["steps"], str)
            first = record_daily_run(session, "SYN-P001", None, ZoneInfo("UTC"))
            second = record_daily_run(session, "SYN-P001", None, ZoneInfo("UTC"))
            assert first.id != second.id
            assert first.input_sha256 == second.input_sha256
            assert first.result == second.result and len(first.result) == 2
        with Session(engine) as session:
            assert session.scalar(select(func.count()).select_from(AnalysisRun)) == 2
    finally:
        engine.dispose()


def test_optional_observation_quality_flags(client):
    data = ("participant_id,timestamp_utc,latitude,longitude,steps\n"
            "SYN-P001,2026-11-16T00:00:00Z,34,-118,0\n"
            "SYN-P001,2026-11-16T00:05:00Z,36,-118,0\n"
            "SYN-P001,2026-11-16T00:10:00Z,36,-118,0\n"
            "SYN-P001,2026-11-16T04:00:00Z,36,-118,0\n")
    assert client.post("/api/import", files={"file": ("edges.csv", data)}).json()["accepted"] == 4
    path = "/api/participants/SYN-P001/observations"
    assert "quality_flags" not in client.get(path).json()[0]
    points = client.get(path, params={"include_quality": True}).json()
    assert [p["quality_flags"] for p in points] == [
        [], ["speed_outlier"], ["repeated_coordinate"], ["sampling_gap"]
    ]
    assert [p["incoming_segment_excluded"] for p in points] == [False, True, False, True]
    page = client.get(path, params={"include_quality": True, "offset": 1, "limit": 1}).json()
    assert page == [points[1]]


def test_distributed_trace_reports_unavailable_local_area():
    trace = [point("2026-11-16T12:00", 0, 0), point("2026-11-16T12:05", 0, 179)]
    collection = geojson_features(trace)
    assert collection["warnings"]
    assert "activity_area" not in {feature["properties"]["kind"] for feature in collection["features"]}


def test_mock_adapter_uses_the_same_utc_validation_and_deduplication(tmp_path):
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from app.db import build_engine, upgrade_schema
    from app.models import ImportBatch
    from app.wearable_adapter import MockFitbitAdapter, import_wearable

    engine = build_engine(f"sqlite:///{tmp_path / 'wearable.db'}")
    try:
        upgrade_schema(engine)
        for expected in ((2, 0), (0, 2)):
            with Session(engine) as session, session.begin():
                result = import_wearable(session, MockFitbitAdapter())
                assert (result["accepted"], result["duplicates"]) == expected
        with Session(engine) as session:
            points = session.scalars(select(Observation).order_by(Observation.timestamp_utc)).all()
            assert [(p.timestamp_utc.hour, p.steps, p.heart_rate_bpm) for p in points] == [(17, 12, 74), (17, 26, 82)]
            assert set(session.scalars(select(ImportBatch.source))) == {"mock_fitbit"}
    finally:
        engine.dispose()
