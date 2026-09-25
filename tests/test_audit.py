"""Acceptance tests for the publication audit, game statuses and identity rules.

All data here is synthetic and lives only in this file; nothing touches the
published snapshots under data/.
"""

from __future__ import annotations

import copy
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone

import pytest

from conftest import make_game, make_team
from mfpi.audit import BLOCKING, INFO, WARNING, audit_snapshot
from mfpi.config import CENTRAL, Settings
from mfpi.dates import calendar_date, calendar_date_from_snapshot
from mfpi.engine import calculate_rankings
from mfpi.explain import rank_sentence, rating_sentence
from mfpi.game_status import (
    CANCELED, EXHIBITION, FINAL, FORFEIT, IN_PROGRESS, NO_CONTEST, POSTPONED,
    SCHEDULED, SUSPENDED, UNRESOLVED, counts_toward_record, counts_toward_scoring, status_category,
)
from mfpi.models import RankingRow, RawGame
from mfpi.reconcile import reconcile_games
from mfpi.snapshots import game_ledger, preview_payload
from mfpi.validation import validate_inputs


def build(teams, games, cutoff, previous=None, status="PUBLISHED"):
    settings = Settings()
    result = calculate_rankings(teams, games, cutoff, settings, previous)
    report = validate_inputs(teams, games, cutoff, settings)
    payload = preview_payload(
        season=2026, week=2 if previous else 1, cutoff=cutoff, generated_at=cutoff, status=status,
        teams=teams, games=games, rankings=result.rankings, report=report,
    )
    return payload, game_ledger(teams, games, result.rankings, cutoff), result


def codes(report, severity=None):
    return {issue.code for issue in report.issues if severity is None or issue.severity == severity}


@pytest.fixture
def league(cutoff):
    teams = [make_team("Alpha"), make_team("Beta"), make_team("Gamma"), make_team("Delta")]
    games = [
        make_game("g1", "alpha", "beta", 28, 14),
        make_game("g2", "gamma", "delta", 21, 20),
    ]
    return teams, games


# --- dates -------------------------------------------------------------------

def test_friday_night_game_stays_on_friday() -> None:
    friday_7pm = datetime(2026, 8, 28, 19, 0, tzinfo=CENTRAL)
    assert calendar_date(friday_7pm) == date(2026, 8, 28)
    # Formatting the same instant in UTC would say Saturday; calendar_date must not.
    assert friday_7pm.astimezone(timezone.utc).date() == date(2026, 8, 29)


def test_date_only_marker_in_western_offset_keeps_source_date() -> None:
    pacific = timezone(timedelta(hours=-7))
    marker = datetime(2026, 8, 28, 23, 59, tzinfo=pacific)
    assert calendar_date(marker) == date(2026, 8, 28)
    # Legacy snapshots stored that marker converted to 01:59 Central.
    assert calendar_date_from_snapshot("2026-08-29T01:59:00-05:00") == date(2026, 8, 28)
    assert calendar_date_from_snapshot("2026-08-28T19:00:00-05:00") == date(2026, 8, 28)
    assert calendar_date_from_snapshot("2026-08-29T01:59:00-05:00", "2026-08-28") == date(2026, 8, 28)


# --- statuses ----------------------------------------------------------------

@pytest.mark.parametrize(
    ("status", "expected"),
    [("POSTPONED", POSTPONED), ("CANCELLED", CANCELED), ("SUSPENDED", SUSPENDED),
     ("NO_CONTEST", NO_CONTEST), ("IN_PROGRESS", IN_PROGRESS)],
)
def test_non_final_statuses_never_count(cutoff, status, expected) -> None:
    game = replace(make_game("x", "alpha", "beta", 14, 7), status=status)
    assert status_category(game, cutoff) == expected
    assert not counts_toward_record(game, cutoff)
    assert not counts_toward_scoring(game, cutoff)


def test_future_missing_forfeit_and_exhibition_statuses(cutoff) -> None:
    future = replace(make_game("f", "alpha", "beta", 0, 0), date=cutoff + timedelta(days=2),
                     status="UPCOMING", home_score=None, away_score=None, verified=False)
    assert status_category(future, cutoff) == SCHEDULED
    missing = replace(future, date=cutoff - timedelta(days=4))
    assert status_category(missing, cutoff) == UNRESOLVED
    assert not counts_toward_record(missing, cutoff)
    forfeit = make_game("ff", "alpha", "beta", 2, 0, forfeit=True)
    assert status_category(forfeit, cutoff) == FORFEIT
    assert counts_toward_record(forfeit, cutoff) and not counts_toward_scoring(forfeit, cutoff)
    scrimmage = replace(make_game("s", "alpha", "beta", 14, 7), contest_type="Scrimmage")
    assert status_category(scrimmage, cutoff) == EXHIBITION and not counts_toward_record(scrimmage, cutoff)
    assert status_category(make_game("ok", "alpha", "beta", 14, 7), cutoff) == FINAL


