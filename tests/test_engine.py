from __future__ import annotations

from mfpi.config import Settings
from mfpi.engine import calculate_rankings
from mfpi.matching import TeamMatcher, normalize_name
from mfpi.models import MaxPrepsSignal

from conftest import make_game, make_team


def test_alias_normalization_is_aggressive_but_deterministic() -> None:
    teams = [make_team("St. Martin"), make_team("D'Iberville"), make_team("East Union"), make_team("Leake Central")]
    matcher = TeamMatcher(teams)
    assert matcher.match("Saint Martin High School")[0].team_id == "st.-martin"
    assert matcher.match("Diberville Senior High Sch")[0].team_id == "d'iberville"
    assert matcher.match("East Union Attendance Center")[0].team_id == "east-union"
    assert matcher.match("Leake High School")[0].team_id == "leake-central"
    assert normalize_name("O’Bannon High School") == normalize_name("O'Bannon")


def test_record_tie_offense_defense_and_forfeit_components(cutoff) -> None:
    teams = [make_team("Alpha"), make_team("Beta")]
    games = [make_game("tie", "alpha", "beta", 21, 21), make_game("forfeit", "alpha", "beta", 1, 0, forfeit=True)]
    result = calculate_rankings(teams, games, cutoff, Settings())
    alpha = next(row for row in result.rankings if row.team.team_id == "alpha")
    assert alpha.record == "1-0-1"
    assert alpha.points_for == 22
    assert alpha.points_against == 21
    assert alpha.components["record"].raw == 0.75


def test_zero_game_team_is_neutral_for_game_only_components(cutoff) -> None:
    teams = [make_team("Alpha"), make_team("Beta"), make_team("Idle")]
    games = [make_game("1", "alpha", "beta", 14, 7)]
    result = calculate_rankings(teams, games, cutoff, Settings())
    idle = next(row for row in result.rankings if row.team.team_id == "idle")
    assert idle.games_played == 0
    for component in ("record", "offense", "defense", "recent", "sos", "maxpreps_rank", "maxpreps_sos"):
        assert idle.components[component].normalized == 50.0


def test_classification_prior_keeps_zero_external_data_calculation_functional(cutoff) -> None:
    teams = [make_team("Alpha"), make_team("Beta")]
    result = calculate_rankings(teams, [make_game("1", "alpha", "beta", 28, 14)], cutoff, Settings())
    assert len(result.rankings) == 2
    assert all(1 <= row.mfpi <= 100 for row in result.rankings)


def test_published_external_rating_seeds_opponent_adjusted_performance(cutoff) -> None:
    teams = [make_team("Tupelo", "6A"), make_team("Other MS", "6A"), make_team("Elite Alabama", None)]
    games = [
        make_game("cross-state", "tupelo", "elite-alabama", 21, 14),
        make_game("in-state", "other-ms", "elite-alabama", 7, 14),
    ]
    neutral = calculate_rankings(teams, games, cutoff, Settings())
    rated = calculate_rankings(teams, games, cutoff, Settings(), external_ratings={"elite-alabama": 92.0})
    assert rated.srs["elite-alabama"] > neutral.srs["elite-alabama"]


def test_weekly_movement_and_class_rank_use_same_score(cutoff) -> None:
    teams = [make_team("Alpha", "4A"), make_team("Beta", "4A"), make_team("Gamma", "5A")]
    games = [make_game("1", "alpha", "beta", 28, 14), make_game("2", "gamma", "alpha", 21, 20)]
    previous = {
        "alpha": {"state_rank": 3, "class_rank": 2, "mfpi_unrounded": 50.0},
        "beta": {"state_rank": 2, "class_rank": 1, "mfpi_unrounded": 55.0},
        "gamma": {"state_rank": 1, "class_rank": 1, "mfpi_unrounded": 60.0},
    }
    result = calculate_rankings(teams, games, cutoff, Settings(), previous)
    alpha = next(row for row in result.rankings if row.team.team_id == "alpha")
    assert alpha.to_dict()["state_rank_change"] == 3 - alpha.state_rank
    assert alpha.to_dict()["class_rank_change"] == 2 - alpha.class_rank
    assert [row.mfpi for row in result.rankings] == sorted((row.mfpi for row in result.rankings), reverse=True)


def test_recent_form_uses_opponent_adjusted_game_performance(cutoff) -> None:
    teams = [make_team(name) for name in ("Alpha", "Beta", "Gamma", "Delta")]
    games = [
        make_game("1", "alpha", "delta", 35, 7),
        make_game("2", "alpha", "gamma", 24, 21),
        make_game("3", "beta", "delta", 21, 20),
        make_game("4", "beta", "gamma", 17, 14),
    ]
    result = calculate_rankings(teams, games, cutoff, Settings())
    alpha = next(row for row in result.rankings if row.team.team_id == "alpha")
    beta = next(row for row in result.rankings if row.team.team_id == "beta")
    assert alpha.components["recent"].raw != beta.components["recent"].raw


def test_playing_up_is_recorded_and_rewards_same_margin(cutoff) -> None:
    teams = [
        make_team("Up Winner", "4A"),
        make_team("Down Winner", "4A"),
        make_team("Big School", "7A"),
        make_team("Small School", "1A"),
    ]
    games = [
        make_game("up", "up-winner", "big-school", 21, 14),
        make_game("down", "down-winner", "small-school", 21, 14),
    ]
    result = calculate_rankings(teams, games, cutoff, Settings())
    rows = {row.team.team_id: row for row in result.rankings}
    assert rows["up-winner"].up_games == 1
    assert rows["up-winner"].schedule_direction == "Playing up"
    assert rows["down-winner"].down_games == 1
    assert rows["up-winner"].components["performance"].raw > rows["down-winner"].components["performance"].raw
    assert rows["up-winner"].mfpi > rows["down-winner"].mfpi


def test_maxpreps_rank_and_strength_contribute_twenty_percent(cutoff) -> None:
    teams = [make_team("Alpha"), make_team("Beta")]
    signals = {
        "alpha": MaxPrepsSignal("alpha", 1, 80.0, 40.0, "Alpha"),
        "beta": MaxPrepsSignal("beta", 2, 60.0, 20.0, "Beta"),
    }
    result = calculate_rankings(teams, [], cutoff, Settings(), maxpreps=signals)
    rows = {row.team.team_id: row for row in result.rankings}
    assert rows["alpha"].components["maxpreps_rank"].weight == 0.10
    assert rows["alpha"].components["maxpreps_sos"].weight == 0.10
    assert rows["alpha"].components["maxpreps_rank"].normalized == 100.0
    assert rows["alpha"].components["maxpreps_sos"].normalized == 100.0
    assert rows["alpha"].maxpreps_state_rank == 1
    assert rows["alpha"].mfpi > rows["beta"].mfpi
