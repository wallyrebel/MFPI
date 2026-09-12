from __future__ import annotations

import math
from datetime import datetime

from mfpi.config import CENTRAL, class_prior_points, ranking_week, weights_for_games
from mfpi.normalize import robust_percentiles
from mfpi.srs import adjusted_margin, solve_srs

from conftest import make_game


def test_margin_cap_has_diminishing_returns() -> None:
    margin_42 = adjusted_margin(42, "NEUTRAL")
    margin_70 = adjusted_margin(70, "NEUTRAL")
    margin_140 = adjusted_margin(140, "NEUTRAL")
    assert margin_42 < margin_70 < margin_140 < 42
    assert margin_140 - margin_70 < margin_70 - margin_42


def test_home_field_adjustment_rewards_same_road_margin() -> None:
    assert adjusted_margin(21, "AWAY") - adjusted_margin(21, "HOME") == 4.0
    assert adjusted_margin(21, "NEUTRAL") == (adjusted_margin(21, "AWAY") + adjusted_margin(21, "HOME")) / 2


def test_srs_converges_and_is_centered() -> None:
    games = [
        make_game("1", "a", "b", 28, 14),
        make_game("2", "b", "c", 21, 7),
        make_game("3", "c", "a", 17, 14),
    ]
    ratings, iterations, converged = solve_srs(
        {"a", "b", "c"}, games, {"a": 0, "b": 0, "c": 0},
        {"a": 1, "b": 1, "c": 1}, {"a", "b", "c"},
    )
    assert converged
    assert iterations < 100
    assert abs(sum(ratings.values())) < 1e-9


def test_normalization_handles_ties_missing_and_outlier() -> None:
    values = robust_percentiles({"low": 0.0, "tie1": 10.0, "tie2": 10.0, "outlier": 1_000_000.0, "missing": None})
    assert values["low"] == 0.0
    assert values["tie1"] == values["tie2"] == 50.0
    assert values["outlier"] == 100.0
    assert values["missing"] == 50.0


def test_field_performance_weights_sum_to_one() -> None:
    assert math.isclose(weights_for_games(0)["performance"], 0.35)
    assert math.isclose(weights_for_games(4)["sos"], 0.20)
    assert math.isclose(weights_for_games(8)["maxpreps_rank"], 0.10)
    assert math.isclose(weights_for_games(8)["maxpreps_sos"], 0.10)
    assert math.isclose(weights_for_games(8)["offense"], 0.08)
    assert all(math.isclose(sum(weights_for_games(games).values()), 1.0) for games in (0, 2, 3, 5, 6, 12))


def test_class_prior_orders_7a_through_1a_and_is_centered() -> None:
    values = [class_prior_points(f"{number}A") for number in range(1, 8)]
    assert values == sorted(values)
    assert values[0] == -values[-1]
    assert class_prior_points(None) == 0.0


def test_ranking_week_changes_only_at_central_cutoff() -> None:
    # The boundary is Tuesday 11:00 Central, and the scheduled workflow runs at
    # that same moment. A run even a minute early would recompute the week that
    # is already published, so the edges matter.
    assert ranking_week(datetime(2026, 9, 8, 10, 59, tzinfo=CENTRAL)) == 1
    assert ranking_week(datetime(2026, 9, 8, 11, 0, tzinfo=CENTRAL)) == 2
    assert ranking_week(datetime(2026, 9, 15, 10, 59, tzinfo=CENTRAL)) == 2
    assert ranking_week(datetime(2026, 9, 15, 11, 0, tzinfo=CENTRAL)) == 3


def test_ranking_week_boundary_holds_across_dst() -> None:
    # Central time leaves DST on 1 November 2026; the cron carries the same
    # America/Chicago timezone, so both must stay on the 11:00 wall clock.
    from mfpi.config import Settings

    for week in (9, 10):
        cutoff = Settings(season=2026, week=week).default_cutoff()
        assert cutoff.strftime("%A") == "Tuesday"
        assert (cutoff.hour, cutoff.minute) == (11, 0)
