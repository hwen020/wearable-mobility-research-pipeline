"""Minimal research schema, with pseudonymous IDs and no names/PII."""
from datetime import date, datetime, timezone
from sqlalchemy import (
    Date, DateTime, Float, ForeignKey, ForeignKeyConstraint, Integer, JSON, String,
    UniqueConstraint, Index,
)
from sqlalchemy.dialects.mysql import DATETIME as MySQLDateTime
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base


UTC_INSTANT = DateTime(timezone=True).with_variant(MySQLDateTime(fsp=6), "mysql")


class Participant(Base):
    __tablename__ = "participants"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Observation(Base):
    __tablename__ = "observations"
    __table_args__ = (
        UniqueConstraint("participant_id", "timestamp_utc", name="uq_participant_timestamp"),
        Index("idx_observation_time", "timestamp_utc"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    participant_id: Mapped[str] = mapped_column(String(32), ForeignKey("participants.id", ondelete="CASCADE"), index=True)
    timestamp_utc: Mapped[datetime] = mapped_column(UTC_INSTANT, nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    steps: Mapped[int] = mapped_column(Integer, default=0)
    heart_rate_bpm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="synthetic")


class ImportBatch(Base):
    __tablename__ = "import_batches"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(String(160), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    accepted: Mapped[int] = mapped_column(Integer, default=0)
    duplicates: Mapped[int] = mapped_column(Integer, default=0)
    rejected: Mapped[int] = mapped_column(Integer, default=0)
    sha256: Mapped[str | None] = mapped_column(String(64))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    source: Mapped[str | None] = mapped_column(String(32))
    schema_version: Mapped[str | None] = mapped_column(String(16))


class ImportDiagnostic(Base):
    __tablename__ = "import_diagnostics"
    batch_id: Mapped[int] = mapped_column(ForeignKey("import_batches.id", ondelete="CASCADE"), primary_key=True)
    row_number: Mapped[int] = mapped_column(Integer, primary_key=True)
    reason: Mapped[str] = mapped_column(String(200))
    outcome: Mapped[str] = mapped_column(String(12), server_default="rejected")


class DemoIdentity(Base):
    __tablename__ = "demo_identity"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)


DEFAULT_STUDY_ID = "SYN-STUDY"


class Study(Base):
    __tablename__ = "studies"
    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    label: Mapped[str] = mapped_column(String(100))


class StudyParticipant(Base):
    __tablename__ = "study_participants"
    participant_id: Mapped[str] = mapped_column(
        ForeignKey("participants.id", ondelete="CASCADE"), primary_key=True
    )
    study_id: Mapped[str] = mapped_column(ForeignKey("studies.id"))


class Device(Base):
    """A synthetic source association for a participant."""
    __tablename__ = "devices"
    participant_id: Mapped[str] = mapped_column(
        ForeignKey("participants.id", ondelete="CASCADE"), primary_key=True
    )
    source: Mapped[str] = mapped_column(String(32), primary_key=True)


class ObservationProvenance(Base):
    __tablename__ = "observation_provenance"
    __table_args__ = (
        ForeignKeyConstraint(["participant_id", "timestamp_utc"],
                             ["observations.participant_id", "observations.timestamp_utc"],
                             ondelete="CASCADE"),
        UniqueConstraint("batch_id", "row_number", name="uq_provenance_batch_row"),
    )
    participant_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    timestamp_utc: Mapped[datetime] = mapped_column(UTC_INSTANT, primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("import_batches.id", ondelete="CASCADE"))
    row_number: Mapped[int] = mapped_column(Integer)
    raw_fields: Mapped[dict | None] = mapped_column(JSON)


class AnalysisRun(Base):
    __tablename__ = "analysis_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    participant_id: Mapped[str] = mapped_column(ForeignKey("participants.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    study_date: Mapped[date | None] = mapped_column(Date)
    study_timezone: Mapped[str] = mapped_column(String(64))
    schema_version: Mapped[str] = mapped_column(String(16))
    algorithm_version: Mapped[str] = mapped_column(String(16))
    input_sha256: Mapped[str] = mapped_column(String(64))
    parameters: Mapped[dict] = mapped_column(JSON)
    result: Mapped[list] = mapped_column(JSON)
