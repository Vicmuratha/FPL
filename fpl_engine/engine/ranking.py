from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

import numpy as np

from .models import RankingEstimate, Top10kModelState, UserSquad
from .models import PlayerProjection


@dataclass
class SimulationConfig:
    samples: int = 8000
    rank_spread: int = 9500000


def _team_projection_mean_and_std(
    squad: UserSquad, projections: Dict[int, PlayerProjection]
) -> tuple[float, float]:
    total_mean = float(squad.overall_points_before_gw + squad.gameweek_live_points)
    variance = 0.0

    for pick in squad.picks:
        proj = projections.get(pick.player_id)
        if proj is None:
            continue
        weighted_mean = (proj.projected_total_points - proj.current_points) * pick.multiplier
        weighted_std = proj.volatility * pick.multiplier
        total_mean += weighted_mean
        variance += weighted_std**2

    return total_mean, max(1.0, variance**0.5)


def estimate_top10k_probability(
    squad: UserSquad,
    projections: Dict[int, PlayerProjection],
    top10k_state: Top10kModelState,
    config: SimulationConfig,
    rng: np.random.Generator,
) -> RankingEstimate:
    team_mean, team_std = _team_projection_mean_and_std(squad, projections)

    # Sample the user's final score and moving top-10k cutoff.
    team_samples = rng.normal(loc=team_mean, scale=team_std, size=config.samples)
    threshold_samples = rng.normal(
        loc=top10k_state.threshold_mean,
        scale=max(1.0, top10k_state.threshold_std),
        size=config.samples,
    )

    wins = team_samples >= threshold_samples
    probability = float(np.mean(wins))

    # Convert probability to an expected rank among active teams.
    expected_rank = int(max(1, round((1.0 - probability) * config.rank_spread)))

    return RankingEstimate(
        probability_top10k=probability,
        expected_global_rank=expected_rank,
        sampled_threshold_mean=float(np.mean(threshold_samples)),
        sampled_threshold_std=float(np.std(threshold_samples)),
    )