def test_postponed_game_is_not_a_loss_and_missing_score_is_not_zero(cutoff, league) -> None:
    teams, games = league
    postponed = replace(make_game("p", "alpha", "gamma", 0, 0), status="POSTPONED",
                        home_score=None, away_score=None, verified=False)
    unresolved = replace(make_game("u", "beta", "delta", 0, 0), status="UPCOMING",
                         home_score=None, away_score=None, verified=False)
    _, ledger, result = build(teams, [*games, postponed, unresolved], cutoff)
    rows = {row.team.team_id: row for row in result.rankings}
    assert rows["alpha"].record == "1-0" and rows["gamma"].record == "1-0"
    assert rows["beta"].pending_games == 1 and rows["beta"].data_status == "partial"
    assert rows["alpha"].pending_games == 0
    by_id = {game["game_id"]: game for game in ledger["games"]}
    assert by_id["u"]["home_score"] is None and by_id["u"]["status_category"] == UNRESOLVED
    assert by_id["p"]["status_category"] == POSTPONED and not by_id["p"]["counts_toward_record"]


# --- preseason versus unknown ------------------------------------------------

def test_verified_preseason_differs_from_unknown_results(league) -> None:
    teams, _ = league
    preseason_cutoff = datetime(2026, 8, 20, 11, tzinfo=CENTRAL)
    _, _, result = build(teams, [], preseason_cutoff)
    row = result.rankings[0]
    assert row.data_status == "preseason"
    assert row.to_dict()["pf_per_game"] is None and row.to_dict()["pa_per_game"] is None

    in_season = datetime(2026, 9, 22, 11, tzinfo=CENTRAL)
    listing = replace(make_game("l", "alpha", "beta", 0, 0), date=in_season - timedelta(days=4),
                      status="UPCOMING", home_score=None, away_score=None, verified=False)
    _, _, result = build(teams, [listing], in_season)
    rows = {row.team.team_id: row for row in result.rankings}
    assert rows["alpha"].data_status == "unavailable"
    assert "No verified results" in rows["alpha"].explanation
    assert "0-0" not in rows["alpha"].explanation
    assert RankingRow.data_status_for(0, 0, True) == "unavailable"


# --- movement wording --------------------------------------------------------

def test_rank_unchanged_while_rating_increases() -> None:
    assert rank_sentence(1, 1) == "State ranking: unchanged at No. 1."
    assert rating_sentence(96.2, 3.1) == "MFPI rating: increased 3.1 points to 96.2."


def test_rating_unchanged_while_rank_changes() -> None:
    assert rank_sentence(218, 221) == "State ranking: up 3 spots to No. 218 (from No. 221)."
    assert rating_sentence(11.6, 0.0) == "MFPI rating: unchanged at 11.6."


def test_missing_previous_snapshot_is_new_not_unchanged() -> None:
    assert "new at No. 7" in rank_sentence(7, None)
    assert "not comparable" in rating_sentence(55.0, None)


def test_rating_change_uses_displayed_values_and_never_negative_zero(cutoff, league) -> None:
    teams, games = league
    _, _, result = build(teams, games, cutoff)
    row = result.rankings[0]
    row.previous_mfpi = row.mfpi - 0.01
    change = row.to_dict()["mfpi_change"]
    assert change == round(round(row.mfpi, 1) - round(row.previous_mfpi, 1), 1)
    row.previous_mfpi = row.mfpi + 0.01
    assert str(row.to_dict()["mfpi_change"]) in {"0.0", "-0.1", "0.1"}
    assert str(row.to_dict()["mfpi_change"]) != "-0.0"


# --- identities --------------------------------------------------------------

def raw(game_id, home, away, home_id, away_id, *, home_city="", away_city="", day=28, score=(21, 14)):
    return RawGame(
        game_id=game_id, date=datetime(2026, 8, day, 19, tzinfo=CENTRAL), home_name=home, away_name=away,
        home_source_id=home_id, away_source_id=away_id, home_score=score[0], away_score=score[1],
        status="COMPLETED", home_city=home_city, away_city=away_city,
    )


