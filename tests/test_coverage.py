from __future__ import annotations

import json
from dataclasses import replace
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from conftest import make_game, make_team
from mfpi.config import CENTRAL, Settings
from mfpi.coverage import audit_schedule_coverage
from mfpi.engine import calculate_rankings
from mfpi.models import MaxPrepsScoreObservation, MaxPrepsSignal
from mfpi.providers import MHSAAClassificationProvider, MHSAAOfficialScoreProvider
from mfpi.reconcile import reconcile_games, supplement_games_with_maxpreps


ROOT = Path(__file__).resolve().parents[1]


def test_verified_northside_legacy_identity_recovers_four_official_results_without_duplicates() -> None:
    payload = json.loads((ROOT / "tests/fixtures/northside_2026.json").read_text())
    retrieved = datetime.fromisoformat(payload["retrieved_at"])
    official = MHSAAClassificationProvider().fetch(ROOT / "data/reference/mhsaa_teams_2025_27.json")
    raw = MHSAAOfficialScoreProvider.parse_nodes(payload["primary_nodes"], retrieved)
    teams, games, issues = reconcile_games(official, raw)
    assert len(games) == 4
    assert all("northside" in {g.home_team_id, g.away_team_id} for g in games)
    assert not any(t.team_id == "external-243751" for t in teams)
    northside = next(t for t in teams if t.team_id == "northside")
    assert (northside.city, northside.source_team_id) == ("Shelby", "243751")
    assert [i.code for i in issues] == ["REVIEWED_IDENTITY_APPLIED"]
    observations = [MaxPrepsScoreObservation(**{
        **r, "date": datetime.fromisoformat(r["date"]), "retrieved_at": datetime.fromisoformat(r["retrieved_at"]),
    }) for r in payload["secondary_observations"]]
    cutoff = datetime(2026, 9, 29, 11, tzinfo=CENTRAL)
    supplemented, _ = supplement_games_with_maxpreps(teams, games, observations, cutoff)
    assert supplemented == games
    result = calculate_rankings(teams, games, cutoff, Settings(week=5))
    row = next(r for r in result.rankings if r.team.team_id == "northside")
    assert (row.games_played, row.record, row.points_for, row.points_against) == (4, "3-1", 119, 30)
    assert reconcile_games(official, raw)[1] == games


@pytest.mark.parametrize("changes", [
    {"away_source_id": "999"}, {"away_city": "Memphis"}, {"away_city": ""},
    {"source": "other_source"}, {"away_name": "Broad Street Academy"},
])
def test_northside_mapping_requires_exact_source_id_name_and_shelby(changes) -> None:
    payload = json.loads((ROOT / "tests/fixtures/northside_2026.json").read_text())
    raw = MHSAAOfficialScoreProvider.parse_nodes(payload["primary_nodes"], datetime.fromisoformat(payload["retrieved_at"]))[0]
    assert raw.away_name == "Broad Street"
    teams = [make_team("Northside"), make_team("Jefferson County")]
    _, games, _ = reconcile_games(teams, [replace(raw, **changes)])
    assert games[0].away_team_id.startswith("external-")


def sources():
    return {t: MaxPrepsSignal(t, i + 1, 70, 30, t.title(), f"/ms/{t}/{t}/football/")
            for i, t in enumerate(["alpha", "beta"])}


def observation(cutoff):
    return MaxPrepsScoreObservation(
        "secondary", cutoff - timedelta(days=4), "Alpha", "Beta", 21, 14,
        "COMPLETED", False, "https://www.maxpreps.com/game/one/", "alpha", cutoff,
        "/ms/alpha/alpha/football/", "/ms/beta/beta/football/",
    )


def audit(games, observations, cutoff, fresh=None):
    return audit_schedule_coverage([make_team("Alpha"), make_team("Beta")], games, observations,
                                   sources(), cutoff, date(2026, 8, 27), {"alpha", "beta"} if fresh is None else fresh)


def test_schedule_audit_detects_a_game_completely_absent_from_primary_feed(cutoff) -> None:
    item = observation(cutoff)
    issues = audit([], [item, replace(item, observed_from_team_id="beta")], cutoff)
    assert [i.code for i in issues] == ["MISSING_PRIMARY_SCHEDULE_GAME"]
    assert issues[0].severity == "CRITICAL"
    assert issues[0].context["observed_from_team_ids"] == ["alpha", "beta"]


def test_schedule_audit_reports_legacy_external_identity_without_adding_a_duplicate(cutoff) -> None:
    item = observation(cutoff)
    game = replace(make_game("official", "alpha", "external-old", 21, 14), date=item.date)
    issues = audit([game], [item], cutoff)
    assert [i.code for i in issues] == ["MISSING_PRIMARY_SCHEDULE_GAME"]
    assert game.away_team_id == "external-old"


def test_schedule_audit_uses_profile_urls_to_keep_same_named_out_of_state_team_external(cutoff) -> None:
    item = replace(observation(cutoff), away_url="https://www.maxpreps.com/tn/beta/beta/football/")
    game = replace(make_game("official", "alpha", "external-beta", 21, 14), date=item.date)
    assert not audit([game], [item], cutoff)
    issues = audit([], [item], cutoff)
    assert [i.code for i in issues] == ["SECONDARY_OPPONENT_UNRESOLVED"]


def test_schedule_audit_detects_conflicting_final_but_retains_primary(cutoff) -> None:
    item = observation(cutoff)
    game = replace(make_game("official", "alpha", "beta", 24, 14), date=item.date)
    issues = audit([game], [item], cutoff)
    assert [i.code for i in issues] == ["PRIMARY_SECONDARY_SCORE_DISAGREEMENT"]
    assert game.home_score == 24


def test_schedule_audit_excludes_future_preseason_and_cached_observations(cutoff) -> None:
    item = observation(cutoff)
    assert not audit([], [replace(item, date=cutoff + timedelta(days=1))], cutoff)
    assert not audit([], [replace(item, date=datetime(2026, 8, 21, tzinfo=CENTRAL))], cutoff)
    assert not audit([], [item], cutoff, fresh=set())


def test_schedule_audit_accepts_reversed_primary_sides_and_one_day_reschedule(cutoff) -> None:
    item = observation(cutoff)
    game = replace(make_game("official", "beta", "alpha", 14, 21), date=item.date + timedelta(days=1))
    assert not audit([game], [item], cutoff)


def test_schedule_audit_reports_conflicting_secondary_reports_once(cutoff) -> None:
    item = observation(cutoff)
    issues = audit([], [item, replace(item, home_score=24, observed_from_team_id="beta")], cutoff)
    assert [i.code for i in issues] == ["SECONDARY_SCHEDULE_DISAGREEMENT"]
