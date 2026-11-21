from fastapi.testclient import TestClient

from app.db import build_engine
from app.main import create_app


def test_public_demo_blocks_all_mutating_requests_before_parsing(monkeypatch, tmp_path):
    monkeypatch.setenv("DEMO_PUBLIC_READONLY", "true")
    monkeypatch.setenv("DEMO_RESET_ENABLED", "1")
    engine = build_engine(f"sqlite:///{tmp_path / 'public.db'}")
    app = create_app(engine)

    @app.patch("/api/future-write")
    def future_write():
        raise AssertionError("Public middleware allowed a future mutating endpoint")

    try:
        with TestClient(app) as client:
            health = client.get("/api/health").json()
            assert health["public_read_only"] and health["read_only"]
            assert not health["demo_restore_enabled"]
            assert "/api/import" not in client.get("/openapi.json").json()["paths"]
            for method, path in (
                ("POST", "/api/import"), ("POST", "/api/demo/restore"),
                ("DELETE", "/api/participants/SYN-P001"), ("PUT", "/"),
                ("PATCH", "/api/future-write"), ("POST", "/static/app.js"),
            ):
                response = client.request(method, path, content=b"malformed")
                assert response.status_code == 403
            assert client.get("/api/summary").json()["observations"] == 0
    finally:
        engine.dispose()