def test_same_name_in_another_state_is_reported_not_silently_merged() -> None:
    teams = [make_team("Houston"), make_team("Corinth"), make_team("Tupelo", "7A")]
    raws = [
        raw("1", "Houston", "Corinth", "100", "200", home_city="Houston", away_city="Corinth", day=11),
        raw("2", "Houston", "Tupelo", "999", "300", home_city="Germantown", away_city="Tupelo", day=11),
    ]
    _, games, issues = reconcile_games(teams, raws)
    flagged = [issue for issue in issues if issue.code == "MULTIPLE_SOURCE_IDS_FOR_TEAM"]
    assert flagged and set(flagged[0].context["source_ids"]) == {"100", "999"}
    report = validate_inputs(teams, games, datetime(2026, 9, 15, 11, tzinfo=CENTRAL), Settings(), issues)
    assert "TEAM_DOUBLE_BOOKED" in {issue.code for issue in report.issues}


def test_confirmed_cleveland_identity_requires_source_id_and_name() -> None:
    teams = [replace(make_team("Cleveland Central", "5A"), team_id="cleveland-central"), make_team("Clarksdale")]
    for city in ("Cleveland", ""):
        listing = [raw("1", "Cleveland", "Clarksdale", "241722", "5", home_city=city, away_city="Clarksdale")]
        _, games, issues = reconcile_games(teams, listing)
        assert games[0].home_team_id == "cleveland-central"
        assert "REVIEWED_IDENTITY_APPLIED" in {issue.code for issue in issues}

    other_id = [raw("1", "Cleveland", "Clarksdale", "777", "5", home_city="Cleveland", away_city="Clarksdale")]
    _, games, _ = reconcile_games(teams, other_id)
    assert games[0].home_team_id == "external-777"  # the name alone never merges


def test_city_mismatch_blocks_an_unconfirmed_identity(monkeypatch) -> None:
    from mfpi import matching

    rule = matching.ReviewedIdentity("mhsaa_score_center", "55", "alpha", ("Alpha Town",), "Alpha", "test")
    monkeypatch.setattr(matching, "REVIEWED_SOURCE_IDENTITIES", (rule,))
    teams = [make_team("Alpha"), make_team("Beta")]
    _, games, issues = reconcile_games(teams, [raw("1", "Alpha Town", "Beta", "55", "2", home_city="Memphis")])
    assert games[0].home_team_id.startswith("external-")
    assert "REVIEWED_IDENTITY_NOT_CORROBORATED" in {issue.code for issue in issues}


def test_out_of_state_houston_on_sept_11_stays_external() -> None:
    teams = [make_team("Houston"), make_team("Corinth"), make_team("Tupelo", "7A")]
    raws = [
        raw("1", "Houston", "Corinth", "100", "200", day=11),
        replace(raw("2", "Houston", "Tupelo", "999", "300"), date=datetime(2026, 9, 11, 19, tzinfo=CENTRAL)),
    ]
    raws[0] = replace(raws[0], date=datetime(2026, 9, 11, 19, tzinfo=CENTRAL))
    all_teams, games, issues = reconcile_games(teams, raws)
    by_id = {game.game_id: game for game in games}
    assert by_id["1"].home_team_id == "houston"
    assert by_id["2"].home_team_id != "houston" and by_id["2"].home_team_id.startswith("external-")
    assert next(t for t in all_teams if t.team_id == by_id["2"].home_team_id).display_name == "Houston (out of state)"
    report = validate_inputs(teams, games, datetime(2026, 9, 15, 11, tzinfo=CENTRAL), Settings(), issues)
    assert "TEAM_DOUBLE_BOOKED" not in {issue.code for issue in report.issues}


def test_reviewed_external_identity_keeps_same_named_school_external(monkeypatch) -> None:
    from mfpi import matching

    extra = matching.ReviewedIdentity("mhsaa_score_center", "999", None, ("Houston",), "Germantown", "test")
    monkeypatch.setattr(matching, "REVIEWED_SOURCE_IDENTITIES", (*matching.REVIEWED_SOURCE_IDENTITIES, extra))
    teams = [make_team("Houston"), make_team("Tupelo", "7A")]
    _, games, issues = reconcile_games(teams, [raw("2", "Houston", "Tupelo", "999", "300", home_city="Germantown")])
    assert games[0].home_team_id == "external-999"
    assert "REVIEWED_EXTERNAL_IDENTITY" in {issue.code for issue in issues}


def test_repeated_import_is_idempotent() -> None:
    teams = [make_team("Alpha"), make_team("Beta")]
    raws = [raw("1", "Alpha", "Beta", "1", "2")]
    first = reconcile_games(teams, raws)[1]
    second = reconcile_games(teams, raws + raws)[1]
    assert [game.game_id for game in first] == ["1"]
    report = validate_inputs(teams, second, datetime(2026, 9, 1, tzinfo=CENTRAL), Settings())
    assert "DUPLICATE_GAME_ID" in {issue.code for issue in report.issues}


