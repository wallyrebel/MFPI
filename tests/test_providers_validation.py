from __future__ import annotations

import json
import pytest
from pathlib import Path
from dataclasses import replace
from datetime import datetime, timedelta, timezone

from mfpi.config import Settings
from mfpi.models import MaxPrepsRanking, MaxPrepsScoreObservation, Team, ValidationIssue
from mfpi.providers import (
    MHSAAClassificationProvider,
    MHSAAOfficialScoreProvider,
    MaxPrepsRankingProvider,
    MaxPrepsScoreProvider,
)
from mfpi.reconcile import reconcile_external_maxpreps_ratings, reconcile_maxpreps, supplement_games_with_maxpreps
from mfpi.matching import TeamMatcher
from mfpi.validation import can_show_provisional, validate_inputs

from conftest import make_game, make_team


def columbia_academies():
    # Source 231141 is the TN Bulldogs; 229414 is the MS Cougars.
    return [Team(f"external-{source_id}", "columbia academy", "Columbia Academy", None)
            for source_id in ("231141", "229414")]


@pytest.mark.parametrize("reverse", [False, True])
def test_secondary_shared_external_names_preserve_finals_and_recover_other_games(cutoff, reverse):
    external = columbia_academies()[:: -1 if reverse else 1]
    teams = [make_team("Alpha"), make_team("Beta"), *external]
    finals = [make_game("tn-final", "alpha", "external-231141", 42, 0),
              make_game("ms-final", "beta", "external-229414", 21, 14)]
    pending = replace(make_game("pending", "alpha", "beta", 0, 0),
                      home_score=None, away_score=None, verified=False, status="UPCOMING")
    observation = MaxPrepsScoreObservation(
        "other-final", pending.date, "Alpha", "Beta", 35, 14, "COMPLETED", False,
        "https://www.maxpreps.com/game/other-final/", "alpha", cutoff,
    )
    games, issues = supplement_games_with_maxpreps(teams, [*finals, pending], [observation], cutoff)
    assert games[:2] == finals
    assert games[2].completed and games[2].verified
    assert (games[2].home_score, games[2].away_score) == (35, 14)
    assert any(issue.code == "MAXPREPS_SECONDARY_RESULTS_USED" for issue in issues)


def test_secondary_shared_external_name_cannot_fill_either_school_by_guessing(cutoff):
    teams = [make_team("Alpha"), *columbia_academies()]
    pending = replace(make_game("pending", "alpha", "external-231141", 0, 0),
                      home_score=None, away_score=None, verified=False, status="UPCOMING")
    observation = MaxPrepsScoreObservation(
        "ambiguous-final", pending.date, "Alpha", "Columbia Academy", 42, 0,
        "COMPLETED", False, "https://www.maxpreps.com/game/ambiguous-final/", "alpha", cutoff,
    )
    games, issues = supplement_games_with_maxpreps(teams, [pending], [observation], cutoff)
    assert games == [pending]
    assert any(issue.code == "AMBIGUOUS_SECONDARY_TEAM_NAME" for issue in issues)
    matcher = TeamMatcher(teams, allow_external_name_collisions=True)
    assert matcher.match("Columbia Academy") == (None, 1.0, "ambiguous")
    assert matcher.match("Columbia Academi")[0] is None


def test_secondary_external_collision_option_keeps_official_aliases_strict():
    with pytest.raises(ValueError, match="Duplicate normalized alias"):
        TeamMatcher(columbia_academies())
    teams = [make_team("Columbia Academy"), *columbia_academies()]
    with pytest.raises(ValueError, match="Duplicate normalized alias"):
        TeamMatcher(teams, allow_external_name_collisions=True)


