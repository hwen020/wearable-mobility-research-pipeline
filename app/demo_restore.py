"""Restore only a SQLite database explicitly initialized for the demo."""
from sqlalchemy import delete, func, select

from .models import (
    AnalysisRun, DemoIdentity, Device, ImportBatch, ImportDiagnostic, Observation,
    ObservationProvenance, Participant, StudyParticipant,
)
from .pipeline import import_csv_stream

DEMO_MARKER = "canonical_synthetic_v01"
SYNTHETIC_SOURCES = ("synthetic", "demo", "simulated")


def demo_marked(session):
    return session.get(DemoIdentity, DEMO_MARKER) is not None


def mark_empty_database(session):
    if demo_marked(session):
        return
    for model in (Observation, Participant, ImportBatch):
        if session.scalar(select(func.count()).select_from(model)):
            raise ValueError("Use an empty SQLite database to opt into demo restoration.")
    session.add(DemoIdentity(id=DEMO_MARKER))


def restore_demo(session, fixture):
    # The marker row is the write lock for concurrent restore requests.
    marker = session.execute(
        DemoIdentity.__table__.update().where(DemoIdentity.id == DEMO_MARKER).values(id=DEMO_MARKER)
    )
    if marker.rowcount != 1:
        raise ValueError("The database has no demo marker.")
    unexpected = select(Observation.id).where(
        func.lower(Observation.source).not_in(SYNTHETIC_SOURCES)
    ).limit(1)
    if session.scalar(unexpected) is not None:
        raise ValueError("Unexpected observation sources prevent restoration.")
    for model in (AnalysisRun, ObservationProvenance, ImportDiagnostic, Observation,
                  Device, StudyParticipant, Participant, ImportBatch):
        session.execute(delete(model))
    with fixture.open("rb") as file:
        result = import_csv_stream(session, file, fixture.name, source="demo_restore")
    if (result["accepted"], result["rejected"], result["duplicates"]) != (366, 0, 0):
        raise ValueError("The canonical demo fixture did not validate.")
    return result
