from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from fpl_engine.app import create_app
from fpl_engine.engine.settings import get_settings
from fpl_engine.engine.models import EngineSnapshot


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


def test_readiness_fails_when_engine_is_stale() -> None:
    app = create_app()
    stale_time = datetime.now(timezone.utc) - timedelta(seconds=60)

    async def stale_status() -> dict[str, object]:
        return {
            "running": True,
            "iteration": 12,
            "failure_count": 0,
            "last_success_at": stale_time.isoformat(),
            "last_error": None,
        }

    app.state.engine.status = stale_status

    with TestClient(app) as client:
        response = client.get("/health/ready")
        assert response.status_code == 503


def test_snapshot_etag_supports_conditional_get() -> None:
    app = create_app()
    fixed_time = datetime(2026, 4, 29, 12, 0, 0, tzinfo=timezone.utc)
    snapshot = EngineSnapshot(
        as_of=fixed_time,
        projections={},
        ranking_by_team={},
        recent_events=[],
        iteration=42,
    )

    async def fixed_snapshot() -> EngineSnapshot:
        return snapshot

    app.state.engine.get_snapshot = fixed_snapshot

    with TestClient(app) as client:
        settings = get_settings()
        headers = {"X-API-Key": settings.api_key} if settings.api_key else {}
        first = client.get("/snapshot", headers=headers)
        assert first.status_code == 200
        etag = first.headers.get("ETag")
        assert etag is not None

        second = client.get("/snapshot", headers={**headers, "If-None-Match": etag})
        assert second.status_code == 304