@pytest.mark.parametrize("reverse", [False, True])
def test_external_ratings_use_reviewed_profile_not_same_named_school_order(cutoff, reverse):
    teams = columbia_academies()[:: -1 if reverse else 1]
    profile = "/tn/columbia/columbia-academy-bulldogs/football/"
    observation = MaxPrepsScoreObservation(
        "tn-game", cutoff, "Alpha", "Columbia Academy", 42, 0, "COMPLETED", False,
        "https://www.maxpreps.com/game/tn-game/", "alpha", cutoff, away_url=profile,
    )
    ratings = {"tn": [MaxPrepsRanking(1, "Columbia Academy", "2-4", 50, 25, profile)]}
    assert reconcile_external_maxpreps_ratings(teams, [observation], ratings) == {"external-231141": 50}
    unknown = replace(observation, away_url="/tn/elsewhere/columbia-academy/football/")
    ratings["tn"].append(MaxPrepsRanking(2, "Columbia Academy", "1-5", 40, 20, unknown.away_url))
    assert reconcile_external_maxpreps_ratings(teams, [unknown], ratings) == {}


@pytest.mark.parametrize("source_id,profile", [
    ("231141", "/tn/columbia/columbia-academy-bulldogs/football/"),
    ("229414", "/ms/columbia/columbia-academy-cougars/football/"),
])
def test_secondary_reviewed_profile_recovers_only_correct_columbia_school(cutoff, source_id, profile):
    teams = [make_team("Alpha"), *columbia_academies()]
    pending = [replace(make_game(source, "alpha", f"external-{source}", 0, 0),
                       home_score=None, away_score=None, verified=False, status="UPCOMING")
               for source in ("231141", "229414")]
    observation = MaxPrepsScoreObservation(
        "reviewed-final", pending[0].date, "Alpha", "Columbia Academy", 42, 0,
        "COMPLETED", False, "https://www.maxpreps.com/game/reviewed-final/", "alpha", cutoff,
        away_url=profile,
    )
    games, _ = supplement_games_with_maxpreps(teams, pending, [observation], cutoff)
    assert [game.game_id for game in games if game.completed] == [source_id]
    assert games[0 if source_id == "229414" else 1] == pending[0 if source_id == "229414" else 1]


def test_official_classification_parser_and_duplicate_enterprise_hardening() -> None:
    rows = """
    <table><tr><th>School</th><th>Class</th><th>Region</th></tr>
    """ + "".join(f"<tr><td>School {i}</td><td>{1 + i % 7}</td><td>1</td></tr>" for i in range(150)) + """
    <tr><td>ENTERPRISE HIGH SCHOOL</td><td>2</td><td>6</td></tr>
    <tr><td>ENTERPRISE SCHOOL</td><td>2</td><td>7</td></tr></table>
    """
    teams = MHSAAClassificationProvider.parse(rows)
    ids = {team.team_id for team in teams}
    assert "enterprise-clarke" in ids
    assert "enterprise-brookhaven" in ids


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("profile,remove_stale", [
    ("/ms/brookhaven/enterprise-yellowjackets/football/", True),
    ("https://www.maxpreps.com/ms/brookhaven/enterprise-yellowjackets/football/", True),
    ("/ms/enterprise/enterprise-bulldogs/football/", False),
    ("/tn/brookhaven/enterprise-yellowjackets/football/", False),
    ("/ms/brookhaven/another-enterprise/football/", False),
    ("https://example.com/ms/brookhaven/enterprise-yellowjackets/football/", False),
    ("", False),
])
def test_enterprise_exact_profile_excludes_only_corroborated_bogue_chitto_stale_listing(reverse, profile, remove_stale):
    teams = [make_team("Bogue Chitto"), make_team("Enterprise Brookhaven"), make_team("Enterprise Clarke")]
    cutoff = datetime(2026, 10, 13, 16, tzinfo=timezone.utc)
    final = replace(make_game("7984799", "bogue-chitto", "enterprise-brookhaven", 32, 64),
                    date=datetime(2026, 10, 8, 19, tzinfo=timezone.utc), source="mhsaa_score_center")
    stale = replace(final, game_id="7615015", date=final.date + timedelta(days=1),
                    home_score=None, away_score=None, verified=False, status="UPCOMING")
    unrelated = replace(stale, game_id="unrelated-pending", home_team_id="enterprise-clarke",
                        away_team_id="enterprise-brookhaven")
    observation = MaxPrepsScoreObservation(
        "908f3d22-e875-463e-a250-2174fff232bf", final.date, "Bogue Chitto High School", "Enterprise High School",
        32, 64, "COMPLETED", False,
        "https://www.maxpreps.com/ms/football/game/bogue-chitto-vs-enterprise-brookhaven/10-8-2026/?c=908f3d22-e875-463e-a250-2174fff232bf",
        "bogue-chitto", cutoff, away_url=profile,
    )
    primary = [stale, final, unrelated] if reverse else [final, stale, unrelated]
    games, issues = supplement_games_with_maxpreps(teams, primary, [observation], cutoff)
    if remove_stale:
        assert games == [final, unrelated]
        assert len(issues) == 1 and issues[0].code == "STALE_RESCHEDULED_LISTING"
        assert issues[0].context["retained_mhsaa_game_id"] == "7984799"
    else:
        assert games == primary and not issues
    assert next(game for game in games if game.game_id == "7984799") == final