# --- the audit ---------------------------------------------------------------

def test_clean_snapshot_passes(cutoff, league) -> None:
    teams, games = league
    payload, ledger, _ = build(teams, games, cutoff)
    reference = {"teams": [team.to_dict() for team in teams]}
    report = audit_snapshot(payload, reference=reference, ledger=ledger)
    assert not report.blocking, [issue.message for issue in report.blocking]
    assert all(row["internal_consistency"] == "PASS" for row in report.team_rows)
    assert all(row["external_verification"] == "NOT_PERFORMED" for row in report.team_rows)


def test_missing_expected_team_blocks(cutoff, league) -> None:
    teams, games = league
    payload, _, _ = build(teams, games, cutoff)
    reference = {"teams": [team.to_dict() for team in teams] + [make_team("Epsilon").to_dict()]}
    report = audit_snapshot(payload, reference=reference)
    assert "MISSING_EXPECTED_TEAM" in codes(report, BLOCKING)


def test_out_of_state_opponent_needs_no_mhsaa_class(cutoff) -> None:
    teams = [make_team("Alpha"), replace(make_team("Memphis Prep"), classification=None, state="TN")]
    games = [make_game("g", "alpha", "memphis-prep", 14, 21)]
    payload, ledger, _ = build(teams, games, cutoff)
    report = audit_snapshot(payload, ledger=ledger)
    assert not report.blocking
    assert "ONE_SIDED_GAME" not in codes(report)


def test_one_sided_and_conflicting_scores_block(cutoff, league) -> None:
    teams, games = league
    payload, _, _ = build(teams, games, cutoff)
    conflicted = copy.deepcopy(payload)
    beta = next(row for row in conflicted["rankings"] if row["team_id"] == "beta")
    beta["game_results"][0]["home_score"] = 27
    assert "PERSPECTIVE_CONFLICT" in codes(audit_snapshot(conflicted), BLOCKING)
    one_sided = copy.deepcopy(payload)
    beta = next(row for row in one_sided["rankings"] if row["team_id"] == "beta")
    beta["game_results"] = []
    assert "ONE_SIDED_GAME" in codes(audit_snapshot(one_sided), BLOCKING)


def test_corrected_game_updates_both_teams(cutoff, league) -> None:
    teams, games = league
    corrected = [replace(games[0], home_score=35), games[1]]
    payload, ledger, _ = build(teams, corrected, cutoff)
    report = audit_snapshot(payload, ledger=ledger)
    assert not report.blocking
    rows = {row["team_id"]: row for row in payload["rankings"]}
    assert rows["alpha"]["game_results"][0]["home_score"] == rows["beta"]["game_results"][0]["home_score"] == 35


def test_duplicate_import_from_both_teams_is_detected(cutoff, league) -> None:
    teams, games = league
    payload, _, _ = build(teams, games, cutoff)
    doubled = copy.deepcopy(payload)
    alpha = next(row for row in doubled["rankings"] if row["team_id"] == "alpha")
    duplicate = dict(alpha["game_results"][0], date="2026-08-27T19:00:00-05:00", calendar_date="2026-08-27")
    alpha["game_results"].append(duplicate)
    alpha["games_played"] += 1
    alpha["record"] = "2-0"
    assert "DUPLICATE_GAME" in codes(audit_snapshot(doubled), BLOCKING)


def test_record_and_average_must_match_games(cutoff, league) -> None:
    teams, games = league
    payload, _, _ = build(teams, games, cutoff)
    broken = copy.deepcopy(payload)
    alpha = next(row for row in broken["rankings"] if row["team_id"] == "alpha")
    alpha["record"] = "0-1"
    alpha["pf_per_game"] = 3.0
    found = codes(audit_snapshot(broken), BLOCKING)
    assert {"RECORD_MISMATCH", "AVERAGE_MISMATCH"} <= found


def test_future_game_and_nonfinite_values_block(cutoff, league) -> None:
    teams, games = league
    payload, _, _ = build(teams, games, cutoff)
    broken = copy.deepcopy(payload)
    alpha = next(row for row in broken["rankings"] if row["team_id"] == "alpha")
    alpha["game_results"][0]["calendar_date"] = "2026-09-30"
    alpha["components"]["sos"]["raw"] = float("nan")
    found = codes(audit_snapshot(broken), BLOCKING)
    assert {"GAME_AFTER_CUTOFF", "NON_FINITE_VALUE"} <= found


