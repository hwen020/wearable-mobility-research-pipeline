"""Relational persistence: SQLite by default; optionally MySQL via DATABASE_URL."""
import os
from contextlib import contextmanager
from pathlib import Path
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


def build_engine(url: str | None = None):
    url = url or os.getenv("DATABASE_URL", "sqlite:///./mobility.db")
    engine = create_engine(url, connect_args={"check_same_thread": False} if url.startswith("sqlite") else {}, pool_pre_ping=True, hide_parameters=True)
    if url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def _enable_fk(conn, _):
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()
    return engine


engine = build_engine()
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def upgrade_schema(target=engine):
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    with target.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, "head")


@contextmanager
def session_scope(factory=SessionLocal):
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
