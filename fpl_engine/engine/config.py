from __future__ import annotations

from .models import PlayerBaseline, Position, Top10kModelState, UserPick, UserSquad


def default_player_baselines() -> dict[int, PlayerBaseline]:
    return {
        1: PlayerBaseline(
            player_id=1,
            name="Aria Keeper",
            team="ARC",
            position=Position.GK,
            ownership_top10k=0.24,
            xg_per90=0.01,
            xa_per90=0.02,
            clean_sheet_prob=0.38,
            save_rate_per90=3.2,
        ),
        2: PlayerBaseline(
            player_id=2,
            name="Bennett Wall",
            team="ARC",
            position=Position.DEF,
            ownership_top10k=0.31,
            xg_per90=0.10,
            xa_per90=0.08,
            clean_sheet_prob=0.34,
            save_rate_per90=0.0,
        ),
        3: PlayerBaseline(
            player_id=3,
            name="Milo Creator",
            team="BAY",
            position=Position.MID,
            ownership_top10k=0.58,
            xg_per90=0.34,
            xa_per90=0.28,
            clean_sheet_prob=0.19,
            save_rate_per90=0.0,
        ),
        4: PlayerBaseline(
            player_id=4,
            name="Ravi Runner",
            team="BAY",
            position=Position.MID,
            ownership_top10k=0.41,
            xg_per90=0.29,
            xa_per90=0.22,
            clean_sheet_prob=0.15,
            save_rate_per90=0.0,
        ),
        5: PlayerBaseline(
            player_id=5,
            name="Theo Finisher",
            team="CIT",
            position=Position.FWD,
            ownership_top10k=0.64,
            xg_per90=0.62,
            xa_per90=0.12,
            clean_sheet_prob=0.0,
            save_rate_per90=0.0,
        ),
        6: PlayerBaseline(
            player_id=6,
            name="Luca Poacher",
            team="CIT",
            position=Position.FWD,
            ownership_top10k=0.22,
            xg_per90=0.49,
            xa_per90=0.10,
            clean_sheet_prob=0.0,
            save_rate_per90=0.0,
        ),
    }


def default_top10k_state() -> Top10kModelState:
    return Top10kModelState(threshold_mean=1840.0, threshold_std=55.0, momentum_factor=0.25)


def default_squads() -> list[UserSquad]:
    return [
        UserSquad(
            team_id="alpha-analytics",
            overall_points_before_gw=1825,
            gameweek_live_points=18,
            picks=[
                UserPick(player_id=1, multiplier=1.0),
                UserPick(player_id=2, multiplier=1.0),
                UserPick(player_id=3, multiplier=2.0),
                UserPick(player_id=4, multiplier=1.0),
                UserPick(player_id=5, multiplier=1.0),
                UserPick(player_id=6, multiplier=1.0),
            ],
        ),
        UserSquad(
            team_id="template-hunter",
            overall_points_before_gw=1801,
            gameweek_live_points=16,
            picks=[
                UserPick(player_id=1, multiplier=1.0),
                UserPick(player_id=2, multiplier=1.0),
                UserPick(player_id=3, multiplier=1.0),
                UserPick(player_id=4, multiplier=1.0),
                UserPick(player_id=5, multiplier=2.0),
                UserPick(player_id=6, multiplier=1.0),
            ],
        ),
    ]
