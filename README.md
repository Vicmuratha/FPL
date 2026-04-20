# Live Fantasy Premier League Strategy Engine

Real-time FPL strategy engine that ingests official live data, projects player points, and recalculates top-10k finish probabilities continuously.

## What It Does

- Ingests live data from official FPL endpoints.
- Rebuilds player projections on each tick.
- Runs Monte Carlo simulations for top-10k probabilities.
- Persists snapshots and event stream data to SQLite.
- Serves a live dashboard and API endpoints from FastAPI.

## Quick Start (Local)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit .env and set your real FPL team IDs:

```bash
FPL_DATA_SOURCE=fpl
FPL_FPL_ENTRY_IDS=123456,234567
```

Start the app:

```bash
uvicorn fpl_engine.app:app --host 127.0.0.1 --port 8000 --reload
```

Open the frontend dashboard:

- http://127.0.0.1:8000/

## Real-Time Data Source

When FPL_DATA_SOURCE=fpl, the engine uses:

- /api/bootstrap-static/
- /api/event/{gw}/live/
- /api/entry/{entry_id}/
- /api/entry/{entry_id}/event/{gw}/picks/

Notes:

- FPL_FPL_ENTRY_IDS is required in real mode.
- FPL_FPL_CURRENT_EVENT is optional. If blank, the app auto-detects current gameweek.

## Frontend and API

Available routes:

- GET /
- GET /health/live
- GET /health/ready
- GET /snapshot
- GET /metrics
- WS /ws

Security behavior:

- If FPL_API_KEY is set, /snapshot requires header X-API-Key.
- The dashboard at / uses WebSocket updates from /ws.

## Configuration

All runtime settings are environment-driven through .env. See .env.example for full list.

Key options:

- FPL_DATA_SOURCE: mock or fpl
- FPL_TICK_SECONDS: ingestion/prediction cadence
- FPL_SIMULATION_SAMPLES: Monte Carlo sample count
- FPL_SQLITE_PATH: persisted data location
- FPL_SNAPSHOT_LIMIT and FPL_EVENT_LIMIT: retention controls
- FPL_METRICS_ENABLED: enable or disable /metrics

## Testing

```bash
python3 -m pytest -q
```

## Docker

```bash
docker build -t fpl-engine .
docker run --rm -p 8000:8000 --env-file .env fpl-engine
```

## Troubleshooting

### Port already in use

If startup fails with address already in use, run on a different port:

```bash
uvicorn fpl_engine.app:app --host 127.0.0.1 --port 8001 --reload
```

### Dashboard returns 404

This usually means an older server process is still running from a previous version.

- Stop old process.
- Start the current app again.
- Confirm by opening /health/live and then /.

### Real mode fails at startup

Check that:

- FPL_DATA_SOURCE=fpl
- FPL_FPL_ENTRY_IDS has valid numeric entry IDs
- Outbound access to fantasy.premierleague.com is available

## Project Structure

- fpl_engine/app.py: FastAPI app factory, routes, and lifecycle
- fpl_engine/static/index.html: live frontend dashboard
- fpl_engine/engine/fpl_provider.py: official FPL ingestion provider
- fpl_engine/engine/service.py: orchestration, retries, persistence writes
- fpl_engine/engine/predictor.py: projection logic
- fpl_engine/engine/ranking.py: top-10k probability simulation
- fpl_engine/engine/storage.py: SQLite repository
- fpl_engine/engine/settings.py: environment-backed configuration
