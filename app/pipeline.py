"""CSV validation and reproducible ingestion, without real-person identifiers."""
import csv
import hashlib
import io
import math
import re
from datetime import datetime, timedelta, timezone
from pathlib import PureWindowsPath
from time import perf_counter
from typing import BinaryIO
from sqlalchemy import insert, select, tuple_
from sqlalchemy.orm import Session
from .models import (
    DEFAULT_STUDY_ID, Device, ImportBatch, ImportDiagnostic, Observation, ObservationProvenance,
    Participant, StudyParticipant,
)

REQUIRED = {"participant_id", "timestamp_utc", "latitude", "longitude", "steps"}
PARTICIPANT_PATTERN = re.compile(r"^[A-Za-z0-9_-]{3,32}$")
MAX_ROWS = 50000
CHUNK_SIZE = 400
SCHEMA_VERSION = "1"
MAX_FUTURE_DAYS = 366
OPTIONAL = {"heart_rate_bpm", "source"}


class ValidationError(ValueError):
    pass


def parse_row(row: dict, row_number: int, *, latest_timestamp=None) -> dict:
    try:
        participant_id = (row.get("participant_id") or "").strip()
        if not PARTICIPANT_PATTERN.fullmatch(participant_id):
            raise ValidationError("participant_id must be 3–32 alphanumeric, underscore or dash characters")
        raw_time = (row.get("timestamp_utc") or "").strip()
        if not raw_time:
            raise ValidationError("timestamp_utc is required")
        try:
            timestamp = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValidationError("timestamp_utc must be an ISO 8601 datetime") from exc
        if timestamp.tzinfo is None:
            raise ValidationError("timestamp_utc requires a timezone (+00:00 or Z)")
        timestamp = timestamp.astimezone(timezone.utc).replace(tzinfo=None)
        if latest_timestamp is not None and timestamp > latest_timestamp:
            raise ValidationError(f"timestamp_utc is more than {MAX_FUTURE_DAYS} days in the future")
        if not row.get("latitude") or not row.get("longitude"):
            raise ValidationError("latitude and longitude are required")
        try:
            latitude = float(row["latitude"])
            longitude = float(row["longitude"])
        except ValueError as exc:
            raise ValidationError("latitude and longitude must be numeric") from exc
        if not (math.isfinite(latitude) and math.isfinite(longitude)):
            raise ValidationError("coordinates must be finite")
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            raise ValidationError("coordinates outside valid WGS84 range")
        try:
            steps = int(row["steps"])
        except ValueError as exc:
            raise ValidationError("steps must be an integer") from exc
        if not 0 <= steps <= 100000:
            raise ValidationError("steps must be between 0 and 100000")
        raw_hr = (row.get("heart_rate_bpm") or "").strip()
        try:
            heart_rate = int(raw_hr) if raw_hr else None
        except ValueError as exc:
            raise ValidationError("heart_rate_bpm must be an integer") from exc
        if heart_rate is not None and not 30 <= heart_rate <= 240:
            raise ValidationError("heart_rate_bpm outside plausible demo range (30–240)")
        source = (row.get("source") or "synthetic").strip() or "synthetic"
        if source.lower() not in {"synthetic", "demo", "simulated"}:
            raise ValidationError("demo only: source must be synthetic, demo or simulated")
        return dict(participant_id=participant_id, timestamp_utc=timestamp,
                    latitude=latitude, longitude=longitude, steps=steps,
                    heart_rate_bpm=heart_rate, source=source)
    except ValidationError:
        raise
    except (ValueError, KeyError, TypeError, OverflowError) as exc:
        raise ValidationError("one or more fields are missing or out of range") from exc


def import_csv_bytes(session: Session, content: bytes, filename: str = "sample.csv") -> dict:
    return import_csv_stream(session, io.BytesIO(content), filename)


