"""Keep subsecond UTC instants distinct on MySQL."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import DATETIME

revision = "0006_mysql_precision"
down_revision = "0005_raw_snapshots"


def set_precision(precision):
    db = op.get_bind()
    if db.dialect.name != "mysql":
        return
    foreign_key = next(
        key for key in sa.inspect(db).get_foreign_keys("observation_provenance")
        if key["referred_table"] == "observations"
    )
    op.drop_constraint(foreign_key["name"], "observation_provenance", type_="foreignkey")
    for table in ("observations", "observation_provenance"):
        op.alter_column(table, "timestamp_utc", existing_type=sa.DateTime(),
                        type_=DATETIME(fsp=precision), existing_nullable=False)
    op.create_foreign_key("fk_provenance_observation", "observation_provenance", "observations",
                          ["participant_id", "timestamp_utc"], ["participant_id", "timestamp_utc"],
                          ondelete="CASCADE")


def upgrade():
    set_precision(6)


def downgrade():
    if op.get_bind().dialect.name == "mysql":
        raise RuntimeError("Downgrading timestamp precision could collapse distinct observations.")
