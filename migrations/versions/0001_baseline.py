"""Register the original schema, preserving databases created by v0.1."""
from alembic import op
import sqlalchemy as sa

revision = "0001_baseline"
down_revision = None


def upgrade():
    tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "participants" not in tables:
        op.create_table(
            "participants",
            sa.Column("id", sa.String(32), primary_key=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        )
    if "observations" not in tables:
        op.create_table(
            "observations",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("participant_id", sa.String(32),
                      sa.ForeignKey("participants.id", ondelete="CASCADE"), nullable=False),
            sa.Column("timestamp_utc", sa.DateTime(timezone=True), nullable=False),
            sa.Column("latitude", sa.Float, nullable=False),
            sa.Column("longitude", sa.Float, nullable=False),
            sa.Column("steps", sa.Integer, nullable=False),
            sa.Column("heart_rate_bpm", sa.Integer),
            sa.Column("source", sa.String(32), nullable=False),
            sa.UniqueConstraint("participant_id", "timestamp_utc", name="uq_participant_timestamp"),
        )
        op.create_index("ix_observations_participant_id", "observations", ["participant_id"])
        op.create_index("idx_observation_time", "observations", ["timestamp_utc"])
    if "import_batches" not in tables:
        op.create_table(
            "import_batches",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("filename", sa.String(160), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("accepted", sa.Integer, nullable=False),
            sa.Column("duplicates", sa.Integer, nullable=False),
            sa.Column("rejected", sa.Integer, nullable=False),
        )


def downgrade():
    raise RuntimeError("Removing the original demo tables would destroy historical data.")