def test_enterprise_clarke_exact_profile_does_not_resolve_to_brookhaven(cutoff):
    teams = [make_team("Bay Springs"), make_team("Enterprise Brookhaven"), make_team("Enterprise Clarke")]
    pending = replace(make_game("clarke-final", "enterprise-clarke", "bay-springs", 0, 0),
                      home_score=None, away_score=None, verified=False, status="UPCOMING")
    observation = MaxPrepsScoreObservation(
        "clarke-event", pending.date, "Enterprise High School", "Bay Springs High School", 41, 22,
        "COMPLETED", False, "https://www.maxpreps.com/game/clarke/", "bay-springs", cutoff,
        home_url="/ms/enterprise/enterprise-bulldogs/football/",
    )
    games, _ = supplement_games_with_maxpreps(teams, [pending], [observation], cutoff)
    assert games[0].home_team_id == "enterprise-clarke" and games[0].home_score == 41


def test_inactive_football_program_is_not_ranked() -> None:
    rows = "<table>" + "".join(
        f"<tr><td>School {i}</td><td>{1 + i % 7}</td><td>1</td></tr>" for i in range(150)
    ) + "<tr><td>THRASHER HIGH SCHOOL</td><td>1</td><td>1</td></tr></table>"
    teams = MHSAAClassificationProvider.parse(rows)
    thrasher = next(team for team in teams if team.team_id == "thrasher")
    assert not thrasher.active
    assert not thrasher.ranked


def test_cached_classification_also_applies_inactive_override(tmp_path) -> None:
    cache = tmp_path / "teams.json"
    cache.write_text(json.dumps({"teams": [{
        "team_id": "thrasher", "canonical_name": "thrasher", "display_name": "Thrasher High School",
        "classification": "1A", "region": "1", "aliases": [], "active": True,
    }]}), encoding="utf-8")
    teams = MHSAAClassificationProvider().fetch(cache)
    assert not teams[0].active
    assert not teams[0].ranked


def test_bundled_classifications_work_without_network_or_cache(tmp_path) -> None:
    def offline(url):
        raise AssertionError("Classifications should load without network access")

    reference = Path(__file__).resolve().parents[1] / "data/reference/mhsaa_teams_2025_27.json"
    teams = MHSAAClassificationProvider(transport=offline).fetch(
        tmp_path / "missing-cache.json", fallback_path=reference,
    )
    published = json.loads((reference.parents[1] / "2026/week-01/overall.json").read_text())
    expected = {(row["team_id"], row["classification"], row["region"]) for row in published["rankings"]}
    assert {(team.team_id, team.classification, team.region) for team in teams if team.ranked} == expected