def store_chunk(session, batch, parsed_rows):
    if not parsed_rows:
        return
    keys = [(row["participant_id"], row["timestamp_utc"]) for _, row, _ in parsed_rows]
    existing = set(session.execute(
        select(Observation.participant_id, Observation.timestamp_utc)
        .where(tuple_(Observation.participant_id, Observation.timestamp_utc).in_(keys))
    ))
    pending = []
    provenance = []
    duplicate_rows = []
    for (row_number, row, raw_fields), key in zip(parsed_rows, keys):
        if key in existing:
            batch.duplicates += 1
            duplicate_rows.append({"batch_id": batch.id, "row_number": row_number,
                                   "outcome": "duplicate",
                                   "reason": "participant and UTC timestamp already exist"})
        else:
            pending.append(row)
            provenance.append({"participant_id": key[0], "timestamp_utc": key[1],
                               "batch_id": batch.id, "row_number": row_number, "raw_fields": raw_fields})
            existing.add(key)
    if duplicate_rows:
        session.execute(insert(ImportDiagnostic), duplicate_rows)
    if not pending:
        return
    ids = {row["participant_id"] for row in pending}
    known = set(session.scalars(select(Participant.id).where(Participant.id.in_(ids))))
    if missing := sorted(ids - known):
        session.execute(insert(Participant), [{"id": pid} for pid in missing])
        session.execute(insert(StudyParticipant), [
            {"participant_id": pid, "study_id": DEFAULT_STUDY_ID} for pid in missing
        ])
    sources = {(row["participant_id"], row["source"].lower()) for row in pending}
    existing_sources = set(session.execute(
        select(Device.participant_id, Device.source)
        .where(tuple_(Device.participant_id, Device.source).in_(sources))
    ))
    if new_sources := sorted(sources - existing_sources):
        session.execute(insert(Device), [
            {"participant_id": pid, "source": source} for pid, source in new_sources
        ])
    session.execute(insert(Observation), pending)
    session.execute(insert(ObservationProvenance), provenance)
    batch.accepted += len(pending)


def import_csv_stream(
    session: Session, file: BinaryIO, filename: str, *, source: str = "csv_upload",
    max_bytes: int | None = None,
) -> dict:
    """Read a bounded, seekable upload. The caller owns the database transaction."""
    start = perf_counter()
    checksum = hashlib.sha256()
    size = 0
    while block := file.read(65536):
        size += len(block)
        if max_bytes is not None and size > max_bytes:
            raise UploadSizeError(f"Maximum CSV size is {max_bytes} bytes")
        checksum.update(block)
    file.seek(0)
    stream = io.TextIOWrapper(file, encoding="utf-8-sig", newline="")
    try:
        return read_csv(session, stream, filename, source, checksum.hexdigest(), start)
    except UnicodeDecodeError as exc:
        raise ValidationError("CSV must be UTF-8 encoded") from exc
    except csv.Error as exc:
        raise ValidationError("malformed CSV quoting or oversized field") from exc
    finally:
        stream.detach()


class UploadSizeError(ValidationError):
    pass


def read_csv(session, stream, filename, source, checksum, start):
    reader = csv.DictReader(stream, strict=True)
    if not reader.fieldnames:
        raise ValidationError("empty CSV header")
    reader.fieldnames = [field.strip() for field in reader.fieldnames]
    fields = set(reader.fieldnames)
    if len(fields) != len(reader.fieldnames):
        raise ValidationError("CSV header contains duplicate column names")
    if not REQUIRED.issubset(fields):
        raise ValidationError("missing columns: " + ", ".join(sorted(REQUIRED - fields)))
    if fields - REQUIRED - OPTIONAL:
        raise ValidationError("CSV header contains unsupported columns")

    batch = ImportBatch(filename=PureWindowsPath(filename).name[:160], accepted=0,
                        rejected=0, duplicates=0, source=source, sha256=checksum,
                        schema_version=SCHEMA_VERSION)
    session.add(batch)
    session.flush()
    parsed_rows, diagnostics, errors = [], [], []
    latest_timestamp = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=MAX_FUTURE_DAYS)
    for number, row in enumerate(reader, start=1):
        if number > MAX_ROWS:
            raise ValidationError(f"upload exceeds maximum {MAX_ROWS} rows")
        row_number = number + 1
        try:
            if None in row or any(value is None for value in row.values()):
                raise ValidationError("CSV record does not match the number of columns")
            parsed = parse_row(row, row_number, latest_timestamp=latest_timestamp)
            parsed_rows.append((row_number, parsed, row))
        except ValidationError as exc:
            batch.rejected += 1
            reason = str(exc)
            diagnostics.append(dict(batch_id=batch.id, row_number=row_number, reason=reason))
            if len(errors) < 20:
                errors.append({"row": row_number, "reason": reason})
        if number % CHUNK_SIZE == 0:
            store_chunk(session, batch, parsed_rows)
            if diagnostics:
                session.execute(insert(ImportDiagnostic), diagnostics)
            parsed_rows.clear()
            diagnostics.clear()
    store_chunk(session, batch, parsed_rows)
    if diagnostics:
        session.execute(insert(ImportDiagnostic), diagnostics)
    batch.duration_ms = round((perf_counter() - start) * 1000)
    session.flush()
    return {"import_id": batch.id, "filename": batch.filename,
            "accepted": batch.accepted, "duplicates": batch.duplicates,
            "rejected": batch.rejected, "errors": errors}
