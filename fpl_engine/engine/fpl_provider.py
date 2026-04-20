from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from datetime import datetime, timezone

import httpx

from .models import (
    EventType,
    LiveEvent,
    PlayerBaseline,
    Position,
    Top10kModelState,
    UserPick,
    UserSquad,
)
from .settings import Settings

logger = logging.getLogger(__name__)


def _to_float(value: object, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


class RealFPLDataProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.base_url = settings.fpl_base_url.rstrip("/")
        self.timeout = settings.fpl_request_timeout_seconds
        self._last_stats: dict[int, dict[str, float]] = {}
        self._event_id: int | None = settings.fpl_current_event

    async def initialize(self) -> tuple[dict[int, PlayerBaseline], list[UserSquad], Top10kModelState]:
        async with httpx.AsyncClient(timeout=self.timeout, headers={"User-Agent": self.settings.fpl_user_agent}) as client:
            bootstrap = await self._get_json(client, f"{self.base_url}/bootstrap-static/")
            if self._event_id is None:
                self._event_id = self._discover_event_id(bootstrap)

            baselines = self._build_baselines(bootstrap)
            squads = await self._load_user_squads(client, self._event_id)

            threshold = self._derive_threshold(bootstrap, self._event_id)
            top10k_state = Top10kModelState(
                threshold_mean=threshold,
                threshold_std=max(20.0, threshold * 0.03),
                momentum_factor=0.25,
            )

        logger.info(
            "fpl_provider_initialized",
            extra={
                "event_id": self._event_id,
                "players": len(baselines),
                "squads": len(squads),
            },
        )
        return baselines, squads, top10k_state

    async def stream(self) -> AsyncIterator[list[LiveEvent]]:
        if self._event_id is None:
            raise RuntimeError("Provider not initialized. Call initialize() first.")

        async with httpx.AsyncClient(timeout=self.timeout, headers={"User-Agent": self.settings.fpl_user_agent}) as client:
            while True:
                payload = await self._get_json(client, f"{self.base_url}/event/{self._event_id}/live/")
                now = datetime.now(timezone.utc)
                events = self._extract_delta_events(payload, now)
                yield events
                await asyncio.sleep(self.settings.tick_seconds)

    async def _load_user_squads(self, client: httpx.AsyncClient, event_id: int) -> list[UserSquad]:
        squads: list[UserSquad] = []
        for entry_id in self.settings.parsed_entry_ids:
            entry_payload = await self._get_json(client, f"{self.base_url}/entry/{entry_id}/")
            picks_payload = await self._get_json(client, f"{self.base_url}/entry/{entry_id}/event/{event_id}/picks/")

            picks = [
                UserPick(player_id=int(item["element"]), multiplier=float(item.get("multiplier", 1.0)))
                for item in picks_payload.get("picks", [])
            ]

            squads.append(
                UserSquad(
                    team_id=f"entry-{entry_id}",
                    overall_points_before_gw=int(entry_payload.get("summary_overall_points", 0)),
                    gameweek_live_points=float(picks_payload.get("entry_history", {}).get("points", 0.0)),
                    picks=picks,
                )
            )

        return squads

    def _discover_event_id(self, bootstrap: dict) -> int:
        events = bootstrap.get("events", [])
        current = next((event for event in events if event.get("is_current")), None)
        if current:
            return int(current["id"])

        next_event = next((event for event in events if event.get("is_next")), None)
        if next_event:
            return int(next_event["id"])

        if events:
            return int(events[-1]["id"])

        raise RuntimeError("No gameweek events found in FPL bootstrap data")

    def _derive_threshold(self, bootstrap: dict, event_id: int) -> float:
        event = next((e for e in bootstrap.get("events", []) if int(e.get("id", -1)) == event_id), None)
        if not event:
            return 1850.0

        avg_entry_score = _to_float(event.get("average_entry_score"), 50.0)
        # This remains a model prior; calibrate from historical top-10k when available.
        return 1750.0 + avg_entry_score

    def _build_baselines(self, bootstrap: dict) -> dict[int, PlayerBaseline]:
        teams = {int(team["id"]): str(team.get("short_name", team.get("name", "UNK"))) for team in bootstrap.get("teams", [])}

        baselines: dict[int, PlayerBaseline] = {}
        for element in bootstrap.get("elements", []):
            player_id = int(element["id"])
            minutes = max(1.0, _to_float(element.get("minutes"), 1.0))
            matches_equivalent = max(1.0, minutes / 90.0)
            element_type = int(element.get("element_type", 4))

            position = {
                1: Position.GK,
                2: Position.DEF,
                3: Position.MID,
                4: Position.FWD,
            }.get(element_type, Position.FWD)

            xg_per90 = _to_float(element.get("expected_goals_per_90"))
            xa_per90 = _to_float(element.get("expected_assists_per_90"))
            if xg_per90 == 0.0:
                xg_per90 = _to_float(element.get("goals_scored")) / matches_equivalent
            if xa_per90 == 0.0:
                xa_per90 = _to_float(element.get("assists")) / matches_equivalent

            clean_sheet_prob = min(1.0, max(0.0, _to_float(element.get("clean_sheets")) / matches_equivalent))
            save_rate_per90 = _to_float(element.get("saves")) / matches_equivalent if position == Position.GK else 0.0

            selected_by_percent = _to_float(element.get("selected_by_percent"))
            ownership = min(1.0, max(0.0, selected_by_percent / 100.0))

            baselines[player_id] = PlayerBaseline(
                player_id=player_id,
                name=str(element.get("web_name", f"P{player_id}")),
                team=teams.get(int(element.get("team", 0)), "UNK"),
                position=position,
                ownership_top10k=ownership,
                xg_per90=max(0.0, xg_per90),
                xa_per90=max(0.0, xa_per90),
                clean_sheet_prob=clean_sheet_prob,
                save_rate_per90=max(0.0, save_rate_per90),
            )

        return baselines

    async def _get_json(self, client: httpx.AsyncClient, url: str) -> dict:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()

    def _extract_delta_events(self, payload: dict, timestamp: datetime) -> list[LiveEvent]:
        events: list[LiveEvent] = []

        for player_key, item in payload.get("elements", {}).items():
            player_id = int(player_key)
            stats = item.get("stats", {})
            current = {
                "minutes": _to_float(stats.get("minutes")),
                "goals_scored": _to_float(stats.get("goals_scored")),
                "assists": _to_float(stats.get("assists")),
                "clean_sheets": _to_float(stats.get("clean_sheets")),
                "saves": _to_float(stats.get("saves")),
                "bonus": _to_float(stats.get("bonus")),
                "yellow_cards": _to_float(stats.get("yellow_cards")),
                "red_cards": _to_float(stats.get("red_cards")),
                "own_goals": _to_float(stats.get("own_goals")),
                "penalties_missed": _to_float(stats.get("penalties_missed")),
                "penalties_saved": _to_float(stats.get("penalties_saved")),
            }

            previous = self._last_stats.get(player_id, {k: 0.0 for k in current.keys()})
            self._last_stats[player_id] = current

            deltas = {k: max(0.0, current[k] - previous.get(k, 0.0)) for k in current.keys()}

            mapping = {
                "minutes": EventType.MINUTES,
                "goals_scored": EventType.GOAL,
                "assists": EventType.ASSIST,
                "clean_sheets": EventType.CLEAN_SHEET,
                "saves": EventType.SAVE,
                "bonus": EventType.BONUS,
                "yellow_cards": EventType.YELLOW,
                "red_cards": EventType.RED,
                "own_goals": EventType.OWN_GOAL,
                "penalties_missed": EventType.PENALTY_MISS,
                "penalties_saved": EventType.PENALTY_SAVE,
            }

            for key, delta in deltas.items():
                if delta <= 0.0:
                    continue
                events.append(
                    LiveEvent(
                        timestamp=timestamp,
                        player_id=player_id,
                        event_type=mapping[key],
                        value=delta,
                    )
                )

        return events