def test_refresh_bypasses_bundled_classifications(tmp_path) -> None:
    import pytest

    def offline(url):
        raise RuntimeError("Live refresh attempted")

    reference = Path(__file__).resolve().parents[1] / "data/reference/mhsaa_teams_2025_27.json"
    with pytest.raises(RuntimeError, match="Live refresh attempted"):
        MHSAAClassificationProvider(transport=offline).fetch(
            tmp_path / "missing-cache.json", refresh=True, fallback_path=reference,
        )


def test_score_provider_parses_home_away_score_and_status() -> None:
    nodes = [{
        "id": "42", "date": "2026-08-28T19:00:00-05:00", "status": "COMPLETED",
        "expectedStatus": "COMPLETED", "longStatusText": "Final OT", "contestTypeLabel": "Non Region",
        "contestParticipants": [
            {"location": "AWAY", "score": 17, "participant": {"__typename": "Team", "id": "2", "name": "Beta", "locationText": "B, MS"}},
            {"location": "HOME", "score": 20, "participant": {"__typename": "Team", "id": "1", "name": "Alpha", "locationText": "A, MS"}},
        ],
    }]
    games = MHSAAOfficialScoreProvider.parse_nodes(nodes, datetime.now(timezone.utc))
    assert games[0].home_name == "Alpha"
    assert games[0].away_score == 17
    assert games[0].overtime


def test_maxpreps_parser_reads_rank_rating_strength_and_url() -> None:
    html = """
    <table><tbody><tr><td class="rank">1</td><td class="team sticky-left">
    <a href="/ms/tupelo/tupelo-golden-wave/football/"><div class="photo-or-initial">T</div>Tupelo</a></td>
    <td class="overall">1-0</td><td class="rating">88.43</td>
    <td class="strength">39.3</td><td class="movement">--</td></tr></tbody></table>
    """
    rows = MaxPrepsRankingProvider.parse(html)
    assert rows == [MaxPrepsRanking(1, "Tupelo", "1-0", 88.43, 39.3, "/ms/tupelo/tupelo-golden-wave/football/")]


def test_maxpreps_schedule_parser_reads_result_forfeit_and_explicit_cancellation() -> None:
    html = """
    <script type="application/ld+json">{
      "@type":"SportsTeam",
      "event":[
        {"@type":"SportsEvent","url":"https://www.maxpreps.com/game/one/?c=one",
         "startDate":"2026-08-28T00:00:00+00:00","eventStatus":"https://schema.org/EventScheduled",
         "description":"On 8/27, the Beta varsity football team won their away game against Alpha by a score of 21-14.",
         "homeTeam":{"name":"Alpha High School","url":"https://www.maxpreps.com/ms/a/alpha/football/"},
         "awayTeam":{"name":"Beta High School","url":"https://www.maxpreps.com/ms/b/beta/football/"}},
        {"@type":"SportsEvent","url":"https://www.maxpreps.com/game/two/?c=two",
         "startDate":"2026-08-29T00:00:00+00:00","eventStatus":"https://schema.org/EventScheduled",
         "description":"On 8/28, Alpha lost by forfeit in their away game against Gamma.",
         "homeTeam":{"name":"Gamma High School","url":"https://www.maxpreps.com/ms/g/gamma/football/"},
         "awayTeam":{"name":"Alpha High School","url":"https://www.maxpreps.com/ms/a/alpha/football/"}},
        {"@type":"SportsEvent","url":"https://www.maxpreps.com/game/three/?c=three",
         "startDate":"2026-08-30T00:00:00+00:00","eventStatus":"https://schema.org/EventCancelled",
         "description":"The Alpha game against Delta was cancelled.",
         "homeTeam":{"name":"Alpha High School","url":"https://www.maxpreps.com/ms/a/alpha/football/"},
         "awayTeam":{"name":"Delta High School","url":"https://www.maxpreps.com/ms/d/delta/football/"}}
      ]
    }</script>
    """
    retrieved = datetime(2026, 9, 2, tzinfo=timezone.utc)
    games = MaxPrepsScoreProvider.parse(
        html,
        source_team_id="alpha",
        source_team_name="Alpha",
        source_team_url="/ms/a/alpha/football/",
        retrieved_at=retrieved,
    )
    assert [(game.game_id, game.status) for game in games] == [
        ("one", "COMPLETED"),
        ("two", "COMPLETED"),
        ("three", "CANCELLED"),
    ]
    assert (games[0].home_score, games[0].away_score) == (14, 21)
    assert games[0].away_url.endswith("/ms/b/beta/football/")
    assert (games[1].home_score, games[1].away_score, games[1].forfeit) == (2, 0, True)


