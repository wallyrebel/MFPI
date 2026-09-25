"""Publication audit for MFPI snapshots.

``validation.py`` checks raw inputs before the engine runs. This module checks
the *output* a reader will see: the published team universe, every team's
game ledger from both sides, records, averages, ranks, component arithmetic,
and week-over-week comparisons. It runs inside the weekly pipeline before a
snapshot replaces ``data/current`` and can be run on any saved snapshot:

    python -m mfpi.audit --snapshot data/current --out reports/current

Severity levels:

* ``BLOCKING`` - the snapshot is internally inconsistent or would mislead a
  reader (a missing team, a one-sided score, a record that disagrees with its
  games, a rank out of order). A new run with a blocking issue is not
  published; the last valid snapshot stays live.
* ``WARNING`` - publishable, but a person should look (results unavailable
  for a team, possible identity split, a team credited with two games on one
  date). These are usually one team's source-identity problem; blocking every
  page for them would freeze the site on a snapshot with the same problem.
* ``INFO`` - flagged for investigation only (unusual scores, large swings).
  Unusual-but-valid results are never "corrected" automatically.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .config import CENTRAL, COMPONENT_WEIGHTS, FORMULA_VERSION
from .dates import calendar_date_from_snapshot
from .matching import normalize_name
from .providers import INACTIVE_FOOTBALL_PROGRAMS, MAXPREPS_RANKINGS_URL, MHSAA_CLASSIFICATIONS_URL

BLOCKING = "BLOCKING"
WARNING = "WARNING"
INFO = "INFO"
RANKED_CLASSES = {f"{n}A" for n in range(1, 8)}
MHSAA_SCORE_CENTER_URL = "https://scores.misshsaa.com/"
KNOWN_STATUSES = {"PUBLISHED", "CORRECTED", "PROVISIONAL", "DEMO"}
SEASON_START = {2026: date(2026, 8, 27)}

# Tolerances. Component contributions are stored to six decimals, so eight of
# them can differ from the unrounded total by at most ~4e-6 plus float noise.
COMPONENT_SUM_TOLERANCE = 0.001
AVERAGE_TOLERANCE = 0.051
UNUSUAL_MARGIN = 60
UNUSUAL_TOTAL = 110
LARGE_RATING_CHANGE = 15.0
LARGE_RANK_CHANGE = 40


@dataclass
class AuditIssue:
    code: str
    severity: str
    message: str
    team_id: str | None = None
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class AuditReport:
    snapshot: str
    season: int
    week: int
    status: str
    formula_version: str
    generated_at: str
    cutoff_at: str
    audited_at: str
    teams: int
    unique_games: int
    issues: list[AuditIssue]
    team_rows: list[dict[str, Any]]
    game_rows: list[dict[str, Any]]
    external_verification: str

    @property
    def blocking(self) -> list[AuditIssue]:
        return [issue for issue in self.issues if issue.severity == BLOCKING]

    @property
    def outcome(self) -> str:
        if self.blocking:
            return "BLOCKED"
        if any(issue.severity == WARNING for issue in self.issues):
            return "PASS_WITH_WARNINGS"
        return "PASS"

    def summary(self) -> dict[str, Any]:
        counts = Counter(issue.severity for issue in self.issues)
        codes = Counter((issue.severity, issue.code) for issue in self.issues)
        return {
            "snapshot": self.snapshot,
            "season": self.season,
            "week": self.week,
            "status": self.status,
            "formula_version": self.formula_version,
            "generated_at": self.generated_at,
            "cutoff_at": self.cutoff_at,
            "audited_at": self.audited_at,
            "outcome": self.outcome,
            "teams": self.teams,
            "unique_games": self.unique_games,
            "blocking": counts.get(BLOCKING, 0),
            "warnings": counts.get(WARNING, 0),
            "info": counts.get(INFO, 0),
            "issue_counts": [
                {"severity": severity, "code": code, "count": count}
                for (severity, code), count in sorted(codes.items())
            ],
            "external_verification": self.external_verification,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.summary(), "issues": [asdict(issue) for issue in self.issues]}


def _finite(value: Any) -> bool:
    return not isinstance(value, float) or math.isfinite(value)


def _walk_numbers(value: Any, path: str = "") -> Iterable[tuple[str, Any]]:
    if isinstance(value, dict):
        for key, item in value.items():
            yield from _walk_numbers(item, f"{path}.{key}" if path else str(key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _walk_numbers(item, f"{path}[{index}]")
    elif isinstance(value, float):
        yield path, value


def _record(wins: int, losses: int, ties: int) -> str:
    return f"{wins}-{losses}" + (f"-{ties}" if ties else "")


def _tokens(name: str) -> set[str]:
    return set(normalize_name(name).split())


def load_snapshot(directory: Path) -> dict[str, Any]:
    return json.loads((directory / "overall.json").read_text(encoding="utf-8"))


def load_optional(path: Path) -> dict[str, Any] | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def latest_revision(week_directory: Path) -> Path:
    revisions = sorted((week_directory / "corrections").glob("revision-*/overall.json"))
    return revisions[-1].parent if revisions else week_directory


def previous_snapshot_dir(data_root: Path, season: int, week: int) -> Path | None:
    if week <= 1:
        return None
    directory = data_root / str(season) / f"week-{week - 1:02d}"
    return latest_revision(directory) if (directory / "overall.json").exists() else None


def expected_universe(reference: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not reference:
        return {}
    return {
        team["team_id"]: team
        for team in reference.get("teams", [])
        if team.get("active", True)
        and team.get("classification") in RANKED_CLASSES
        and team["team_id"] not in INACTIVE_FOOTBALL_PROGRAMS
    }


def audit_snapshot(
    payload: dict[str, Any],
    *,
    snapshot_label: str = "snapshot",
    reference: dict[str, Any] | None = None,
    previous: dict[str, Any] | None = None,
    ledger: dict[str, Any] | None = None,
    validation: dict[str, Any] | None = None,
    audited_at: datetime | None = None,
    external_verification: str = "NOT_PERFORMED",
    check_formula_version: bool = False,
) -> AuditReport:
    metadata = payload.get("metadata", {})
    rows: list[dict[str, Any]] = payload.get("rankings", [])
    issues: list[AuditIssue] = []

    def add(code: str, severity: str, message: str, team_id: str | None = None, **context: Any) -> None:
        issues.append(AuditIssue(code, severity, message, team_id, context))

    season = int(metadata.get("season", 0))
    week = int(metadata.get("week", 0))
    cutoff_text = metadata.get("cutoff_at", "")
    cutoff_date = datetime.fromisoformat(cutoff_text).astimezone(CENTRAL).date() if cutoff_text else None
    opponent_names: dict[str, str] = metadata.get("opponent_names", {}) or {}

    # ---- metadata -------------------------------------------------------
    if metadata.get("status") not in KNOWN_STATUSES:
        add("UNKNOWN_SNAPSHOT_STATUS", BLOCKING, f"Snapshot status {metadata.get('status')!r} is not recognized.")
    coverage = metadata.get("coverage_percentage")
    if coverage is not None and not (0 <= coverage <= 100):
        add("INVALID_COVERAGE", BLOCKING, f"Coverage {coverage} is outside 0-100.")
    expected_games, verified_games = metadata.get("expected_games"), metadata.get("verified_games")
    if isinstance(expected_games, int) and isinstance(verified_games, int) and verified_games > expected_games:
        add("INVALID_COVERAGE", BLOCKING, f"Verified games {verified_games} exceed expected games {expected_games}.")
    if check_formula_version and metadata.get("formula_version") != FORMULA_VERSION:
        add("FORMULA_VERSION_MISMATCH", WARNING,
            f"Snapshot formula {metadata.get('formula_version')} differs from the code's {FORMULA_VERSION}.")
    if validation and not validation.get("valid", True) and metadata.get("status") != "PROVISIONAL":
        add("INVALID_VALIDATION_PUBLISHED", BLOCKING, "A snapshot marked valid carries a failed validation report.")

    for path, value in _walk_numbers(payload):
        if not _finite(value):
            add("NON_FINITE_VALUE", BLOCKING, f"Non-finite number at {path}.", path=path)

    # ---- identity and coverage -----------------------------------------
    ids = Counter(row["team_id"] for row in rows)
    for team_id, count in ids.items():
        if count > 1:
            add("DUPLICATE_TEAM_ID", BLOCKING, f"Team ID {team_id} appears {count} times.", team_id)
    slugs = Counter(row.get("slug") for row in rows)
    for slug, count in slugs.items():
        if count > 1:
            add("DUPLICATE_SLUG", BLOCKING, f"URL slug {slug!r} appears {count} times.")
    names = Counter(normalize_name(row["team"]) for row in rows)
    for name, count in names.items():
        if count > 1:
            add("DUPLICATE_DISPLAY_NAME", WARNING, f"{count} ranked teams normalize to the name {name!r}.")
    for row in rows:
        if row.get("classification") not in RANKED_CLASSES:
            add("OUT_OF_SCOPE_TEAM", BLOCKING,
                f"{row['team']} has classification {row.get('classification')!r}, outside MHSAA 1A-7A.", row["team_id"])
        if row["team_id"].startswith("external-"):
            add("EXTERNAL_TEAM_RANKED", BLOCKING, f"External opponent {row['team']} entered the ranking table.", row["team_id"])

    universe = expected_universe(reference)
    by_id = {row["team_id"]: row for row in rows}
    if universe:
        for team_id, team in sorted(universe.items()):
            if team_id not in by_id:
                add("MISSING_EXPECTED_TEAM", BLOCKING,
                    f"{team['display_name']} ({team['classification']}) is in the MHSAA reference but not the snapshot.", team_id)
            else:
                row = by_id[team_id]
                if (row.get("classification"), str(row.get("region"))) != (team["classification"], str(team.get("region"))):
                    add("CLASSIFICATION_MISMATCH", BLOCKING,
                        f"{row['team']} is {row.get('classification')}/Region {row.get('region')} but the reference says "
                        f"{team['classification']}/Region {team.get('region')}.", team_id)
        for team_id in sorted(set(by_id) - set(universe)):
            add("UNEXPECTED_TEAM", BLOCKING, f"{by_id[team_id]['team']} is not an active MHSAA 1A-7A reference team.", team_id)

    if previous:
        previous_ids = {row["team_id"] for row in previous.get("rankings", [])}
        if len(previous_ids) != len(by_id):
            add("TEAM_COUNT_CHANGED", WARNING,
                f"Ranked team count changed from {len(previous_ids)} to {len(by_id)}.",
                added=sorted(set(by_id) - previous_ids), removed=sorted(previous_ids - set(by_id)))
        for team_id in sorted(previous_ids - set(by_id)):
            add("TEAM_DISAPPEARED", BLOCKING, f"{team_id} was ranked last week and is missing now.", team_id)

    # ---- game ledger from both perspectives ----------------------------
    ranked_ids = set(by_id)
    legacy = bool(rows) and not any("game_results" in row for row in rows)
    if legacy:
        add("LEGACY_SNAPSHOT_NO_GAME_ROWS", INFO,
            "This snapshot predates per-game rows; record, average and two-sided game checks are skipped.")
    perspectives: dict[tuple[str, str, str], dict[str, tuple]] = defaultdict(dict)
    game_rows: list[dict[str, Any]] = []
    for row in rows:
        team_id = row["team_id"]
        seen_dates: Counter[date] = Counter()
        seen_pairs: dict[frozenset[str], list[date]] = defaultdict(list)
        for game in row.get("game_results", []):
            home, away = game.get("home"), game.get("away")
            game_day = calendar_date_from_snapshot(game["date"], game.get("calendar_date"))
            if team_id not in {home, away}:
                add("GAME_NOT_INVOLVING_TEAM", BLOCKING, f"{row['team']} lists a game between {home} and {away}.", team_id)
                continue
            if home == away:
                add("SELF_GAME", BLOCKING, f"{row['team']} is listed as playing itself on {game_day}.", team_id)
            hs, as_ = game.get("home_score"), game.get("away_score")
            if not isinstance(hs, int) or not isinstance(as_, int):
                add("FINAL_WITHOUT_SCORE", BLOCKING, f"{row['team']} has a counted game on {game_day} without both scores.", team_id)
                continue
            if min(hs, as_) < 0 or max(hs, as_) > 150:
                add("IMPOSSIBLE_SCORE", BLOCKING, f"{row['team']} game on {game_day} has score {hs}-{as_}.", team_id)
            if cutoff_date and game_day > cutoff_date:
                add("GAME_AFTER_CUTOFF", BLOCKING, f"{row['team']} counts a {game_day} game after the {cutoff_date} cutoff.", team_id)
            start = SEASON_START.get(season)
            if start and game_day < start:
                add("GAME_BEFORE_SEASON", WARNING, f"{row['team']} counts a {game_day} game before the season start.", team_id)
            seen_dates[game_day] += 1
            opponent = away if home == team_id else home
            seen_pairs[frozenset({home, away})].append(game_day)
            if opponent not in ranked_ids and not opponent_names.get(opponent) and opponent.startswith("external-"):
                add("UNNAMED_OPPONENT", WARNING, f"{row['team']} played {opponent}, which has no display name.", team_id)
            key = (game_day.isoformat(), *sorted((home, away)))
            facts = (home, away, hs, as_, bool(game.get("neutral")), bool(game.get("forfeit")))
            perspectives[key][team_id] = facts
            if game.get("forfeit"):
                add("FORFEIT_REVIEW", INFO,
                    f"{row['team']} has a forfeit on {game_day}; confirm the official ruling before treating its score as played.",
                    team_id)
            margin, total = abs(hs - as_), hs + as_
            if margin >= UNUSUAL_MARGIN or total >= UNUSUAL_TOTAL:
                add("UNUSUAL_SCORE", INFO, f"{row['team']} game on {game_day} finished {hs}-{as_}; flagged for a source check only.", team_id)
        for game_day, count in seen_dates.items():
            if count > 1:
                for game in row.get("game_results", []):
                    if calendar_date_from_snapshot(game["date"], game.get("calendar_date")) == game_day:
                        opponent = game["away"] if game["home"] == team_id else game["home"]
                        if opponent in ranked_ids:
                            add("OPPONENT_LISTING_UNDER_REVIEW", WARNING,
                                f"{opponent}'s {game_day} game against {row['team']} involves a double-booked listing.",
                                opponent, date=game_day.isoformat(), double_booked_team=team_id)
                add("MULTIPLE_GAMES_SAME_DAY", WARNING,
                    f"{row['team']} is credited with {count} games on {game_day}; one listing may belong to a "
                    "same-named school (check source team IDs and cities).", team_id, date=game_day.isoformat())
        for pair, days in seen_pairs.items():
            days.sort()
            for first, second in zip(days, days[1:]):
                if (second - first).days <= 1:
                    add("DUPLICATE_GAME", BLOCKING,
                        f"{row['team']} lists the same matchup on {first} and {second} (likely a duplicate import).", team_id)

    for key, sides in sorted(perspectives.items()):
        game_day, first, second = key
        both_ranked = first in ranked_ids and second in ranked_ids
        facts = set(sides.values())
        home, away, hs, as_, neutral, forfeit = next(iter(sides.values()))
        status = "consistent"
        if len(facts) > 1:
            status = "conflict"
            add("PERSPECTIVE_CONFLICT", BLOCKING,
                f"The {game_day} game between {first} and {second} differs between the two team pages.",
                None, perspectives={team: list(value) for team, value in sides.items()})
        elif both_ranked and len(sides) != 2:
            status = "one_sided"
            missing = ({first, second} - set(sides)).pop()
            add("ONE_SIDED_GAME", BLOCKING,
                f"The {game_day} game between {first} and {second} is missing from {missing}'s results.", missing)
        game_rows.append({
            "calendar_date": game_day,
            "home": home,
            "away": away,
            "home_name": by_id.get(home, {}).get("team") or opponent_names.get(home, home),
            "away_name": by_id.get(away, {}).get("team") or opponent_names.get(away, away),
            "home_score": hs,
            "away_score": as_,
            "neutral": neutral,
            "forfeit": forfeit,
            "both_teams_ranked": both_ranked,
            "perspective_check": status if both_ranked else "single_ranked_team",
        })

    # ---- records, averages and schedule gaps ---------------------------
    played_counts = [row.get("games_played", 0) for row in rows]
    median_played = statistics.median(played_counts) if played_counts else 0
    for row in ([] if legacy else rows):
        team_id = row["team_id"]
        games = [g for g in row.get("game_results", []) if isinstance(g.get("home_score"), int) and isinstance(g.get("away_score"), int)]
        wins = losses = ties = pf = pa = 0
        for game in games:
            home = game["home"] == team_id
            for_, against = (game["home_score"], game["away_score"]) if home else (game["away_score"], game["home_score"])
            pf += for_
            pa += against
            wins += for_ > against
            losses += for_ < against
            ties += for_ == against
        if len(row.get("game_results", [])) != row.get("games_played"):
            add("GAMES_PLAYED_MISMATCH", BLOCKING,
                f"{row['team']} reports {row.get('games_played')} games but lists {len(row.get('game_results', []))}.", team_id)
        if _record(wins, losses, ties) != row.get("record"):
            add("RECORD_MISMATCH", BLOCKING,
                f"{row['team']} shows {row.get('record')} but its games add up to {_record(wins, losses, ties)}.", team_id)
        played = len(games)
        for key, total in (("pf_per_game", pf), ("pa_per_game", pa)):
            value = row.get(key)
            if played == 0:
                if value not in (None,):
                    add("FABRICATED_ZERO_AVERAGE", WARNING,
                        f"{row['team']} has no eligible games but publishes {key}={value}; the site must show it as unavailable.",
                        team_id)
            elif value is None or abs(value - total / played) > AVERAGE_TOLERANCE:
                add("AVERAGE_MISMATCH", BLOCKING,
                    f"{row['team']} {key} is {value} but its games average {total / played:.2f}.", team_id)
        if played == 0:
            status = row.get("data_status")
            if status != "preseason" and (week >= 2 or row.get("pending_games")):
                add("RESULTS_UNAVAILABLE", WARNING,
                    f"{row['team']} has no verified results at week {week}; its page must say results are unavailable, not 0-0.",
                    team_id)
                own = _tokens(row["team"]) - {"high", "school", "attendance", "center"}
                for external_id, name in opponent_names.items():
                    tokens = _tokens(name)
                    if tokens and tokens < own:
                        add("POSSIBLE_IDENTITY_SPLIT", WARNING,
                            f"External opponent {name!r} ({external_id}) may be {row['team']} listed under a shorter name; "
                            "confirm with the source team ID and city before linking.",
                            team_id, external_id=external_id, external_name=name)
        elif median_played - played >= 2:
            add("SCHEDULE_GAP", INFO,
                f"{row['team']} has {played} verified games against a statewide median of {median_played}.", team_id)
        if row.get("pending_games"):
            add("PENDING_RESULTS", INFO, f"{row['team']} has {row['pending_games']} listing(s) awaiting a verified result.", team_id)

    # ---- ranks, components, movement -----------------------------------
    ranks = sorted(row.get("state_rank", 0) for row in rows)
    if ranks != list(range(1, len(rows) + 1)):
        add("STATE_RANKS_NOT_SEQUENTIAL", BLOCKING, "State ranks are not exactly 1..N.")
    ordered = sorted(rows, key=lambda row: row.get("state_rank", 0))
    for above, below in zip(ordered, ordered[1:]):
        if below["mfpi_unrounded"] > above["mfpi_unrounded"] + 1e-6:
            add("RANK_ORDER_VIOLATION", BLOCKING,
                f"No. {below['state_rank']} {below['team']} ({below['mfpi_unrounded']}) outrates No. {above['state_rank']} "
                f"{above['team']} ({above['mfpi_unrounded']}).", below["team_id"])
        elif abs(below["mfpi_unrounded"] - above["mfpi_unrounded"]) <= 1e-6:
            add("RATING_TIE", INFO, f"{above['team']} and {below['team']} share a full-precision rating; tie-breakers decided the order.",
                below["team_id"])
    class_seen: Counter[str] = Counter()
    for row in ordered:
        class_seen[row.get("classification")] += 1
        if row.get("class_rank") != class_seen[row.get("classification")]:
            add("CLASS_RANK_MISMATCH", BLOCKING,
                f"{row['team']} is class No. {row.get('class_rank')} but statewide order implies No. {class_seen[row.get('classification')]}.",
                row["team_id"])
    weights_expected = {name: weight for name, weight in COMPONENT_WEIGHTS.items()}
    for row in rows:
        team_id = row["team_id"]
        mfpi, unrounded = row.get("mfpi"), row.get("mfpi_unrounded")
        if not (1.0 <= unrounded <= 100.0):
            add("RATING_OUT_OF_RANGE", BLOCKING, f"{row['team']} rating {unrounded} is outside 1-100.", team_id)
        if round(unrounded, 1) != mfpi:
            add("DISPLAY_ROUNDING_MISMATCH", BLOCKING, f"{row['team']} displays {mfpi} for {unrounded}.", team_id)
        components = row.get("components", {})
        weights = {name: value.get("weight") for name, value in components.items()}
        if set(weights) == set(weights_expected) and any(abs(weights[k] - weights_expected[k]) > 1e-9 for k in weights):
            add("WEIGHT_MISMATCH", WARNING if metadata.get("formula_version") != FORMULA_VERSION else BLOCKING,
                f"{row['team']} component weights differ from the documented weights.", team_id, weights=weights)
        for name, value in components.items():
            if not (0.0 <= value.get("normalized", -1) <= 100.0):
                add("PERCENTILE_OUT_OF_RANGE", BLOCKING, f"{row['team']} {name} percentile {value.get('normalized')} is outside 0-100.", team_id)
        component_total = sum(value.get("contribution", 0.0) for value in components.values())
        bye = row.get("bye_adjustment") or {}
        expected = min(100.0, max(1.0, component_total)) + float(bye.get("adjustment", 0.0) or 0.0)
        if components and abs(expected - unrounded) > COMPONENT_SUM_TOLERANCE:
            add("COMPONENT_SUM_MISMATCH", BLOCKING,
                f"{row['team']} components plus adjustments total {expected:.4f}, not {unrounded:.4f}.", team_id)

    if previous:
        previous_meta = previous.get("metadata", {})
        if previous_meta.get("season") != season:
            add("PREVIOUS_SEASON_MISMATCH", BLOCKING, "Movement compares against a different season.")
        elif previous_meta.get("week") != week - 1:
            add("PREVIOUS_WEEK_GAP", WARNING, f"Movement compares week {week} with week {previous_meta.get('week')}.")
        prior = {row["team_id"]: row for row in previous.get("rankings", [])}
        for row in rows:
            old = prior.get(row["team_id"])
            if old is None:
                if row.get("state_rank_change") is not None:
                    add("MOVEMENT_WITHOUT_BASELINE", BLOCKING, f"{row['team']} shows movement with no previous snapshot row.", row["team_id"])
                continue
            if row.get("previous_state_rank") not in (None, old.get("state_rank")):
                add("MOVEMENT_BASELINE_MISMATCH", BLOCKING,
                    f"{row['team']} compares against previous rank {row.get('previous_state_rank')}, "
                    f"but the previous snapshot ranked it {old.get('state_rank')}.", row["team_id"])
            change = row.get("state_rank_change")
            if change is not None and change != old["state_rank"] - row["state_rank"]:
                add("RANK_CHANGE_MISMATCH", BLOCKING, f"{row['team']} rank change {change} is not previous minus current.", row["team_id"])
            old_rating = old.get("mfpi_unrounded", old.get("mfpi"))
            if row.get("mfpi_change") is not None:
                full = row["mfpi_unrounded"] - old_rating
                displayed = round(row["mfpi"] - round(old_rating, 1), 1)
                if abs(row["mfpi_change"] - full) > 0.051 and abs(row["mfpi_change"] - displayed) > 0.051:
                    add("RATING_CHANGE_MISMATCH", BLOCKING,
                        f"{row['team']} rating change {row['mfpi_change']} does not match the previous snapshot.", row["team_id"])
                if abs(full) >= LARGE_RATING_CHANGE:
                    add("LARGE_RATING_CHANGE", INFO, f"{row['team']} rating moved {full:+.1f} points.", row["team_id"])
            if change is not None and abs(change) >= LARGE_RANK_CHANGE:
                add("LARGE_RANK_CHANGE", INFO, f"{row['team']} moved {change:+d} places.", row["team_id"])

    # ---- optional full listing ledger ----------------------------------
    ledger_by_team: dict[str, list[dict[str, Any]]] = defaultdict(list)
    if ledger:
        seen_ids: Counter[str] = Counter()
        for game in ledger.get("games", []):
            seen_ids[game["game_id"]] += 1
            for side in ("home", "away"):
                ledger_by_team[game[side]].append(game)
            category = game.get("status_category")
            if category in {"final", "forfeit"} and (game.get("home_score") is None or game.get("away_score") is None):
                add("LEDGER_FINAL_WITHOUT_SCORE", BLOCKING, f"Listing {game['game_id']} is {category} without both scores.")
            if game.get("counts_toward_record") and category not in {"final", "forfeit"}:
                add("LEDGER_NONFINAL_COUNTED", BLOCKING, f"Listing {game['game_id']} ({category}) counts toward a record.")
            if category not in {"final", "forfeit"} and (game.get("home_score") is not None or game.get("away_score") is not None):
                add("LEDGER_SCORE_ON_NONFINAL", BLOCKING, f"Listing {game['game_id']} ({category}) carries a score.")
        for game_id, count in seen_ids.items():
            if count > 1:
                add("LEDGER_DUPLICATE_GAME_ID", BLOCKING, f"Listing {game_id} appears {count} times.")
        for row in rows:
            counted = [g for g in ledger_by_team.get(row["team_id"], []) if g.get("counts_toward_record")]
            if len(counted) != row.get("games_played"):
                add("LEDGER_RECORD_MISMATCH", BLOCKING,
                    f"{row['team']} counts {row.get('games_played')} games but the listing ledger has {len(counted)}.", row["team_id"])

    # ---- per-team reconciliation rows ----------------------------------
    issue_codes: dict[str, list[str]] = defaultdict(list)
    for issue in issues:
        if issue.team_id and issue.severity in {BLOCKING, WARNING}:
            issue_codes[issue.team_id].append(issue.code)
    prior_rows = {row["team_id"]: row for row in (previous or {}).get("rankings", [])}
    team_rows = []
    for row in sorted(rows, key=lambda item: item["state_rank"]):
        team_id = row["team_id"]
        pending = row.get("pending_games")
        if row.get("games_played", 0) == 0:
            ledger_status = "unavailable: no verified results linked"
        elif ledger:
            unresolved = [g for g in ledger_by_team.get(team_id, []) if g.get("status_category") == "unresolved"]
            ledger_status = f"incomplete: {len(unresolved)} unresolved listing(s)" if unresolved else "complete for listings in feed"
        elif pending is not None:
            ledger_status = f"incomplete: {pending} unresolved listing(s)" if pending else "complete for listings in feed"
        else:
            ledger_status = "counted games consistent; unresolved listings not recorded in this legacy snapshot"
        reference_team = universe.get(team_id, {})
        team_rows.append({
            "team_id": team_id,
            "name": row["team"],
            "class": row.get("classification"),
            "region": row.get("region"),
            "reference_class": reference_team.get("classification", ""),
            "reference_region": reference_team.get("region", ""),
            "state_rank": row["state_rank"],
            "prior_record": prior_rows.get(team_id, {}).get("record", ""),
            "snapshot_record": row.get("record"),
            "games_counted": row.get("games_played"),
            "cutoff": cutoff_text,
            "ledger_status": ledger_status,
            "internal_consistency": "FAIL" if any(
                i.severity == BLOCKING and i.team_id == team_id for i in issues
            ) else "PASS",
            "external_verification": external_verification,
            "source_links": " ".join(filter(None, [
                MHSAA_SCORE_CENTER_URL,
                MHSAA_CLASSIFICATIONS_URL,
                MAXPREPS_RANKINGS_URL.format(page=1) if row.get("maxpreps_state_rank") else "",
            ])),
            "correction_made": "",
            "unresolved_issue": ";".join(sorted(set(issue_codes.get(team_id, [])))),
        })

    return AuditReport(
        snapshot=snapshot_label,
        season=season,
        week=week,
        status=str(metadata.get("status")),
        formula_version=str(metadata.get("formula_version")),
        generated_at=str(metadata.get("generated_at")),
        cutoff_at=cutoff_text,
        audited_at=(audited_at or datetime.now(timezone.utc)).isoformat(),
        teams=len(rows),
        unique_games=len(perspectives),
        issues=issues,
        team_rows=team_rows,
        game_rows=game_rows,
        external_verification=external_verification,
    )


def write_report(report: AuditReport, out_dir: Path, corrections: dict[str, str] | None = None) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "data-quality.json").write_text(json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8")
    corrections = corrections or {}
    if report.team_rows:
        with (out_dir / "team-reconciliation.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(report.team_rows[0]))
            writer.writeheader()
            for row in report.team_rows:
                writer.writerow({**row, "correction_made": corrections.get(row["team_id"], row["correction_made"])})
    if report.game_rows:
        with (out_dir / "game-ledger-check.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(report.game_rows[0]))
            writer.writeheader()
            writer.writerows(report.game_rows)


def audit_directory(
    directory: Path,
    *,
    data_root: Path,
    reference_path: Path | None,
    external_verification: str,
    check_formula_version: bool = False,
) -> AuditReport:
    payload = load_snapshot(directory)
    metadata = payload["metadata"]
    previous_dir = previous_snapshot_dir(data_root, int(metadata["season"]), int(metadata["week"]))
    previous = load_snapshot(previous_dir) if previous_dir else None
    reference = load_optional(reference_path) if reference_path else None
    return audit_snapshot(
        payload,
        snapshot_label=str(directory),
        reference=reference,
        previous=previous,
        ledger=load_optional(directory / "games.json"),
        validation=load_optional(directory / "validation.json"),
        external_verification=external_verification,
        check_formula_version=check_formula_version,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit a published MFPI snapshot.")
    parser.add_argument("--snapshot", type=Path, default=Path("data/current"))
    parser.add_argument("--data-root", type=Path, default=Path("data"))
    parser.add_argument("--reference", type=Path, default=Path("data/reference/mhsaa_teams_2025_27.json"))
    parser.add_argument("--out", type=Path, help="Write data-quality.json and CSV reports here.")
    parser.add_argument(
        "--external-verification",
        default="NOT_PERFORMED",
        help="Label recorded for external source re-verification (never 'VERIFIED' without evidence).",
    )
    parser.add_argument("--strict", action="store_true", help="Exit 1 on warnings as well as blocking issues.")
    parser.add_argument("--corrections", type=Path, help="JSON map of team_id -> correction note for the CSV report.")
    args = parser.parse_args(argv)
    report = audit_directory(
        args.snapshot,
        data_root=args.data_root,
        reference_path=args.reference,
        external_verification=args.external_verification,
        check_formula_version=args.snapshot.name == "current",
    )
    if args.out:
        corrections = json.loads(args.corrections.read_text(encoding="utf-8")) if args.corrections else None
        write_report(report, args.out, corrections)
    print(json.dumps(report.summary(), indent=2))
    for issue in report.issues:
        if issue.severity == BLOCKING:
            print(f"BLOCKING {issue.code}: {issue.message}", file=sys.stderr)
    if report.blocking:
        return 2
    if args.strict and report.outcome != "PASS":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
