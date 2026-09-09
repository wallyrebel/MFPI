from dataclasses import replace
from datetime import timedelta
import json

import pytest

from conftest import make_game, make_team
from mfpi.byes import confirmed_byes
from mfpi.config import Settings
from mfpi.engine import calculate_rankings
from mfpi.models import MaxPrepsScoreObservation
from mfpi.snapshots import load_previous


def schedule(cutoff):
    first = MaxPrepsScoreObservation(
        game_id="first", date=cutoff - timedelta(days=10), home_name="Alpha", away_name="Beta",
        home_score=21, away_score=7, status="COMPLETED", forfeit=False,
        source_url="https://www.maxpreps.com/game/one/", observed_from_team_id="alpha", retrieved_at=cutoff,
    )
    return [first, replace(first, game_id="next", date=cutoff + timedelta(days=2),
                           status="UPCOMING", home_score=None, away_score=None)]


def test_bye_requires_fresh_bracketed_empty_schedule(cutoff):
    observations = schedule(cutoff)
    assert confirmed_byes([], observations, cutoff, {"alpha"}) == {"alpha"}
    assert not confirmed_byes([], observations, cutoff, set())
    assert not confirmed_byes([], observations[:1], cutoff, {"alpha"})
    assert not confirmed_byes([], observations[1:], cutoff, {"alpha"})
    assert not confirmed_byes([], [], cutoff, {"alpha"})


@pytest.mark.parametrize("status", ["COMPLETED", "UPCOMING", "CANCELLED", "POSTPONED"])
def test_contest_in_week_blocks_bye(cutoff, status):
    observations = schedule(cutoff)
    recent = replace(observations[0], date=cutoff - timedelta(days=2), status=status)
    assert not confirmed_byes([], observations + [recent], cutoff, {"alpha"})
    official = replace(make_game("game", "alpha", "beta", 21, 7), date=recent.date, status=status)
    assert not confirmed_byes([official], observations, cutoff, {"alpha"})


def test_missing_old_score_is_not_bye(cutoff):
    missing = replace(make_game("old", "alpha", "beta", 21, 7),
                      date=cutoff - timedelta(days=10), verified=False)
    assert not confirmed_byes([missing], schedule(cutoff), cutoff, {"alpha"})


@pytest.mark.parametrize("previous_score", [25.0, 85.0])
def test_ninety_ten_is_symmetric_and_components_remain_auditable(cutoff, previous_score):
    teams = [make_team("Alpha"), make_team("Beta")]
    games = [make_game("one", "alpha", "beta", 21, 7)]
    raw = calculate_rankings(teams, games, cutoff, Settings())
    previous = {row.team.team_id: row.to_dict() for row in raw.rankings}
    previous["alpha"]["mfpi_unrounded"] = previous_score
    updated = calculate_rankings(teams, games, cutoff, Settings(), previous, confirmed_bye_team_ids={"alpha"})
    row = next(row for row in updated.rankings if row.team.team_id == "alpha")
    raw_score = next(row.mfpi for row in raw.rankings if row.team.team_id == "alpha")
    assert row.mfpi == pytest.approx(.9 * previous_score + .1 * raw_score)
    assert sum(item.contribution for item in row.components.values()) + row.bye_adjustment["adjustment"] == pytest.approx(row.mfpi)
    assert row.to_dict()["bye_adjustment"]["previous_weight"] == .9
    assert [r.mfpi for r in updated.rankings] == sorted((r.mfpi for r in updated.rankings), reverse=True)
    assert next(r for r in updated.rankings if r.team.team_id == "beta").bye_adjustment is None


@pytest.mark.parametrize("legacy", [False, True])
def test_score_corrections_and_new_games_bypass_protection(cutoff, legacy):
    teams = [make_team("Alpha"), make_team("Beta")]
    original = make_game("one", "alpha", "beta", 21, 7)
    prior_rows = calculate_rankings(teams, [original], cutoff, Settings()).rankings
    previous = {r.team.team_id: r.to_dict() for r in prior_rows}
    if legacy:
        for row in previous.values():
            row.pop("game_results")
    unchanged = calculate_rankings(teams, [original], cutoff, Settings(), previous, confirmed_bye_team_ids={"alpha"})
    assert next(r for r in unchanged.rankings if r.team.team_id == "alpha").bye_adjustment
    for games in ([replace(original, home_score=24)], [original, replace(original, game_id="two")]):
        result = calculate_rankings(teams, games, cutoff, Settings(), previous, confirmed_bye_team_ids={"alpha"})
        assert all(r.bye_adjustment is None for r in result.rankings)


def test_zero_games_and_missing_baseline_never_receive_protection(cutoff):
    teams = [make_team("Alpha"), make_team("Beta")]
    result = calculate_rankings(teams, [], cutoff, Settings())
    previous = {r.team.team_id: r.to_dict() for r in result.rankings}
    result = calculate_rankings(teams, [], cutoff, Settings(), previous, confirmed_bye_team_ids={"alpha"})
    assert all(r.bye_adjustment is None for r in result.rankings)


def test_changed_opponent_bypasses_protection_and_repeated_run_is_stable(cutoff):
    teams = [make_team(name) for name in ("Alpha", "Beta", "Gamma")]
    game = make_game("one", "alpha", "beta", 21, 7)
    previous = {r.team.team_id: r.to_dict() for r in calculate_rankings(teams, [game], cutoff, Settings()).rankings}
    previous["alpha"]["mfpi_unrounded"] = 80.0
    first = calculate_rankings(teams, [game], cutoff, Settings(), previous, confirmed_bye_team_ids={"alpha"})
    repeat = calculate_rankings(teams, [game], cutoff, Settings(), previous, confirmed_bye_team_ids={"alpha"})
    assert [r.to_dict() for r in first.rankings] == [r.to_dict() for r in repeat.rankings]
    changed = calculate_rankings(teams, [replace(game, away_team_id="gamma")], cutoff, Settings(), previous,
                                 confirmed_bye_team_ids={"alpha"})
    assert all(r.bye_adjustment is None for r in changed.rankings)


def test_latest_prior_week_revision_is_used_not_current_week(tmp_path):
    for path, value in [("week-01", 50), ("week-01/corrections/revision-01", 60), ("week-02", 99)]:
        directory = tmp_path / "2026" / path
        directory.mkdir(parents=True)
        (directory / "overall.json").write_text(json.dumps({"rankings": [{"team_id": "alpha", "mfpi": value}]}))
    assert load_previous(tmp_path, 2026, 2)["alpha"]["mfpi"] == 60