def test_maxpreps_secondary_supplements_exact_pair_with_one_day_move(cutoff) -> None:
    teams = [make_team("Alpha"), make_team("Beta")]
    primary = replace(
        make_game("mhsaa-1", "alpha", "beta", 0, 0),
        home_score=None,
        away_score=None,
        status="UPCOMING",
        verified=False,
    )
    observation = MaxPrepsScoreObservation(
        game_id="maxpreps-1",
        date=primary.date - timedelta(days=1),
        home_name="Alpha High School",
        away_name="Beta High School",
        home_score=35,
        away_score=14,
        status="COMPLETED",
        forfeit=False,
        source_url="https://www.maxpreps.com/game/one/",
        observed_from_team_id="alpha",
        retrieved_at=datetime(2026, 9, 2, tzinfo=timezone.utc),
    )
    games, issues = supplement_games_with_maxpreps(teams, [primary], [observation], cutoff)
    assert games[0].completed and games[0].verified
    assert (games[0].home_score, games[0].away_score) == (35, 14)
    assert games[0].source == "maxpreps_secondary"
    assert any(issue.code == "MAXPREPS_SECONDARY_RESULTS_USED" for issue in issues)


def test_maxpreps_secondary_rejects_conflicting_reports(cutoff) -> None:
    teams = [make_team("Alpha"), make_team("Beta")]
    primary = replace(
        make_game("mhsaa-1", "alpha", "beta", 0, 0),
        home_score=None,
        away_score=None,
        status="UPCOMING",
        verified=False,
    )
    base = MaxPrepsScoreObservation(
        game_id="maxpreps-1",
        date=primary.date,
        home_name="Alpha",
        away_name="Beta",
        home_score=21,
        away_score=14,
        status="COMPLETED",
        forfeit=False,
        source_url="https://www.maxpreps.com/game/one/",
        observed_from_team_id="alpha",
        retrieved_at=datetime(2026, 9, 2, tzinfo=timezone.utc),
    )
    conflict = replace(base, home_score=24, source_url="https://www.maxpreps.com/game/two/")
    games, issues = supplement_games_with_maxpreps(teams, [primary], [base, conflict], cutoff)
    assert not games[0].completed
    assert any(issue.code == "MAXPREPS_SCORE_CONFLICT" and issue.severity == "CRITICAL" for issue in issues)


def test_maxpreps_reconciliation_requires_every_active_team() -> None:
    teams = [make_team("Alpha"), make_team("Beta")]
    signals, issues = reconcile_maxpreps(teams, [MaxPrepsRanking(1, "Alpha", "1-0", 70.0, 30.0)])
    assert set(signals) == {"alpha"}
    assert any(issue.code == "MISSING_MAXPREPS_TEAMS" and issue.severity == "CRITICAL" for issue in issues)


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("active_url", [
    "/local/team/home.aspx?schoolid=80480779-619d-4cd9-9feb-c26005e4201f&season=fall",
    "/ms/carthage/leake-gators/football/",
])
def test_consolidated_leake_profile_replaces_only_retired_placeholder(reverse, active_url) -> None:
    teams = [make_team("Leake Central")]
    old = MaxPrepsRanking(82, "Leake Central", "0-0", 47.67, 0.0,
                         "/ms/carthage/leake-central-gators/football/")
    active = MaxPrepsRanking(139, "Leake", "2-0", 38.61, 10.3,
                            active_url)
    rows = [active, old] if reverse else [old, active]
    signals, issues = reconcile_maxpreps(teams, rows)
    assert signals["leake-central"].rating == 38.61
    assert [issue.code for issue in issues] == ["RETIRED_MAXPREPS_PROFILE"]
    _, issues = reconcile_maxpreps(teams, [replace(old, record="1-0"), active])
    assert any(issue.code == "DUPLICATE_MAXPREPS_TEAM" for issue in issues)
    _, issues = reconcile_maxpreps(teams, [old, replace(active, team_url="/unknown/")])
    assert any(issue.code == "DUPLICATE_MAXPREPS_TEAM" for issue in issues)


