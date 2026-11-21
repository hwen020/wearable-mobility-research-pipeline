import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool
from app.db import Base
from app.main import create_app


@pytest.fixture
def client():
    engine = create_engine("sqlite://", connect_args={"check_same_thread":False}, poolclass=StaticPool)
    @event.listens_for(engine, "connect")
    def enforce_foreign_keys(conn, _):
        conn.execute("PRAGMA foreign_keys=ON")
    app = create_app(engine)
    with TestClient(app) as c:
        yield c
    engine.dispose()
