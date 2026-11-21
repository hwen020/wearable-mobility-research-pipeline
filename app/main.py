"""Read-only research portal plus gated synthetic CSV import."""
import csv
import io
import json
import os
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from typing import Literal
from pathlib import Path
from time import sleep
from zoneinfo import ZoneInfo
from fastapi import FastAPI, HTTPException, UploadFile, File, Query, Request
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import sessionmaker
from . import VERSION
from .sampling import SamplingPolicy
from .db import upgrade_schema, engine as default_engine
from .demo_restore import demo_marked, restore_demo
from .models import Participant, Observation, ImportBatch, ImportDiagnostic
from .pipeline import import_csv_stream, UploadSizeError, ValidationError, SCHEMA_VERSION
from .analytics import (
    ALGORITHM_VERSION, analysis_parameters, day_bounds_utc, daily_summary, geojson_features,
    stays, edge_quality, quality_distance, serial_time, study_date,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def create_app(db_engine=None):
    db_engine = db_engine or default_engine
    zone = ZoneInfo(os.getenv("STUDY_TIMEZONE", "UTC"))
    sampling = SamplingPolicy.from_environment()
    public_read_only = os.getenv("DEMO_PUBLIC_READONLY", "").strip().lower() == "true"
    read_only = public_read_only or os.getenv("DEMO_READ_ONLY") == "1"
    allow_demo_restore = not read_only and db_engine.dialect.name == "sqlite" and os.getenv("DEMO_RESET_ENABLED") == "1"
    sessions = sessionmaker(bind=db_engine, expire_on_commit=False)

    @asynccontextmanager
    async def lifespan(app):
        upgrade_schema(db_engine)
        yield

    app = FastAPI(title="Wearable Mobility Research Pipeline", version=VERSION, lifespan=lifespan,
                  description="Synthetic-only research demo. No Fitbit OAuth or real patient data.")
    if public_read_only:
        @app.middleware("http")
        async def block_public_writes(request: Request, call_next):
            if request.method not in {"GET", "HEAD", "OPTIONS"}:
                return JSONResponse({"detail": "The public demo is read-only"}, status_code=403)
            return await call_next(request)

    app.mount("/static", StaticFiles(directory=str(PROJECT_ROOT / "static")), name="static")

    def get_points(session, pid=None, on_date=None, limit=None, offset=0):
        stmt = select(Observation).order_by(Observation.participant_id, Observation.timestamp_utc)
        if pid:
            stmt = stmt.where(Observation.participant_id == pid)
        if on_date:
            try:
                start, end = day_bounds_utc(on_date, zone)
            except (ValueError, OverflowError) as exc:
                raise HTTPException(422, "Study date is outside the supported range") from exc
            stmt = stmt.where(Observation.timestamp_utc >= start, Observation.timestamp_utc < end)
        if offset:
            stmt = stmt.offset(offset)
        if limit is not None:
            stmt = stmt.limit(limit)
        return session.scalars(stmt).all()

    def check_pid(session, pid):
        if not session.get(Participant, pid):
            raise HTTPException(404, "Unknown participant")

    @app.get("/")
    def home():
        return FileResponse(PROJECT_ROOT / "static" / "index.html")

    def local_request(request):
        peers = {"127.0.0.1", "::1"}
        hosts = peers | {"localhost"}
        return request.client and request.client.host in peers and request.url.hostname in hosts

    @app.get("/api/health")
    def health(request: Request):
        can_restore = False
        if allow_demo_restore and local_request(request):
            with sessions() as session:
                can_restore = demo_marked(session)
        return {"status":"ok", "version":VERSION, "data_policy":"SYNTHETIC_ONLY", "database":"configured", "study_timezone":zone.key, "demo_restore_enabled":can_restore, "read_only":read_only, "public_read_only":public_read_only}

    if allow_demo_restore:
        @app.post("/api/demo/restore")
        def restore(request: Request, confirmation: dict[str, str]):
            if not local_request(request):
                raise HTTPException(403, "Demo restoration requires a local request")
            origin = request.headers.get("origin")
            if origin and origin != str(request.base_url).rstrip("/"):
                raise HTTPException(403, "Demo restoration requires a same-origin request")
            if confirmation.get("confirmation") != "RESTORE SYNTHETIC DEMO":
                raise HTTPException(422, "Explicit demo restoration confirmation is required")
            try:
                with sessions.begin() as session:
                    return restore_demo(session, PROJECT_ROOT / "data" / "synthetic_wearable.csv")
            except ValueError as exc:
                raise HTTPException(409, str(exc)) from exc

    @app.get("/api/summary")
    def summary():
        with sessions() as session:
            points = get_points(session)
            pid = session.scalar(select(func.count(Participant.id))) or 0
            daily = defaultdict(list)
            for p in points:
                daily[(p.participant_id, study_date(p.timestamp_utc, zone))].append(p)
            miles = [quality_distance(ps, zone) for ps in daily.values()]
            study_days = [day for _, day in daily]
            rejected = session.scalar(select(func.sum(ImportBatch.rejected))) or 0
            return {"participants":pid,"observations":len(points),"participant_days":len(daily),
                    "distance_km":round(sum(x[0] for x in miles),2),
                    "speed_outliers":sum(x[1] for x in miles),
                    "total_steps":sum(p.steps for p in points), "rejected_rows": rejected,
                    "first_study_date": min(study_days).isoformat() if study_days else None,
                    "last_study_date": max(study_days).isoformat() if study_days else None,
                    "data_policy":"SYNTHETIC_ONLY"}

    @app.get("/api/participants")
    def participants():
        with sessions() as session:
            points = get_points(session)
            groups = defaultdict(list)
            for p in points:
                groups[p.participant_id].append(p)
            all_ids = session.scalars(select(Participant.id).order_by(Participant.id)).all()
            result = []
            for pid in all_ids:
                ps = groups[pid]
                dailies = daily_summary(ps, zone)
                result.append({"participant_id":pid,"observations":len(ps),"days":len(dailies),
                               "steps":sum(x["steps"] for x in dailies),
                               "distance_km":round(sum(x["distance_km"] for x in dailies),2),
                               "dates":[x["date"] for x in (daily_summary(ps, zone, sampling=sampling) if sampling else dailies)]})
            return result

    @app.get("/api/participants/{pid}/daily")
    def participant_daily(pid: str):
        with sessions() as session:
            check_pid(session,pid)
            return daily_summary(get_points(session,pid), zone, sampling=sampling)

    def research_metadata(pid, date_filter):
        return {
            "schema_version": SCHEMA_VERSION,
            "algorithm_version": ALGORITHM_VERSION,
            "crs": "EPSG:4326",
            "units": {"latitude": "degrees", "longitude": "degrees", "distance": "km",
                      "area": "km2", "duration": "minutes", "heart_rate": "bpm", "steps": "count"},
            "data_source": "synthetic-only SQLite/MySQL observation store",
            "synthetic": True,
            "study_timezone": zone.key,
            "participant_id": pid,
            "study_date": date_filter.isoformat() if date_filter else None,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "algorithms": ["screened_haversine_segments", "anchor_radius", "projected_buffer_convex_hull"],
            "parameters": analysis_parameters(sampling),
        }

    @app.get("/api/participants/{pid}/geojson")
    def participant_geojson(
        pid: str, date_filter: date | None = Query(default=None, alias="date"),
        layer: Literal["route", "stay", "activity_area"] | None = None,
        download: bool = False, metadata_only: bool = False,
    ):
        with sessions() as session:
            check_pid(session, pid)
            metadata = research_metadata(pid, date_filter)
            if metadata_only:
                return JSONResponse(metadata, headers={
                    "Content-Disposition": f'attachment; filename="{pid}_analysis.json"'
                })
            points = get_points(session, pid, date_filter)
            output = geojson_features(points, zone=zone, include_area=layer in (None, "activity_area"))
            if layer:
                output["features"] = [f for f in output["features"] if f["properties"]["kind"] == layer]
            output["metadata"] = metadata
            if download:
                return JSONResponse(output, media_type="application/geo+json", headers={
                    "Content-Disposition": f'attachment; filename="{pid}_{layer or "mobility"}.geojson"'
                })
            return output

    @app.get("/api/participants/{pid}/stays")
    def participant_stays(pid: str, date_filter: date | None = Query(default=None, alias="date")):
        with sessions() as session:
            check_pid(session,pid)
            return stays(get_points(session,pid,date_filter), zone=zone)

    @app.get("/api/participants/{pid}/observations")
    def observations(
        pid: str, date_filter: date | None = Query(default=None, alias="date"),
        limit: int = Query(default=250, ge=1, le=2000), include_quality: bool = False,
        offset: int = Query(default=0, ge=0, le=10_000_000),
    ):
        with sessions() as session:
            check_pid(session, pid)
            previous_for_page = 1 if offset and include_quality else 0
            points = get_points(session, pid, date_filter, limit + previous_for_page,
                                offset - previous_for_page)
            result = [{"timestamp_utc": serial_time(p.timestamp_utc), "latitude": p.latitude,
                       "longitude": p.longitude, "steps": p.steps, "heart_rate_bpm": p.heart_rate_bpm}
                      for p in points]
            if include_quality:
                for i, row in enumerate(result):
                    flag = edge_quality(points[i - 1], points[i], zone)[1] if i else None
                    row["quality_flags"] = [flag] if flag and flag != "day_boundary" else []
                    row["incoming_segment_excluded"] = flag in {
                        "day_boundary", "nonpositive_interval", "sampling_gap", "speed_outlier"
                    }
            return result[previous_for_page:]

    @app.get("/api/participants/{pid}/export.csv")
    def export_csv(
        pid: str, date_filter: date | None = Query(default=None, alias="date"),
        dataset: Literal["observations", "daily"] = "observations",
    ):
        with sessions() as session:
            check_pid(session,pid)
            points = get_points(session,pid,date_filter)
            output=io.StringIO()
            writer=csv.writer(output)
            if dataset == "daily":
                fields = ["date", "samples", "steps", "distance_km", "avg_heart_rate_bpm",
                          "speed_outliers", "sampling_gaps", "repeated_coordinates", "screened_gps_ratio",
                          "algorithm_version", "observed_validity_rate", "expected_sampling_coverage",
                          "occupied_sampling_slots", "expected_sampling_slots"]
                daily_writer = csv.DictWriter(output, fieldnames=fields)
                daily_writer.writeheader()
                daily_writer.writerows(daily_summary(points, zone, sampling=sampling, only_day=date_filter))
            else:
                writer.writerow(["participant_id","timestamp_utc","latitude","longitude","steps","heart_rate_bpm","source"])
                for p in points:
                    writer.writerow([p.participant_id, serial_time(p.timestamp_utc), p.latitude, p.longitude,
                                     p.steps, p.heart_rate_bpm, p.source])
            return StreamingResponse(iter([output.getvalue()]), media_type="text/csv; charset=utf-8",
                headers={"Content-Disposition": f'attachment; filename="{pid}_{dataset}.csv"',
                         "X-Research-Metadata": json.dumps(research_metadata(pid, date_filter))})

    @app.post("/api/import", include_in_schema=not public_read_only)
    def import_file(file: UploadFile = File(...)):
        if read_only:
            raise HTTPException(403, "CSV import is disabled in the read-only demo")
        if not (file.filename or "").lower().endswith(".csv"):
            raise HTTPException(415,"Only .csv files are accepted")
        max_bytes = int(os.environ.get("MAX_UPLOAD_BYTES", "5242880"))
        for attempt in range(3):
            file.file.seek(0)
            try:
                with sessions.begin() as session:
                    return import_csv_stream(session, file.file, file.filename or "upload.csv",
                                             max_bytes=max_bytes)
            except UploadSizeError as exc:
                raise HTTPException(413, str(exc)) from exc
            except ValidationError as exc:
                raise HTTPException(422, str(exc)) from exc
            except (IntegrityError, OperationalError) as exc:
                if db_engine.dialect.name == "mysql":
                    retryable = bool(exc.orig.args) and exc.orig.args[0] in {1062, 1205, 1213}
                else:
                    retryable = getattr(exc.orig, "sqlite_errorname", "").startswith(
                        ("SQLITE_BUSY", "SQLITE_LOCKED")
                    )
                if not retryable:
                    raise
                if attempt == 2:
                    raise HTTPException(409, "Import conflicts with another write; retry the upload") from exc
                sleep(0.05 * (attempt + 1))

    @app.get("/api/imports")
    def imports(batch_id: int | None = Query(default=None, ge=1),
                outcome: Literal["rejected", "duplicate"] = "rejected",
                reason: str | None = Query(default=None, max_length=200),
                offset: int = Query(default=0, ge=0),
                limit: int = Query(default=100, ge=1, le=500)):
        with sessions() as session:
            if batch_id is not None:
                if session.get(ImportBatch, batch_id) is None:
                    raise HTTPException(404, "Unknown import batch")
                batch_outcome = (ImportDiagnostic.batch_id == batch_id, ImportDiagnostic.outcome == outcome)
                stmt = select(ImportDiagnostic).where(*batch_outcome)
                if reason:
                    stmt = stmt.where(ImportDiagnostic.reason == reason)
                count = session.scalar(select(func.count()).select_from(stmt.subquery()))
                page = session.scalars(stmt.order_by(ImportDiagnostic.row_number).offset(offset).limit(limit))
                categories = session.execute(
                    select(ImportDiagnostic.reason, func.count()).where(*batch_outcome)
                    .group_by(ImportDiagnostic.reason).order_by(ImportDiagnostic.reason)
                ).all()
                return {"total": count, "offset": offset, "limit": limit,
                        "categories": [{"reason": category, "count": n} for category, n in categories],
                        "records": [{"row": item.row_number, "reason": item.reason} for item in page]}
            batches = session.scalars(select(ImportBatch).order_by(ImportBatch.id.desc()).limit(20)).all()
            return [{"id":b.id,"filename":b.filename,"created_at":b.created_at.isoformat(),
                     "accepted":b.accepted,"duplicates":b.duplicates,"rejected":b.rejected,
                     "sha256":b.sha256,"duration_ms":b.duration_ms,"source":b.source,
                     "schema_version":b.schema_version,
                     "total_rows":b.accepted + b.duplicates + b.rejected} for b in batches]

    return app


app = create_app()
