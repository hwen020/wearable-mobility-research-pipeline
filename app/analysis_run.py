"""Record deterministic daily metrics for one synthetic participant."""
import argparse
import hashlib
import json
import os
from datetime import date
from zoneinfo import ZoneInfo

from sqlalchemy import select

from .analytics import ALGORITHM_VERSION, analysis_parameters, day_bounds_utc, daily_summary, serial_time
from .sampling import SamplingPolicy
from .db import SessionLocal, upgrade_schema
from .models import AnalysisRun, Observation, Participant
from .pipeline import SCHEMA_VERSION


def record_daily_run(session, participant_id, study_day, zone, *, sampling=None):
    if not session.get(Participant, participant_id):
        raise ValueError("Unknown participant")
    stmt = select(Observation).where(Observation.participant_id == participant_id)
    if study_day:
        start, end = day_bounds_utc(study_day, zone)
        stmt = stmt.where(Observation.timestamp_utc >= start, Observation.timestamp_utc < end)
    points = session.scalars(stmt.order_by(Observation.timestamp_utc)).all()
    digest = hashlib.sha256()
    for point in points:
        fields = [point.participant_id, serial_time(point.timestamp_utc), point.latitude,
                  point.longitude, point.steps, point.heart_rate_bpm, point.source]
        digest.update((json.dumps(fields, separators=(",", ":")) + "\n").encode())
    run = AnalysisRun(
        participant_id=participant_id, study_date=study_day, study_timezone=zone.key,
        input_sha256=digest.hexdigest(), schema_version=SCHEMA_VERSION,
        algorithm_version=ALGORITHM_VERSION, parameters=analysis_parameters(sampling),
        result=daily_summary(points, zone, sampling=sampling, only_day=study_day),
    )
    session.add(run)
    session.flush()
    return run


def serialize_run(run):
    return {"id": run.id, "participant_id": run.participant_id,
            "study_date": run.study_date.isoformat() if run.study_date else None,
            "study_timezone": run.study_timezone, "created_at": run.created_at.isoformat(),
            "schema_version": run.schema_version, "algorithm_version": run.algorithm_version,
            "parameters": run.parameters, "input_sha256": run.input_sha256, "daily_metrics": run.result}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("participant")
    filters = parser.add_mutually_exclusive_group()
    filters.add_argument("--date", type=date.fromisoformat)
    filters.add_argument("--list", action="store_true")
    args = parser.parse_args()
    upgrade_schema()
    with SessionLocal.begin() as session:
        if args.list:
            runs = session.scalars(select(AnalysisRun).where(AnalysisRun.participant_id == args.participant)
                                   .order_by(AnalysisRun.id.desc()).limit(20))
            output = [serialize_run(run) for run in runs]
        else:
            try:
                zone = ZoneInfo(os.getenv("STUDY_TIMEZONE", "UTC"))
                output = serialize_run(record_daily_run(session, args.participant, args.date, zone,
                                                        sampling=SamplingPolicy.from_environment()))
            except (ValueError, OverflowError) as exc:
                parser.error(str(exc))
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