def test_empty_secondary_schedule_does_not_replace_a_readable_cache(tmp_path) -> None:
    from mfpi.models import MaxPrepsSignal
    cache = tmp_path / "alpha.json"
    retrieved = datetime(2026, 9, 1, tzinfo=timezone.utc)
    observation = MaxPrepsScoreObservation(
        "one", retrieved, "Alpha", "Beta", 21, 14, "COMPLETED", False,
        "https://www.maxpreps.com/game/one/", "alpha", retrieved,
    )
    cache.write_text(json.dumps({"retrieved_at": retrieved.isoformat(),
                                 "games": [observation.to_dict()]}))
    signal = MaxPrepsSignal("alpha", 1, 70, 30, "Alpha", "/ms/a/alpha/football/")
    fetched = MaxPrepsScoreProvider(transport=lambda url: b"<html>Unavailable</html>").fetch({"alpha": signal}, tmp_path)
    assert fetched.games == [observation]
    assert fetched.cached_team_ids == ("alpha",)
    assert json.loads(cache.read_text())["games"] == [observation.to_dict()]
    cache.unlink()
    fetched = MaxPrepsScoreProvider(transport=lambda url: b"<html>Unavailable</html>").fetch({"alpha": signal}, tmp_path)
    assert fetched.failed_team_ids == ("alpha",)
    assert not cache.exists()


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("conflicting", [False, True])
def test_rescheduled_listing_does_not_double_count_corroborated_official_final(cutoff, reverse, conflicting) -> None:
    teams = [make_team("Alpha"), make_team("Beta")]
    final = make_game("official-final", "alpha", "beta", 21, 14)
    stale = replace(final, game_id="old-listing", date=final.date + timedelta(days=1),
                    status="UPCOMING", verified=False, home_score=None, away_score=None)
    observation = MaxPrepsScoreObservation(
        game_id="secondary", date=final.date, home_name="Beta", away_name="Alpha",
        home_score=14, away_score=24 if conflicting else 21, status="COMPLETED", forfeit=False,
        source_url="https://www.maxpreps.com/game/one/", observed_from_team_id="alpha",
        retrieved_at=cutoff,
    )
    primary = [stale, final] if reverse else [final, stale]
    games, issues = supplement_games_with_maxpreps(teams, primary, [observation], cutoff)
    if conflicting:
        assert len(games) == 2
        assert any(issue.code == "MAXPREPS_SCORE_CONFLICT" for issue in issues)
        assert not validate_inputs(teams, games, cutoff, Settings(), issues).valid
        assert not any(game.completed and game.verified for game in games)
    else:
        assert games == [final]
        assert [issue.code for issue in issues] == ["STALE_RESCHEDULED_LISTING"]
        report = validate_inputs(teams, games, cutoff, Settings(), issues)
        assert report.valid and report.verified_games == report.expected_games == 1


def test_rescheduled_listing_needs_independent_evidence(cutoff) -> None:
    teams = [make_team("Alpha"), make_team("Beta")]
    final = make_game("official-final", "alpha", "beta", 21, 14)
    stale = replace(final, game_id="old-listing", date=final.date + timedelta(days=1),
                    status="UPCOMING", verified=False, home_score=None, away_score=None)
    games, issues = supplement_games_with_maxpreps(teams, [final, stale], [], cutoff)
    assert games == [final, stale]
    assert not issues


