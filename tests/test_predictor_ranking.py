from __future__ import annotations

import numpy as np

from fpl_engine.engine.config import default_player_baselines, default_squads, default_top10k_state
from fpl_engine.engine.models import PlayerLiveState, PlayerBaseline, Position
from fpl_engine.engine.predictor import (
    project_players,
    compute_current_points,
    compute_expected_additional_points
)
from fpl_engine.engine.ranking import SimulationConfig, estimate_top10k_probability


def test_compute_current_points_edge_cases() -> None:
    # Test GK edge cases (saves, penalties saved)
    gk_base = PlayerBaseline(
        player_id=1, position=Position.GK, fpl_id=1, name="GK", start_prob=1.0,
        team="Team", ownership_top10k=0.1, xg_per90=0.0, xa_per90=0.0, clean_sheet_prob=0.4, save_rate_per90=3.0
    )
    gk_live = PlayerLiveState(player_id=1, minutes=90, saves=7, penalties_saved=1, clean_sheet=1)
    # 2 (minutes) + 4 (CS) + 2 (saves) + 5 (pens saved) = 13
    assert compute_current_points(gk_base, gk_live) == 13.0

    # Test Midfielder points, cards, own goals
    mid_base = PlayerBaseline(
        player_id=2, position=Position.MID, fpl_id=2, name="MID", start_prob=1.0,
        team="Team", ownership_top10k=0.1, xg_per90=0.0, xa_per90=0.0, clean_sheet_prob=0.4, save_rate_per90=0.0
    )
    mid_live = PlayerLiveState(player_id=2, minutes=45, goals=1, clean_sheet=1, red_cards=1, own_goals=1)
    # 1 (minutes) + 5 (goal) + 1 (CS) - 3 (red card) - 2 (own goal) = 2
    assert compute_current_points(mid_base, mid_live) == 2.0


def test_expected_additional_points_full_match() -> None:
    base = PlayerBaseline(
        player_id=1, position=Position.FWD, fpl_id=1, name="FWD", start_prob=1.0,
        team="Team", ownership_top10k=0.1, xg_per90=0.5, xa_per90=0.2, clean_sheet_prob=0.1, save_rate_per90=0.0
    )
    live = PlayerLiveState(player_id=1, minutes=90)
    # No time left, expected points should be strictly 0
    assert compute_expected_additional_points(base, live) == 0.0
    
    overtime_live = PlayerLiveState(player_id=1, minutes=120)
    assert compute_expected_additional_points(base, overtime_live) == 0.0


def test_projection_outputs_for_all_players() -> None:
    baselines = default_player_baselines()
    live_state = {pid: PlayerLiveState(player_id=pid, minutes=45) for pid in baselines}

    projections = project_players(baselines, live_state)

    assert len(projections) == len(baselines)
    for projection in projections.values():
        assert projection.projected_total_points >= projection.current_points
        assert projection.volatility >= 0.75


def test_top10k_probability_bounds() -> None:
    baselines = default_player_baselines()
    live_state = {pid: PlayerLiveState(player_id=pid, minutes=60) for pid in baselines}
    projections = project_players(baselines, live_state)

    squad = default_squads()[0]
    estimate = estimate_top10k_probability(
        squad=squad,
        projections=projections,
        top10k_state=default_top10k_state(),
        config=SimulationConfig(samples=2500),
        rng=np.random.default_rng(123),
    )

    assert 0.0 <= estimate.probability_top10k <= 1.0
    assert estimate.expected_global_rank >= 1