def test_zero_average_for_team_without_games_is_flagged(cutoff, league) -> None:
    teams, games = league
    payload, _, _ = build(teams + [make_team("Idle")], games, cutoff)
    idle = next(row for row in payload["rankings"] if row["team_id"] == "idle")
    assert idle["pf_per_game"] is None
    legacy = copy.deepcopy(payload)
    idle = next(row for row in legacy["rankings"] if row["team_id"] == "idle")
    idle["pf_per_game"] = 0.0
    assert "FABRICATED_ZERO_AVERAGE" in codes(audit_snapshot(legacy), WARNING)


def test_rank_order_rounding_and_component_sum(cutoff, league) -> None:
    teams, games = league
    payload, _, _ = build(teams, games, cutoff)
    swapped = copy.deepcopy(payload)
    swapped["rankings"][0]["state_rank"], swapped["rankings"][1]["state_rank"] = 2, 1
    assert "RANK_ORDER_VIOLATION" in codes(audit_snapshot(swapped), BLOCKING)
    drifted = copy.deepcopy(payload)
    drifted["rankings"][0]["mfpi"] = round(drifted["rankings"][0]["mfpi"] + 0.2, 1)
    drifted["rankings"][0]["components"]["record"]["contribution"] += 1.0
    assert {"DISPLAY_ROUNDING_MISMATCH", "COMPONENT_SUM_MISMATCH"} <= codes(audit_snapshot(drifted), BLOCKING)


def test_tied_ratings_are_reported_not_blocked(cutoff) -> None:
    teams = [make_team("Alpha"), make_team("Beta")]
    payload, _, _ = build(teams, [], cutoff)
    report = audit_snapshot(payload)
    assert not report.blocking
    assert "RATING_TIE" in codes(report, INFO)
    assert [row["team"] for row in payload["rankings"]] == ["Alpha", "Beta"]  # deterministic name order


def test_movement_must_use_the_matching_previous_snapshot(cutoff, league) -> None:
    teams, games = league
    first, _, first_result = build(teams, games, cutoff)
    previous_rows = {row["team_id"]: row for row in first["rankings"]}
    second, _, _ = build(teams, games, cutoff, previous=previous_rows)
    assert not audit_snapshot(second, previous=first).blocking
    wrong_season = copy.deepcopy(first)
    wrong_season["metadata"]["season"] = 2025
    assert "PREVIOUS_SEASON_MISMATCH" in codes(audit_snapshot(second, previous=wrong_season), BLOCKING)
    shifted = copy.deepcopy(first)
    shifted["rankings"][0]["state_rank"] = 99
    assert "MOVEMENT_BASELINE_MISMATCH" in codes(audit_snapshot(second, previous=shifted), BLOCKING)


def test_team_with_no_results_and_shorter_external_name_is_flagged(cutoff) -> None:
    teams = [replace(make_team("Cleveland Central", "5A"), team_id="cleveland-central"), make_team("Grenada"),
             replace(make_team("Cleveland"), team_id="external-241722", classification=None)]
    games = [make_game("g", "grenada", "external-241722", 33, 20)]
    payload, _, _ = build(teams, games, cutoff)
    payload["metadata"]["week"] = 4
    report = audit_snapshot(payload)
    flagged = [issue for issue in report.issues if issue.code == "POSSIBLE_IDENTITY_SPLIT"]
    assert flagged and flagged[0].team_id == "cleveland-central"
    assert "RESULTS_UNAVAILABLE" in codes(report, WARNING)


def test_ledger_rejects_scores_on_nonfinal_listings(cutoff, league) -> None:
    teams, games = league
    payload, ledger, _ = build(teams, games, cutoff)
    ledger = copy.deepcopy(ledger)
    ledger["games"].append(dict(ledger["games"][0], game_id="p", status_category="postponed", counts_toward_record=False))
    assert "LEDGER_SCORE_ON_NONFINAL" in codes(audit_snapshot(payload, ledger=ledger), BLOCKING)


def test_scrimmage_with_final_score_never_counts(cutoff, league) -> None:
    teams, games = league
    scrimmage = replace(make_game("s", "alpha", "gamma", 35, 0), contest_type="Jamboree")
    _, ledger, result = build(teams, [*games, scrimmage], cutoff)
    rows = {row.team.team_id: row for row in result.rankings}
    assert rows["alpha"].record == "1-0" and rows["gamma"].record == "1-0"
    listing = next(g for g in ledger["games"] if g["game_id"] == "s")
    assert not listing["counts_toward_record"] and listing["home_score"] is None
    payload, _, _ = build(teams, [*games, scrimmage], cutoff)
    assert not audit_snapshot(payload, ledger=ledger).blocking
