"""Keep validated original field text and distinguish duplicate diagnostics."""
from alembic import op
import sqlalchemy as sa

revision = "0005_raw_snapshots"
down_revision = "0004_research_records"


def upgrade():
    op.add_column("observation_provenance", sa.Column("raw_fields", sa.JSON))
    op.add_column("import_diagnostics", sa.Column(
        "outcome", sa.String(12), nullable=False, server_default="rejected"
    ))


def downgrade():
    op.drop_column("import_diagnostics", "outcome")
    op.drop_column("observation_provenance", "raw_fields")