@pytest.mark.parametrize("reverse", [False, True])
@pytest.mark.parametrize("evidence", [False, True])
@pytest.mark.parametrize("conflicting", [False, True])
def test_completed_reschedule_duplicates_require_corroborated_date_and_score(cutoff, reverse, evidence, conflicting):
    teams = [make_team("Alpha"), make_team("Beta")]
    final = make_game("actual-final", "alpha", "beta", 27, 24)
    stale = replace(final, game_id="stale-final", date=final.date + timedelta(days=1),
                    home_team_id="beta", away_team_id="alpha", home_score=24, away_score=28 if conflicting else 27)
    observation = MaxPrepsScoreObservation(
        "secondary-final", final.date, "Beta", "Alpha", 24, 27, "COMPLETED", False,
        "https://www.maxpreps.com/game/actual/", "alpha", cutoff,
    )
    primary = [stale, final] if reverse else [final, stale]
    games, issues = supplement_games_with_maxpreps(teams, primary, [observation] if evidence else [], cutoff)
    if not evidence:
        assert games == primary and not issues
    elif conflicting:
        assert len(games) == 2 and not any(game.completed and game.verified for game in games)
        assert any(issue.code == "MAXPREPS_SCORE_CONFLICT" for issue in issues)
    else:
        assert games == [final]
        assert [issue.code for issue in issues] == ["STALE_RESCHEDULED_LISTING"]


def test_validation_blocks_low_coverage_and_impossible_scores(cutoff) -> None:
    teams = [make_team("Alpha"), make_team("Beta")]
    games = [make_game("bad", "alpha", "beta", 151, 0)]
    games.append(type(games[0])(**{**games[0].__dict__, "game_id": "missing", "home_score": None, "away_score": None, "status": "UPCOMING", "verified": False}))
    report = validate_inputs(teams, games, cutoff, Settings(), [ValidationIssue("PRECHECK", "WARNING", "test")])
    codes = {issue.code for issue in report.issues}
    assert {"IMPOSSIBLE_SCORE", "LOW_GAME_COVERAGE", "PRECHECK"} <= codes
    assert not report.valid
    assert not can_show_provisional(report)


def test_validation_accepts_complete_verified_data(cutoff) -> None:
    teams = [make_team("Alpha"), make_team("Beta")]
    games = [make_game("ok", "alpha", "beta", 21, 14)]
    report = validate_inputs(teams, games, cutoff, Settings())
    assert report.valid
    assert report.coverage == 1.0
    assert not can_show_provisional(report)


def test_low_coverage_alone_is_safe_to_show_as_provisional(cutoff) -> None:
    teams = [make_team("Alpha"), make_team("Beta")]
    game = make_game("missing", "alpha", "beta", 21, 14)
    missing = type(game)(**{
        **game.__dict__,
        "home_score": None,
        "away_score": None,
        "status": "UPCOMING",
        "verified": False,
    })
    report = validate_inputs(teams, [missing], cutoff, Settings())
    assert not report.valid
    assert can_show_provisional(report)


def test_unverified_games_above_threshold_remain_visible_as_warning(cutoff) -> None:
    teams = [make_team("Alpha"), make_team("Beta")]
    complete = make_game("ok", "alpha", "beta", 21, 14)
    missing = replace(
        complete,
        game_id="missing",
        date=complete.date + timedelta(days=1),
        home_score=None,
        away_score=None,
        status="UPCOMING",
        verified=False,
    )
    report = validate_inputs(teams, [complete, missing], cutoff, Settings(coverage_threshold=0.5))
    assert report.valid
    assert any(issue.code == "UNVERIFIED_GAMES_REMAIN" and issue.severity == "WARNING" for issue in report.issues)
