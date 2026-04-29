from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

from .engine.logging_utils import configure_logging
from .engine.settings import get_settings
from .engine.service import LiveFPLEngine

REQUESTS_TOTAL = Counter("fpl_requests_total", "Total HTTP requests", ["path"])
SNAPSHOT_ITERATION = Gauge("fpl_snapshot_iteration", "Last computed iteration")
TICK_DURATION = Histogram("fpl_tick_duration_seconds", "Engine tick latency")
STATIC_ROOT = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine: LiveFPLEngine = app.state.engine
    await engine.start()
    try:
        yield
    finally:
        await engine.stop()


def _api_key_guard(x_api_key: str | None = Header(default=None), settings=Depends(get_settings)) -> None:
    if settings.api_key and x_api_key != settings.api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")


def create_app() -> FastAPI:
    configure_logging()
    settings = get_settings()
    engine = LiveFPLEngine(settings)

    app = FastAPI(
        title=settings.app_name,
        description="Streams live FPL projections and top-10k probability estimates.",
        version=settings.app_version,
        lifespan=lifespan,
    )
    app.state.engine = engine
    app.state.settings = settings

    @app.get("/")
    async def dashboard() -> FileResponse:
        return FileResponse(STATIC_ROOT / "index.html")

    @app.get("/health/live")
    async def health_live() -> dict[str, str]:
        REQUESTS_TOTAL.labels(path="/health/live").inc()
        return {"status": "ok"}

    @app.get("/health/ready")
    async def health_ready() -> dict:
        REQUESTS_TOTAL.labels(path="/health/ready").inc()
        status = await app.state.engine.status()
        if not status["running"]:
            raise HTTPException(status_code=503, detail=status)

        last_error = status.get("last_error")
        last_success_at = status.get("last_success_at")
        if last_error is not None or last_success_at is None:
            raise HTTPException(status_code=503, detail=status)

        success_at = datetime.fromisoformat(str(last_success_at))
        max_age_seconds = max(3.0 * app.state.settings.tick_seconds, 10.0)
        age_seconds = (datetime.now(timezone.utc) - success_at).total_seconds()
        if age_seconds > max_age_seconds:
            raise HTTPException(status_code=503, detail=status)
        return {"status": "ready", "engine": status}

    @app.get("/snapshot", dependencies=[Depends(_api_key_guard)])
    async def snapshot() -> dict:
        REQUESTS_TOTAL.labels(path="/snapshot").inc()
        with TICK_DURATION.time():
            snap = await app.state.engine.get_snapshot()
        SNAPSHOT_ITERATION.set(snap.iteration)
        return snap.model_dump(mode="json")

    @app.get("/metrics")
    async def metrics() -> Response:
        if not app.state.settings.metrics_enabled:
            raise HTTPException(status_code=404, detail="metrics disabled")
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.websocket("/ws")
    async def ws_updates(websocket: WebSocket) -> None:
        await websocket.accept()
        try:
            while True:
                snap = await app.state.engine.get_snapshot()
                await websocket.send_text(json.dumps(snap.model_dump(mode="json")))
                await asyncio.sleep(app.state.settings.ws_push_seconds)
        except WebSocketDisconnect:
            return

    return app


app = create_app()
