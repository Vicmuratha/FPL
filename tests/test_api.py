from __future__ import annotations

from fastapi.testclient import TestClient

from fpl_engine.app import create_app
from fpl_engine.engine.settings import get_settings


def test_liveness() -> None:
    app = create_app()
    with TestClient(app) as client:
        response = client.get("/health/live")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


def test_snapshot_endpoint() -> None:
    app = create_app()
    settings = get_settings()
    headers = {"X-API-Key": settings.api_key} if settings.api_key else {}
    with TestClient(app) as client:
        response = client.get("/snapshot", headers=headers)
        assert response.status_code == 200
        payload = response.json()
        assert "iteration" in payload
        assert "ranking_by_team" in payload
