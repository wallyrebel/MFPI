from __future__ import annotations

from mfpi.config import Settings
from mfpi.engine import calculate_rankings
from mfpi.srs import adjusted_margin

from conftest import make_game, make_team


def _rows(result):
    return {row.team.team_id: row for row in result.rankings}


def test_quality_win_beats_blowout_of_terrible_opponent(cutoff) -> None:
    teams = [make_team(name) for name in ("Elite", "Contender", "Crusher", "Weak", "Average One", "Average Two", "Average Three")]
    games = [
        make_game("elite-1", "elite", "average-one", 35, 14),
        make_game("elite-2", "elite", "average-two", 35, 14),
        make_game("elite-3", "elite", "average-three", 35, 14),
        make_game("weak-1", "average-one", "weak", 28, 7),
        make_game("weak-2", "average-two", "weak", 28, 7),
        make_game("weak-3", "average-three", "weak", 28, 7),
        make_game("quality", "contender", "elite", 20, 10),
        make_game("blowout", "crusher", "weak", 30, 0),
    ]
    result = calculate_rankings(teams, games, cutoff, Settings())
    rows = _rows(result)
    assert rows["contender"].mfpi > rows["crusher"].mfpi
    assert rows["contender"].components["sos"].normalized > rows["crusher"].components["sos"].normalized


def test_close_loss_to_elite_can_rate_above_small_win_over_weak(cutoff) -> None:
    teams = [make_team(name) for name in ("Elite", "Close Loss", "Small Win", "Weak")]
    games = [
        make_game("elite-weak", "elite", "weak", 49, 0),
        make_game("close", "elite", "close-loss", 21, 18),
        make_game("small", "small-win", "weak", 17, 14),
    ]
    result = calculate_rankings(teams, games, cutoff, Settings())
    rows = _rows(result)
    assert rows["close-loss"].components["performance"].normalized > rows["small-win"].components["performance"].normalized
    assert rows["close-loss"].mfpi > rows["small-win"].mfpi


def test_weak_undefeated_team_can_rank_below_one_loss_elite_schedule(cutoff) -> None:
    names = ("Elite", "Strong", "Tested", "Unbeaten", "Cupcake One", "Cupcake Two", "Cupcake Three")
    teams = [make_team(name) for name in names]
    games = [
        make_game("tested-loss", "elite", "tested", 24, 21),
        make_game("tested-win", "tested", "strong", 28, 24),
        make_game("elite-strong", "elite", "strong", 35, 14),
        make_game("weak-1", "unbeaten", "cupcake-one", 14, 7),
        make_game("weak-2", "unbeaten", "cupcake-two", 14, 10),
        make_game("weak-3", "unbeaten", "cupcake-three", 7, 3),
        make_game("cup-1", "strong", "cupcake-one", 42, 0),
        make_game("cup-2", "strong", "cupcake-two", 38, 0),
        make_game("cup-3", "strong", "cupcake-three", 35, 0),
    ]
    result = calculate_rankings(teams, games, cutoff, Settings())
    rows = _rows(result)
    assert rows["tested"].record == "1-1"
    assert rows["unbeaten"].record == "3-0"
    assert rows["tested"].components["sos"].normalized > rows["unbeaten"].components["sos"].normalized
    assert rows["tested"].mfpi > rows["unbeaten"].mfpi


def test_seventy_point_win_does_not_create_unlimited_credit() -> None:
    forty_two = adjusted_margin(42, "NEUTRAL")
    seventy = adjusted_margin(70, "NEUTRAL")
    assert seventy < 42
    assert seventy - forty_two < 10
