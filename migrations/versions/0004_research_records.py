"""Register a single synthetic study, devices and reproducible analysis runs."""
from alembic import op
import sqlalchemy as sa

revision = "0004_research_records"
down_revision = "0003_demo_identity"
DEFAULT_STUDY = "SYN-STUDY"


def upgrade():
    study = op.create_table(
        "studies",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("label", sa.String(100), nullable=False),
    )
    op.bulk_insert(study, [{"id": DEFAULT_STUDY, "label": "Synthetic mobility demonstration"}])
    op.create_table(
        "study_participants",
        sa.Column("participant_id", sa.String(32),
                  sa.ForeignKey("participants.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("study_id", sa.String(32), sa.ForeignKey("studies.id"), nullable=False),
    )
    op.create_table(
        "devices",
        sa.Column("participant_id", sa.String(32),
                  sa.ForeignKey("participants.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("source", sa.String(32), primary_key=True),
    )
    op.create_table(
        "observation_provenance",
        sa.Column("participant_id", sa.String(32), primary_key=True),
        sa.Column("timestamp_utc", sa.DateTime(timezone=True), primary_key=True),
        sa.Column("batch_id", sa.Integer, sa.ForeignKey("import_batches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("row_number", sa.Integer, nullable=False),
        sa.ForeignKeyConstraint(
            ["participant_id", "timestamp_utc"],
            ["observations.participant_id", "observations.timestamp_utc"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint("batch_id", "row_number", name="uq_provenance_batch_row"),
    )
    op.create_table(
        "analysis_runs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("participant_id", sa.String(32),
                  sa.ForeignKey("participants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("study_date", sa.Date),
        sa.Column("study_timezone", sa.String(64), nullable=False),
        sa.Column("schema_version", sa.String(16), nullable=False),
        sa.Column("algorithm_version", sa.String(16), nullable=False),
        sa.Column("input_sha256", sa.String(64), nullable=False),
        sa.Column("parameters", sa.JSON, nullable=False),
        sa.Column("result", sa.JSON, nullable=False),
    )
    op.create_index("ix_analysis_runs_participant_id", "analysis_runs", ["participant_id"])
    db = op.get_bind()
    db.execute(sa.text(
        "INSERT INTO study_participants (participant_id, study_id) SELECT id, :study FROM participants"
    ), {"study": DEFAULT_STUDY})
    db.execute(sa.text(
        "INSERT INTO devices (participant_id, source) SELECT DISTINCT participant_id, lower(source) FROM observations"
    ))


def downgrade():
    for table in ("analysis_runs", "observation_provenance", "devices", "study_participants", "studies"):
        op.drop_table(table)
