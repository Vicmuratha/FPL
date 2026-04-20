from __future__ import annotations

import asyncio
import random
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Dict, List, Protocol

from .models import EventType, LiveEvent, PlayerBaseline, PlayerLiveState, Top10kModelState, UserSquad


class LiveDataProvider(Protocol):
    async def initialize(self) -> tuple[Dict[int, PlayerBaseline], list[UserSquad], Top10kModelState]:
        ...

    async def stream(self) -> AsyncIterator[List[LiveEvent]]:
        ...


class MockLiveDataProvider:
    def __init__(
        self,
        baselines: Dict[int, PlayerBaseline],
        tick_seconds: float = 1.0,
        rand: random.Random | None = None,
    ) -> None:
        self.baselines = baselines
        self.tick_seconds = tick_seconds
        self.rand = rand or random.Random()
        self._minutes: Dict[int, int] = {pid: 0 for pid in baselines}

    async def initialize(self) -> tuple[Dict[int, PlayerBaseline], list[UserSquad], Top10kModelState]:
        from .config import default_squads, default_top10k_state

        return self.baselines, default_squads(), default_top10k_state()

    async def stream(self) -> AsyncIterator[List[LiveEvent]]:
        while True:
            await asyncio.sleep(self.tick_seconds)
            events = self._generate_tick_events()
            yield events

    def _generate_tick_events(self) -> List[LiveEvent]:
        events: List[LiveEvent] = []
        now = datetime.now(timezone.utc)

        for player_id, baseline in self.baselines.items():
            if self._minutes[player_id] >= 90:
                continue

            # Advance by 1-3 minutes each tick for variable pace.
            inc = self.rand.choice((1, 2, 3))
            self._minutes[player_id] = min(90, self._minutes[player_id] + inc)
            events.append(
                LiveEvent(
                    timestamp=now,
                    player_id=player_id,
                    event_type=EventType.MINUTES,
                    value=float(inc),
                )
            )

            # Simple stochastic event generation from baseline rates.
            if self.rand.random() < baseline.xg_per90 * 0.08:
                events.append(
                    LiveEvent(
                        timestamp=now,
                        player_id=player_id,
                        event_type=EventType.GOAL,
                        value=1.0,
                    )
                )
            if self.rand.random() < baseline.xa_per90 * 0.08:
                events.append(
                    LiveEvent(
                        timestamp=now,
                        player_id=player_id,
                        event_type=EventType.ASSIST,
                        value=1.0,
                    )
                )
            if self.rand.random() < 0.01:
                events.append(
                    LiveEvent(
                        timestamp=now,
                        player_id=player_id,
                        event_type=EventType.YELLOW,
                        value=1.0,
                    )
                )
            if baseline.position.value == "GK" and self.rand.random() < baseline.save_rate_per90 * 0.04:
                events.append(
                    LiveEvent(
                        timestamp=now,
                        player_id=player_id,
                        event_type=EventType.SAVE,
                        value=1.0,
                    )
                )

        return events


def apply_events(live_state: Dict[int, PlayerLiveState], events: List[LiveEvent]) -> None:
    for event in events:
        state = live_state.setdefault(event.player_id, PlayerLiveState(player_id=event.player_id))
        if event.event_type == EventType.MINUTES:
            state.minutes = min(90, state.minutes + int(event.value))
        elif event.event_type == EventType.GOAL:
            state.goals += int(event.value)
        elif event.event_type == EventType.ASSIST:
            state.assists += int(event.value)
        elif event.event_type == EventType.CLEAN_SHEET:
            state.clean_sheet += int(event.value)
        elif event.event_type == EventType.SAVE:
            state.saves += int(event.value)
        elif event.event_type == EventType.BONUS:
            state.bonus += int(event.value)
        elif event.event_type == EventType.YELLOW:
            state.yellow_cards += int(event.value)
        elif event.event_type == EventType.RED:
            state.red_cards += int(event.value)
        elif event.event_type == EventType.OWN_GOAL:
            state.own_goals += int(event.value)
        elif event.event_type == EventType.PENALTY_MISS:
            state.penalties_missed += int(event.value)
        elif event.event_type == EventType.PENALTY_SAVE:
            state.penalties_saved += int(event.value)
