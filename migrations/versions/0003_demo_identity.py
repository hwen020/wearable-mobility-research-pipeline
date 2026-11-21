from alembic import op
import sqlalchemy as sa

revision = "0003_demo_identity"
down_revision = "0002_import_audit"


def upgrade():
    op.create_table("demo_identity", sa.Column("id", sa.String(32), primary_key=True))


def downgrade():
    op.drop_table("demo_identity")
