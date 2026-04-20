# Live Fantasy Premier League Strategy Engine

Production-oriented real-time FPL strategy engine that:
- Ingests official live FPL match data continuously from the public FPL API.
- Recalculates player projected points every tick.
- Re-estimates top-10k finish probabilities with Monte Carlo simulation.
- Persists events and snapshots to SQLite with bounded retention.
- Exposes operational health and Prometheus metrics.

## Key Components

- fpl_engine/engine/ingest.py
  - Live data provider protocol, mock provider, and event reducer.
- fpl_engine/engine/predictor.py
  - FPL scoring logic and expected additional points model.
- fpl_engine/engine/ranking.py
  - Monte Carlo top-10k probability estimator.
- fpl_engine/engine/service.py
  - Engine runtime, retry/backoff, durability writes, and status tracking.
- fpl_engine/engine/storage.py
  - SQLite repository with WAL mode and bounded cleanup.
- fpl_engine/engine/settings.py
  - Environment-driven runtime configuration.
- fpl_engine/app.py
  - FastAPI app factory with readiness, metrics, auth guard, and WebSocket streaming.

## Local Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn fpl_engine.app:app --reload
```

## Real Data Configuration

Set your FPL entry IDs in .env:

```bash
FPL_DATA_SOURCE=fpl
FPL_FPL_ENTRY_IDS=123456,234567
```

Optional:
- Set FPL_FPL_CURRENT_EVENT to lock a specific gameweek.
- Leave FPL_FPL_CURRENT_EVENT empty to auto-detect current gameweek.

The engine polls:
- /api/bootstrap-static/ for players/teams metadata
- /api/event/{gw}/live/ for real-time player stats
- /api/entry/{entry_id}/ and /api/entry/{entry_id}/event/{gw}/picks/ for tracked squads

## Endpoints

- GET /
- GET /health/live
- GET /health/ready
- GET /snapshot
- GET /metrics
- WS /ws

If FPL_API_KEY is configured, pass header X-API-Key on /snapshot.
The dashboard at / uses WebSocket updates and does not require calling /snapshot directly.

## Tests

```bash
pytest -q
```

## Container Run

```bash
docker build -t fpl-engine .
docker run --rm -p 8000:8000 --env-file .env fpl-engine
```

## Production Readiness Notes

- Official FPL API provider is enabled in real mode via FPL_DATA_SOURCE=fpl.
- Back pressure, retries, and failure counts are implemented in engine runtime.
- Event and snapshot retention is bounded via environment variables.
- Metrics are Prometheus compatible for dashboards and alerting.
