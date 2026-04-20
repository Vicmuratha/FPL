from __future__ import annotations

from math import sqrt
from typing import Dict

from .models import PlayerBaseline, PlayerLiveState, PlayerProjection, Position


def _appearance_points(minutes: int) -> int:
    if minutes == 0:
        return 0
    if minutes < 60:
        return 1
    return 2


def _goal_points(position: Position) -> int:
    if position == Position.GK or position == Position.DEF:
        return 6
    if position == Position.MID:
        return 5
    return 4


def _clean_sheet_points(position: Position) -> int:
    if position == Position.GK or position == Position.DEF:
        return 4
    if position == Position.MID:
        return 1
    return 0


def compute_current_points(baseline: PlayerBaseline, live: PlayerLiveState) -> float:
    points = 0.0
    points += _appearance_points(live.minutes)
    points += live.goals * _goal_points(baseline.position)
    points += live.assists * 3
    points += live.clean_sheet * _clean_sheet_points(baseline.position)
    if baseline.position == Position.GK:
        points += (live.saves // 3)
        points += live.penalties_saved * 5
    points += live.bonus
    points -= live.yellow_cards
    points -= live.red_cards * 3
    points -= live.own_goals * 2
    points -= live.penalties_missed * 2
    return points


def compute_expected_additional_points(baseline: PlayerBaseline, live: PlayerLiveState) -> float:
    remaining_minutes = max(0, 90 - live.minutes)
    rem_ratio = remaining_minutes / 90.0

    expected_goals = baseline.xg_per90 * rem_ratio
    expected_assists = baseline.xa_per90 * rem_ratio
    expected_cs = baseline.clean_sheet_prob * rem_ratio
    expected_saves = baseline.save_rate_per90 * rem_ratio

    ep = 0.0
    if live.minutes < 60:
        ep += max(0.0, 2.0 - _appearance_points(live.minutes))
    ep += expected_goals * _goal_points(baseline.position)
    ep += expected_assists * 3.0
    ep += expected_cs * _clean_sheet_points(baseline.position)
    if baseline.position == Position.GK:
        ep += expected_saves / 3.0

    # Late-game cards and random variance drag expected value slightly.
    variance_drag = 0.15 * rem_ratio
    return max(0.0, ep - variance_drag)


def project_players(
    baselines: Dict[int, PlayerBaseline],
    live_state: Dict[int, PlayerLiveState],
) -> Dict[int, PlayerProjection]:
    projections: Dict[int, PlayerProjection] = {}
    for player_id, baseline in baselines.items():
        live = live_state.get(player_id, PlayerLiveState(player_id=player_id))
        current = compute_current_points(baseline, live)
        additional = compute_expected_additional_points(baseline, live)
        volatility = max(0.75, sqrt(additional + 0.75))
        projections[player_id] = PlayerProjection(
            player_id=player_id,
            current_points=current,
            expected_additional_points=additional,
            projected_total_points=current + additional,
            volatility=volatility,
        )
    return projections
