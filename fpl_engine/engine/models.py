from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class Position(str, Enum):
    GK = "GK"
    DEF = "DEF"
    MID = "MID"
    FWD = "FWD"


class EventType(str, Enum):
    GOAL = "goal"
    ASSIST = "assist"
    CLEAN_SHEET = "clean_sheet"
    SAVE = "save"
    BONUS = "bonus"
    YELLOW = "yellow"
    RED = "red"
    OWN_GOAL = "own_goal"
    PENALTY_MISS = "penalty_miss"
    PENALTY_SAVE = "penalty_save"
    MINUTES = "minutes"


class PlayerBaseline(BaseModel):
    player_id: int
    name: str
    team: str
    position: Position
    ownership_top10k: float = Field(ge=0.0, le=1.0)
    xg_per90: float = Field(ge=0.0)
    xa_per90: float = Field(ge=0.0)
    clean_sheet_prob: float = Field(ge=0.0, le=1.0)
    save_rate_per90: float = Field(ge=0.0)


class LiveEvent(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    player_id: int
    event_type: EventType
    value: float = 1.0


class PlayerLiveState(BaseModel):
    player_id: int
    minutes: int = 0
    goals: int = 0
    assists: int = 0
    clean_sheet: int = 0
    saves: int = 0
    bonus: int = 0
    yellow_cards: int = 0
    red_cards: int = 0
    own_goals: int = 0
    penalties_missed: int = 0
    penalties_saved: int = 0


class PlayerProjection(BaseModel):
    player_id: int
    current_points: float
    expected_additional_points: float
    projected_total_points: float
    volatility: float = Field(ge=0.1)


class UserPick(BaseModel):
    player_id: int
    multiplier: float = 1.0


class UserSquad(BaseModel):
    team_id: str
    overall_points_before_gw: int
    gameweek_live_points: float = 0.0
    picks: List[UserPick]


class Top10kModelState(BaseModel):
    threshold_mean: float = 65.0
    threshold_std: float = 12.0
    momentum_factor: float = 0.35


class RankingEstimate(BaseModel):
    probability_top10k: float = Field(ge=0.0, le=1.0)
    expected_global_rank: int = Field(ge=1)
    sampled_threshold_mean: float
    sampled_threshold_std: float


class EngineSnapshot(BaseModel):
    as_of: datetime
    projections: Dict[int, PlayerProjection]
    ranking_by_team: Dict[str, RankingEstimate]
    recent_events: List[LiveEvent]
    iteration: int

