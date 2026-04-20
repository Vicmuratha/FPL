from __future__ import annotations

import asyncio
import logging
import random
from collections import deque
from datetime import datetime, timezone
from typing import Deque, Dict

import numpy as np

from .config import default_player_baselines, default_squads, default_top10k_state
from .fpl_provider import RealFPLDataProvider
from .ingest import LiveDataProvider, MockLiveDataProvider, apply_events
from .models import EngineSnapshot, LiveEvent, RankingEstimate, Top10kModelState, UserSquad
from .predictor import project_players
from .ranking import SimulationConfig, estimate_top10k_probability
from .settings import Settings
from .storage import SQLiteRepository

logger = logging.getLogger(__name__)


class LiveFPLEngine:
    def __init__(self, settings: Settings, provider: LiveDataProvider | None = None) -> None:
        self.settings = settings
        self.baselines = default_player_baselines() if settings.data_source == "mock" else {}
        self.squads: list[UserSquad] = default_squads() if settings.data_source == "mock" else []
        self.top10k_state: Top10kModelState = default_top10k_state()

        self._py_rand = random.Random(settings.random_seed)
        self._np_rng = np.random.default_rng(settings.random_seed)

        if provider is not None:
            self.provider = provider
        elif settings.data_source == "fpl":
            self.provider = RealFPLDataProvider(settings)
        else:
            self.provider = MockLiveDataProvider(
                self.baselines,
                tick_seconds=settings.tick_seconds,
                rand=self._py_rand,
            )
        self.simulation_cfg = SimulationConfig(samples=settings.simulation_samples)
        self.repo = SQLiteRepository(settings.sqlite_path)

        self.live_state = {}
        self.recent_events: Deque[LiveEvent] = deque(maxlen=250)
        self._iteration = 0
        self._running = False
        self._last_success_at: datetime | None = None
        self._last_error: str | None = None
        self._failure_count = 0
        self._task: asyncio.Task | None = None
        self._snapshot = EngineSnapshot(
            as_of=datetime.now(timezone.utc),
            projections={},
            ranking_by_team={},
            recent_events=[],
            iteration=0,
        )
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        baselines, squads, top10k_state = await self.provider.initialize()
        self.baselines = baselines
        if squads:
            self.squads = squads
        self.top10k_state = top10k_state

        if not self.squads:
            raise RuntimeError(
                "No tracked squads configured. Set FPL_ENTRY_IDS when using real FPL data."
            )

        if self._task is None:
            self._running = True
            self._task = asyncio.create_task(self.run_forever())

    async def stop(self) -> None:
        self._running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        self.repo.close()

    async def run_forever(self) -> None:
        backoff_seconds = 0.5
        while self._running:
            try:
                async for events in self.provider.stream():
                    if not self._running:
                        break
                    await self.process_tick(events)
                backoff_seconds = 0.5
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._failure_count += 1
                self._last_error = str(exc)
                logger.exception("engine_tick_failed")
                await asyncio.sleep(min(backoff_seconds, 5.0))
                backoff_seconds *= 2.0

    async def process_tick(self, events: list[LiveEvent]) -> None:
        async with self._lock:
            apply_events(self.live_state, events)
            self.recent_events.extend(events)

            projections = project_players(self.baselines, self.live_state)
            ranking = self._rank_all_teams(projections)

            self._iteration += 1
            self._snapshot = EngineSnapshot(
                as_of=datetime.now(timezone.utc),
                projections=projections,
                ranking_by_team=ranking,
                recent_events=list(self.recent_events)[-25:],
                iteration=self._iteration,
            )
            self._last_success_at = self._snapshot.as_of
            self._last_error = None

        self.repo.persist_events(events, max_rows=self.settings.event_limit)
        self.repo.persist_snapshot(self._snapshot, max_rows=self.settings.snapshot_limit)

    def _rank_all_teams(self, projections) -> Dict[str, RankingEstimate]:
        ranking: Dict[str, RankingEstimate] = {}
        live_intensity = sum(p.projected_total_points for p in projections.values()) / max(1, len(projections))

        # Dynamic threshold shifts with live scoring intensity.
        shifted_threshold = self.top10k_state.threshold_mean + self.top10k_state.momentum_factor * (live_intensity - 6.0)
        current_top10k_state = Top10kModelState(
            threshold_mean=shifted_threshold,
            threshold_std=self.top10k_state.threshold_std,
            momentum_factor=self.top10k_state.momentum_factor,
        )

        for squad in self.squads:
            ranking[squad.team_id] = estimate_top10k_probability(
                squad=squad,
                projections=projections,
                top10k_state=current_top10k_state,
                config=self.simulation_cfg,
                rng=self._np_rng,
            )

        return ranking

    async def get_snapshot(self) -> EngineSnapshot:
        async with self._lock:
            return self._snapshot

    async def status(self) -> dict[str, str | int | bool | None]:
        async with self._lock:
            return {
                "running": self._running,
                "iteration": self._iteration,
                "failure_count": self._failure_count,
                "last_success_at": self._last_success_at.isoformat() if self._last_success_at else None,
                "last_error": self._last_error,
            }
