from __future__ import annotations

import numpy as np

from fpl_engine.engine.config import default_player_baselines, default_squads, default_top10k_state
from fpl_engine.engine.models import PlayerLiveState
from fpl_engine.engine.predictor import project_players
from fpl_engine.engine.ranking import SimulationConfig, estimate_top10k_probability


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
