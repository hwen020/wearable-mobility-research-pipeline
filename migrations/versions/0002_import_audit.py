"""Add import provenance and row diagnostics."""
from alembic import op
import sqlalchemy as sa

revision = "0002_import_audit"
down_revision = "0001_baseline"


def upgrade():
    op.add_column("import_batches", sa.Column("sha256", sa.String(64)))
    op.add_column("import_batches", sa.Column("duration_ms", sa.Integer))
    op.add_column("import_batches", sa.Column("source", sa.String(32)))
    op.add_column("import_batches", sa.Column("schema_version", sa.String(16)))
    op.create_table(
        "import_diagnostics",
        sa.Column("batch_id", sa.Integer, sa.ForeignKey("import_batches.id", ondelete="CASCADE"),
                  primary_key=True),
        sa.Column("row_number", sa.Integer, primary_key=True),
        sa.Column("reason", sa.String(200), nullable=False),
    )


def downgrade():
    op.drop_table("import_diagnostics")
    for column in ("schema_version", "source", "duration_ms", "sha256"):
        op.drop_column("import_batches", column)
