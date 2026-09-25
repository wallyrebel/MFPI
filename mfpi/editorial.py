"""Weekly Analysis drafts and the draft -> review -> publish workflow.

Articles are generated only from published, audited snapshots. Two ways to
publish them:

* ``auto`` (run by the weekly workflow) publishes the week's articles as
  *automated analysis* under the operator's standing approval. They are
  labelled as automated, name no reviewer, and carry no ads.
* ``publish`` marks an article as reviewed by a named person.

    python -m mfpi.editorial generate --week 4
    python -m mfpi.editorial auto                 # latest published week
    python -m mfpi.editorial list
    python -m mfpi.editorial publish 2026-week-04-weekly-analysis --reviewer "Full Name" --confirm-reviewed
    python -m mfpi.editorial validate

Nothing here invents players, injuries, quotes or game narratives. Every
sentence is computed from verified scores and published ratings, and every
opponent rank is labelled as current or as of a stated snapshot.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from .audit import latest_revision
from .config import CENTRAL
from .dates import calendar_date_from_snapshot
from .matching import REVIEWED_GAME_SIDES, REVIEWED_SOURCE_IDENTITIES
from .explain import display_rating_change, rank_sentence, rating_sentence

CONTENT_DIR = Path("content/analysis")
STATUSES = ("draft", "in_review", "published")
DRAFT_AUTHOR = "MFPI automated draft (requires human review)"
AUTOMATED_AUTHOR = "MFPI automated analysis"
# Standing approval from the site's operator (given 2026-09-25) to publish the
# weekly automated analysis without an individual review. Articles published
# this way are labelled "automated" and never claim a human reviewer.
STANDING_APPROVER = "Jon Ross Myers"
MHSAA_SCORES = "https://scores.misshsaa.com/"
MHSAA_CLASSES = "https://www.misshsaa.com/2024/11/19/2025-27-football-regions/"
MEDIA_RANKINGS = "https://www.maxpreps.com/ms/football/rankings/1/"


# ---------------------------------------------------------------------------
# snapshot helpers


@dataclass
class Snapshot:
    week: int
    path: Path
    payload: dict[str, Any]

    @property
    def meta(self) -> dict[str, Any]:
        return self.payload["metadata"]

    @property
    def rows(self) -> list[dict[str, Any]]:
        return self.payload["rankings"]

    @property
    def by_id(self) -> dict[str, dict[str, Any]]:
        return {row["team_id"]: row for row in self.rows}

    @property
    def cutoff_date(self) -> date:
        return datetime.fromisoformat(self.meta["cutoff_at"]).astimezone(CENTRAL).date()

    @property
    def generated_at(self) -> datetime:
        return datetime.fromisoformat(self.meta["generated_at"])


def load_week(data_root: Path, season: int, week: int) -> Snapshot | None:
    directory = data_root / str(season) / f"week-{week:02d}"
    if not (directory / "overall.json").exists():
        return None
    latest = latest_revision(directory)
    return Snapshot(week, latest, json.loads((latest / "overall.json").read_text(encoding="utf-8")))


def team_link(team_id: str, snapshot: Snapshot) -> str:
    """Inline markup the site renders as a link to the team page."""
    row = snapshot.by_id.get(team_id)
    if row:
        return f"[[{team_id}]]"
    return snapshot.meta.get("opponent_names", {}).get(team_id, "a non-MHSAA opponent")


def game_day(game: dict[str, Any]) -> date:
    return calendar_date_from_snapshot(game["date"], game.get("calendar_date"))


def short_date(value: date) -> str:
    return f"{value.strftime('%b')} {value.day}"


def results_in_window(row: dict[str, Any], start: date | None, end: date) -> list[dict[str, Any]]:
    games = [game for game in row.get("game_results", []) if (start is None or game_day(game) > start) and game_day(game) <= end]
    return sorted(games, key=game_day)


def describe_result(team_id: str, game: dict[str, Any], snapshot: Snapshot) -> str:
    home = game["home"] == team_id
    opponent = game["away"] if home else game["home"]
    scored, allowed = (game["home_score"], game["away_score"]) if home else (game["away_score"], game["home_score"])
    verb = "beat" if scored > allowed else "lost to" if scored < allowed else "tied"
    site = "at home" if home and not game.get("neutral") else "on a neutral field" if game.get("neutral") else "on the road"
    opponent_row = snapshot.by_id.get(opponent)
    rank = f" (currently No. {opponent_row['state_rank']})" if opponent_row else " (not in the MHSAA ranking)"
    extra = " in a forfeit" if game.get("forfeit") else " in overtime" if game.get("overtime") else ""
    return f"{verb} {team_link(opponent, snapshot)}{rank} {scored}-{allowed} {site} on {short_date(game_day(game))}{extra}"


def double_booked(snapshot: Snapshot) -> set[tuple[str, date]]:
    counts: Counter[tuple[str, date]] = Counter()
    for row in snapshot.rows:
        for game in row.get("game_results", []):
            counts[(row["team_id"], game_day(game))] += 1
    return {key for key, count in counts.items() if count > 1}


def sources(snapshot: Snapshot) -> list[dict[str, str]]:
    return [
        {"label": "MHSAA official score center (schedules and scores)", "url": MHSAA_SCORES},
        {"label": "MHSAA 2025-27 football classifications and regions", "url": MHSAA_CLASSES},
        {"label": "Statewide media rankings used for the Media Rank inputs", "url": MEDIA_RANKINGS},
        {"label": f"MFPI Week {snapshot.week} rankings archive", "url": f"/archive/{snapshot.meta['season']}/week-{snapshot.week:02d}"},
        {"label": "MFPI methodology", "url": "/methodology"},
    ]


def base_article(slug: str, title: str, dek: str, snapshot: Snapshot, kind: str) -> dict[str, Any]:
    return {
        "slug": slug,
        "kind": kind,
        "title": title,
        "dek": dek,
        "status": "draft",
        "season": snapshot.meta["season"],
        "week": snapshot.week,
        "snapshot_run_id": snapshot.meta.get("run_id"),
        "snapshot_generated_at": snapshot.meta["generated_at"],
        "formula_version": snapshot.meta["formula_version"],
        "draft_generated_at": datetime.now(timezone.utc).isoformat(),
        "author": DRAFT_AUTHOR,
        "reviewed_by": None,
        "reviewed_at": None,
        "published_at": None,
        "review_notes": "",
        "sources": sources(snapshot),
        "limitations": [],
        "sections": [],
    }


def fmt_change(value: float | None) -> str:
    if value is None:
        return "NEW"
    return "0.0" if value == 0 else f"{value:+.1f}"


def fmt_move(value: int | None) -> str:
    if value is None:
        return "NEW"
    return "—" if value == 0 else f"{value:+d}"


def data_notes(snapshot: Snapshot) -> list[str]:
    meta = snapshot.meta
    notes = [
        f"Snapshot generated {datetime.fromisoformat(meta['generated_at']).astimezone(CENTRAL):%B %-d, %Y at %-I:%M %p} Central "
        f"with a cutoff of {datetime.fromisoformat(meta['cutoff_at']).astimezone(CENTRAL):%B %-d at %-I:%M %p} Central, "
        f"formula {meta['formula_version']}.",
    ]
    if meta.get("expected_games"):
        notes.append(
            f"{meta['verified_games']} of {meta['expected_games']} game listings due by the cutoff had verified scores "
            f"({meta['coverage_percentage']:.1f}%); the rest count as unavailable, never as losses or 0-0 results."
        )
    missing = [row for row in snapshot.rows if row.get("games_played", 0) == 0]
    linked = {identity.team_id for identity in REVIEWED_SOURCE_IDENTITIES if identity.team_id}
    pending_link = [row for row in missing if row["team_id"] in linked]
    unexplained = [row for row in missing if row["team_id"] not in linked]
    if pending_link:
        names = ", ".join(team_link(row["team_id"], snapshot) for row in pending_link)
        notes.append(
            f"{names} had no linked results in this snapshot because the score feed lists the school under a "
            "different name. The link has been confirmed and applies from the next weekly run; until then its "
            "rating is provisional and does not reflect its games."
        )
    if unexplained:
        names = ", ".join(team_link(row["team_id"], snapshot) for row in unexplained)
        notes.append(
            f"No verified results were linked to {names} for this cutoff. Their ratings are provisional and rest on "
            "class, media and neutral inputs; their positions should not be read as the product of games."
        )
    confirmed_days = {side.date for side in REVIEWED_GAME_SIDES}
    for team_id, day in sorted(double_booked(snapshot)):
        if day.isoformat() in confirmed_days:
            notes.append(
                f"{team_link(team_id, snapshot)} is credited with two games on {short_date(day)} in this snapshot. "
                "One of them was played by a same-named out-of-state school; that game is removed from "
                f"{team_link(team_id, snapshot)}'s record from the next weekly run, which also affects its opponents."
            )
        else:
            notes.append(
                f"{team_link(team_id, snapshot)} is credited with two games on {short_date(day)}. One listing may belong to a "
                "same-named school; it is under review and affects that team and its opponents."
            )
    notes.append(
        "Opponent ranks in this article are the opponent's rank in this snapshot, not its rank on the day the game "
        "was played, unless a sentence says otherwise."
    )
    return notes


# ---------------------------------------------------------------------------
# article builders


def weekly_analysis(current: Snapshot, previous: Snapshot | None, data_root: Path) -> dict[str, Any]:
    season, week = current.meta["season"], current.week
    window_start = previous.cutoff_date if previous else None
    rows = sorted(current.rows, key=lambda row: row["state_rank"])
    top = rows[0]
    article = base_article(
        f"{season}-week-{week:02d}-weekly-analysis",
        f"Week {week} MFPI analysis: {top['team']} leads the statewide rankings",
        f"What moved in the Week {week} Mississippi Football Power Index, computed from verified results through "
        f"{short_date(current.cutoff_date)}.",
        current,
        "weekly-analysis",
    )

    leader_weeks = 0
    for back in range(week, 0, -1):
        snap = current if back == week else load_week(data_root, season, back)
        if snap is None or sorted(snap.rows, key=lambda r: r["state_rank"])[0]["team_id"] != top["team_id"]:
            break
        leader_weeks += 1

    paragraphs = []
    streak = f"for the {ordinal(leader_weeks)} straight published week" if leader_weeks > 1 else "for the first time this season"
    first = f"[[{top['team_id']}]] ({top['record']}) is No. 1 {streak}. {rating_sentence(top['mfpi'], display_rating_change(top))}"
    window = results_in_window(top, window_start, current.cutoff_date)
    if window:
        first += " In the latest window it " + "; it ".join(describe_result(top["team_id"], game, current) for game in window) + "."
    paragraphs.append(first)
    for row in rows[1:5]:
        sentence = f"No. {row['state_rank']} [[{row['team_id']}]] ({row['record']}, {row['classification']}): "
        sentence += rank_sentence(row["state_rank"], row.get("previous_state_rank")).replace("State ranking: ", "ranking ")
        sentence = sentence.rstrip(".") + "; " + rating_sentence(row["mfpi"], display_rating_change(row)).replace("MFPI rating: ", "rating ").rstrip(".")
        window = results_in_window(row, window_start, current.cutoff_date)
        sentence += (". It " + "; it ".join(describe_result(row["team_id"], game, current) for game in window) + ".") if window \
            else ". It had no verified result in this window."
        paragraphs.append(sentence)
    article["sections"].append({
        "heading": "The top of the statewide rankings",
        "paragraphs": paragraphs,
        "table": {
            "columns": ["Rank", "Team", "Class", "Record", "MFPI", "Rating change", "Rank move"],
            "rows": [
                [str(row["state_rank"]), f"[[{row['team_id']}]]", row["classification"], row["record"], f"{row['mfpi']:.1f}",
                 fmt_change(display_rating_change(row)), fmt_move(row.get("state_rank_change"))]
                for row in rows[:10]
            ],
        },
    })

    leaders, changed = [], []
    previous_leaders = {}
    if previous:
        for row in previous.rows:
            if row["class_rank"] == 1:
                previous_leaders[row["classification"]] = row["team_id"]
    for classification in ("7A", "6A", "5A", "4A", "3A", "2A", "1A"):
        leader = next(row for row in rows if row["classification"] == classification)
        leaders.append(leader)
        if previous_leaders.get(classification) and previous_leaders[classification] != leader["team_id"]:
            changed.append(f"Class {classification}: [[{leader['team_id']}]] replaced [[{previous_leaders[classification]}]] at No. 1.")
    class_paragraphs = [
        "Class ranks are the statewide order filtered to one classification; MFPI never recalculates a separate class rating."
    ]
    class_paragraphs.append(" ".join(changed) if changed else "Every classification kept the same No. 1 team as the previous week.")
    article["sections"].append({
        "heading": "Classification leaders",
        "paragraphs": class_paragraphs,
        "table": {
            "columns": ["Class", "No. 1", "Record", "State rank", "MFPI"],
            "rows": [[row["classification"], f"[[{row['team_id']}]]", row["record"], str(row["state_rank"]), f"{row['mfpi']:.1f}"] for row in leaders],
        },
    })

    movers = [row for row in rows if display_rating_change(row) is not None and results_in_window(row, window_start, current.cutoff_date)]
    gains = sorted(movers, key=lambda row: (-display_rating_change(row), row["state_rank"]))[:5]
    article["sections"].append({
        "heading": "Results that raised ratings most",
        "paragraphs": [
            "The largest rating increases among teams with a verified result in this window. A rating can also move without "
            "a game, because every opponent's rating is re-solved each week."
        ] + [
            f"[[{row['team_id']}]] (+{display_rating_change(row):.1f} to {row['mfpi']:.1f}, now No. {row['state_rank']}) "
            + "; ".join(describe_result(row["team_id"], game, current) for game in results_in_window(row, window_start, current.cutoff_date)) + "."
            for row in gains
        ] + [f"The full list of movers is in the [[risers-and-fallers:{season}-week-{week:02d}-risers-and-fallers]] analysis."],
    })

    sos = sorted(rows, key=lambda row: -row["components"]["sos"]["normalized"])[:5]
    up = sorted((row for row in rows if row.get("up_games", 0) >= 2), key=lambda row: (-row["class_schedule_delta"], row["state_rank"]))[:5]
    article["sections"].append({
        "heading": "Schedule strength",
        "paragraphs": [
            "MFPI strength of schedule is the average current rating of every completed opponent, expressed as a statewide "
            "percentile (100 is the strongest schedule in this week's field, not a perfect grade). The five strongest schedules: "
            + "; ".join(f"[[{row['team_id']}]] ({row['record']}, SOS percentile {row['components']['sos']['normalized']:.1f})" for row in sos) + ".",
            "Teams that have played furthest above their own classification (average class steps up, games up in class): "
            + "; ".join(f"[[{row['team_id']}]] ({row['classification']}, {row['class_schedule_delta']:+.2f}, {row['up_games']} up)" for row in up) + ".",
        ],
    })
    article["sections"].append({"heading": "Data notes and limitations", "paragraphs": data_notes(current)})
    article["limitations"] = [
        "Generated from the published snapshot; no games after the cutoff are included.",
        "Media Rank and Media Strength of Schedule contribute 20% of every rating; MFPI's own score-based model contributes 80%.",
        "No player, injury, coaching or game-narrative information is used or implied.",
    ]
    return article


def ordinal(value: int) -> str:
    suffix = "th" if 10 <= value % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(value % 10, "th")
    return f"{value}{suffix}"


def risers_and_fallers(current: Snapshot, previous: Snapshot | None) -> dict[str, Any]:
    season, week = current.meta["season"], current.week
    window_start = previous.cutoff_date if previous else None
    article = base_article(
        f"{season}-week-{week:02d}-risers-and-fallers",
        f"Week {week} risers and fallers in the MFPI",
        "The largest statewide rank moves this week, with the verified results and rating changes behind each one.",
        current,
        "risers-and-fallers",
    )
    comparable = [row for row in current.rows if row.get("state_rank_change") is not None]

    def entry(row: dict[str, Any]) -> str:
        games = results_in_window(row, window_start, current.cutoff_date)
        text = (
            f"[[{row['team_id']}]] ({row['classification']}, {row['record']}): "
            f"{rank_sentence(row['state_rank'], row.get('previous_state_rank'))} {rating_sentence(row['mfpi'], display_rating_change(row))} "
        )
        if games:
            text += "In the window it " + "; it ".join(describe_result(row["team_id"], game, current) for game in games) + "."
        elif row.get("bye_adjustment"):
            text += "It had a confirmed bye, so its score keeps 90% of last week's rating."
        else:
            text += "It had no verified result in the window; the move comes from other teams' results and re-solved opponent ratings."
        return text

    risers = sorted(comparable, key=lambda row: (-row["state_rank_change"], row["state_rank"]))[:8]
    fallers = sorted(comparable, key=lambda row: (row["state_rank_change"], row["state_rank"]))[:8]
    article["sections"].append({
        "heading": "How to read these moves",
        "paragraphs": [
            "Rank movement is last week's statewide rank minus this week's. Rating change is this week's displayed MFPI "
            "minus last week's. They are separate facts: in the middle of the table, where ratings are close together, a "
            "small rating change can move a team many places, and a team can hold its place while its rating changes.",
            f"Both compare the Week {week} snapshot with the latest audited Week {week - 1} snapshot"
            + (f" (formula {previous.meta['formula_version']})." if previous else "."),
        ],
    })
    article["sections"].append({
        "heading": "Biggest risers",
        "paragraphs": [entry(row) for row in risers],
        "table": table_for(risers),
    })
    article["sections"].append({
        "heading": "Biggest fallers",
        "paragraphs": [entry(row) for row in fallers],
        "table": table_for(fallers),
    })
    rating_only = [row for row in comparable if row["state_rank_change"] == 0 and abs(display_rating_change(row) or 0) >= 1.0]
    rank_only = [row for row in comparable if display_rating_change(row) == 0 and row["state_rank_change"] != 0]
    paragraphs = []
    if rating_only:
        paragraphs.append(
            "Held their rank while the rating changed by at least a point: "
            + "; ".join(f"[[{row['team_id']}]] (No. {row['state_rank']}, {fmt_change(display_rating_change(row))})" for row in rating_only[:8]) + "."
        )
    if rank_only:
        paragraphs.append(
            "Moved in the ranking with an unchanged displayed rating: "
            + "; ".join(f"[[{row['team_id']}]] ({fmt_move(row['state_rank_change'])} to No. {row['state_rank']})" for row in rank_only[:8]) + "."
        )
    if paragraphs:
        article["sections"].append({"heading": "Rank and rating moving separately", "paragraphs": paragraphs})
    article["sections"].append({"heading": "Data notes and limitations", "paragraphs": data_notes(current)})
    article["limitations"] = [
        "Movement is only shown against a comparable previous snapshot; teams without one are NEW.",
        "Large moves in the middle of the table often reflect tightly bunched ratings rather than dramatic results.",
    ]
    return article


def table_for(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "columns": ["Team", "Now", "Before", "Rank move", "MFPI", "Rating change"],
        "rows": [
            [f"[[{row['team_id']}]]", str(row["state_rank"]), str(row.get("previous_state_rank")), fmt_move(row["state_rank_change"]),
             f"{row['mfpi']:.1f}", fmt_change(display_rating_change(row))]
            for row in rows
        ],
    }


def performance_review(data_root: Path, season: int, through_week: int) -> dict[str, Any] | None:
    """Evaluate each published pregame ranking against the results that followed.

    Favorite: the team with the higher full-precision MFPI in the latest
    snapshot (original or audited correction) generated before the game's
    calendar date. Only games between two ranked MHSAA teams are evaluated.
    Results come from the most recent snapshot's verified results.
    """

    snapshots = [load_week(data_root, season, week) for week in range(1, through_week + 1)]
    if any(snapshot is None for snapshot in snapshots) or len(snapshots) < 2:
        return None
    latest = snapshots[-1]
    flagged = double_booked(latest)
    results: dict[tuple[date, str, str], dict[str, Any]] = {}
    for row in latest.rows:
        for game in row.get("game_results", []):
            results[(game_day(game), game["home"], game["away"])] = game

    windows, upsets, buckets = [], [], {"under 5": [0, 0], "5 to 15": [0, 0], "15 or more": [0, 0]}
    for pre, post in zip(snapshots, snapshots[1:]):
        ratings = {row["team_id"]: row["mfpi_unrounded"] for row in pre.rows}
        generated_day = pre.generated_at.astimezone(CENTRAL).date()
        evaluated = correct = excluded_external = excluded_equal = ties = excluded_flagged = 0
        for (day, home, away), game in sorted(results.items()):
            if not (pre.cutoff_date < day <= post.cutoff_date):
                continue
            if day <= generated_day:
                continue
            if home not in ratings or away not in ratings:
                excluded_external += 1
                continue
            if (home, day) in flagged or (away, day) in flagged:
                excluded_flagged += 1
                continue
            if ratings[home] == ratings[away]:
                excluded_equal += 1
                continue
            if game["home_score"] == game["away_score"]:
                ties += 1
                continue
            favorite = home if ratings[home] > ratings[away] else away
            winner = home if game["home_score"] > game["away_score"] else away
            gap = abs(ratings[home] - ratings[away])
            bucket = "under 5" if gap < 5 else "5 to 15" if gap < 15 else "15 or more"
            buckets[bucket][0] += 1
            evaluated += 1
            if winner == favorite:
                correct += 1
                buckets[bucket][1] += 1
            else:
                loser = favorite
                upsets.append((gap, day, winner, loser, game, pre.week))
        windows.append({
            "ranking": f"Week {pre.week} ({pre.meta['formula_version']}, published {pre.generated_at.astimezone(CENTRAL):%b %-d %-I:%M %p} CT)",
            "window": f"{short_date(pre.cutoff_date + (date.resolution))}-{short_date(post.cutoff_date)}",
            "evaluated": evaluated, "correct": correct,
            "excluded_external": excluded_external, "excluded_equal": excluded_equal,
            "excluded_flagged": excluded_flagged, "ties": ties,
        })

    total = sum(window["evaluated"] for window in windows)
    hits = sum(window["correct"] for window in windows)
    if not total:
        return None
    article = base_article(
        f"{season}-rankings-performance-review-weeks-1-{through_week - 1}",
        f"How MFPI's pregame rankings fared: Weeks 1-{through_week - 1} rankings against the games that followed",
        f"The higher-rated team won {hits} of {total} games between ranked MHSAA teams ({hits / total:.1%}), "
        "using only the rankings published before kickoff.",
        latest,
        "performance-review",
    )
    article["sections"].append({
        "heading": "What was measured",
        "paragraphs": [
            "For every game between two ranked MHSAA teams, the favorite is the team with the higher full-precision MFPI in "
            "the latest snapshot published before that game's date, including an audited correction if one was issued "
            "before kickoff. Later rankings and later corrections are never used to pick a favorite.",
            "A game counts as correct when the favorite won. Results are the verified final scores in the "
            f"Week {latest.week} snapshot. MFPI is a rating of past performance, not a betting line: home field, "
            "injuries and weather are not considered, and no point spread is implied.",
            "Excluded and disclosed below: games against non-MHSAA or out-of-state opponents (they have no MFPI rating), "
            "games where both teams had exactly equal ratings, tied games, and games involving a team credited with two "
            "games on the same date (a listing under review).",
        ],
    })
    article["sections"].append({
        "heading": "Results by ranking week",
        "paragraphs": [
            f"Across these windows the favorite won {hits} of {total} ({hits / total:.1%}). The Week 1 ranking was built "
            "from about one game per team plus the fading classification prior; the table shows each week's rate as published."
        ],
        "table": {
            "columns": ["Ranking used", "Games played", "Evaluated", "Favorite won", "Rate", "Non-MHSAA excluded", "Under review excluded", "Equal ratings", "Ties"],
            "rows": [
                [w["ranking"], w["window"], str(w["evaluated"]), str(w["correct"]),
                 f"{w['correct'] / w['evaluated']:.1%}" if w["evaluated"] else "—", str(w["excluded_external"]),
                 str(w["excluded_flagged"]), str(w["excluded_equal"]), str(w["ties"])]
                for w in windows
            ],
        },
    })
    article["sections"].append({
        "heading": "Bigger rating gaps were more reliable",
        "paragraphs": ["Games grouped by the pregame MFPI gap between the two teams."],
        "table": {
            "columns": ["Pregame rating gap", "Games", "Favorite won", "Rate"],
            "rows": [[label, str(n), str(k), f"{k / n:.1%}" if n else "—"] for label, (n, k) in buckets.items()],
        },
    })
    upsets.sort(key=lambda item: -item[0])
    article["sections"].append({
        "heading": "Largest upsets by pregame rating gap",
        "paragraphs": [
            f"[[{winner}]] beat [[{loser}]] {max(game['home_score'], game['away_score'])}-{min(game['home_score'], game['away_score'])} "
            f"on {short_date(day)}, overcoming a {gap:.1f}-point gap in the Week {week} ranking."
            for gap, day, winner, loser, game, week in upsets[:5]
        ],
    })
    article["sections"].append({"heading": "Data notes and limitations", "paragraphs": data_notes(latest) + [
        "Formula versions differed across these weeks (MFPI-3.0 to MFPI-3.2); each ranking is evaluated as it was published.",
        f"Samples are small ({total} games); a few results can move these percentages several points.",
    ]})
    article["limitations"] = [
        "Only games between two ranked MHSAA teams are evaluated.",
        "Uses the rankings actually published before kickoff; no hindsight inputs.",
    ]
    return article


# ---------------------------------------------------------------------------
# workflow


def article_path(slug: str, content_dir: Path = CONTENT_DIR) -> Path:
    return content_dir / f"{slug}.json"


def save_draft(article: dict[str, Any], content_dir: Path = CONTENT_DIR) -> tuple[Path, str]:
    content_dir.mkdir(parents=True, exist_ok=True)
    path = article_path(article["slug"], content_dir)
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        if existing.get("status") == "published":
            return path, "kept (already published; regenerate under a new slug for a correction)"
        article["review_notes"] = existing.get("review_notes", "")
    path.write_text(json.dumps(article, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path, "draft written"


def validate_article(article: dict[str, Any], known_team_ids: set[str] | None = None, now: datetime | None = None) -> list[str]:
    problems = []
    now = now or datetime.now(timezone.utc)
    status = article.get("status")
    mode = article.get("publication_mode", "reviewed")
    if status not in STATUSES:
        problems.append(f"unknown status {status!r}")
    if status == "published":
        if not article.get("published_at"):
            problems.append("published without published_at")
        if mode == "automated":
            if not (article.get("approved_by") or "").strip():
                problems.append("automated publication without a named approver")
            if article.get("reviewed_by") or article.get("reviewed_at"):
                problems.append("an automated article must not claim a human reviewer")
        else:
            if not (article.get("reviewed_by") or "").strip():
                problems.append("published without a named human reviewer")
            if article.get("reviewed_by") in {DRAFT_AUTHOR, AUTOMATED_AUTHOR}:
                problems.append("the automated author cannot be the reviewer")
            if not article.get("reviewed_at"):
                problems.append("published without reviewed_at")
            elif article.get("published_at") and datetime.fromisoformat(article["published_at"]) < datetime.fromisoformat(article["reviewed_at"]):
                problems.append("published before it was reviewed")
        if article.get("published_at"):
            published = datetime.fromisoformat(article["published_at"])
            if published > now:
                problems.append("publication date is in the future")
            if published < datetime.fromisoformat(article["snapshot_generated_at"]):
                problems.append("publication date precedes the data it describes (backdated)")
    elif article.get("reviewed_by") or article.get("published_at"):
        problems.append("a draft must not carry reviewer or publication fields")
    if known_team_ids is not None:
        text = json.dumps(article.get("sections", []))
        for team_id in set(_team_refs(text)) - known_team_ids:
            problems.append(f"links to unknown team {team_id!r}")
    return problems


def auto_publish(article: dict[str, Any], content_dir: Path = CONTENT_DIR, now: datetime | None = None) -> tuple[Path, str]:
    """Publish (or refresh) one automated article. Idempotent per snapshot run.

    A human-reviewed article is never replaced. An automated article is
    replaced only when its snapshot changed (an audited correction), keeping
    its original publication date and recording the update.
    """

    content_dir.mkdir(parents=True, exist_ok=True)
    path = article_path(article["slug"], content_dir)
    stamp = (now or datetime.now(timezone.utc)).astimezone(CENTRAL).isoformat(timespec="seconds")
    existing = json.loads(path.read_text(encoding="utf-8")) if path.exists() else None
    if existing and existing.get("status") == "published":
        if existing.get("publication_mode", "reviewed") != "automated":
            return path, "kept (human-reviewed)"
        if existing.get("snapshot_run_id") == article.get("snapshot_run_id"):
            return path, "unchanged"
    article.update(
        status="published",
        publication_mode="automated",
        author=AUTOMATED_AUTHOR,
        approved_by=STANDING_APPROVER,
        reviewed_by=None,
        reviewed_at=None,
        published_at=(existing or {}).get("published_at") if existing and existing.get("status") == "published" else stamp,
        updated_at=stamp if existing and existing.get("status") == "published" else None,
    )
    problems = validate_article(article, now=now)
    if problems:
        raise SystemExit(f"Refusing to publish {article['slug']}: " + "; ".join(problems))
    path.write_text(json.dumps(article, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path, "updated for a corrected snapshot" if existing and existing.get("status") == "published" else "published"


def build_articles(data_root: Path, season: int, week: int) -> tuple[list[dict[str, Any]], Snapshot]:
    current = load_week(data_root, season, week)
    if current is None:
        raise SystemExit(f"No published snapshot for {season} week {week}.")
    previous = load_week(data_root, season, week - 1) if week > 1 else None
    articles = [weekly_analysis(current, previous, data_root), risers_and_fallers(current, previous)]
    review = performance_review(data_root, season, week)
    if review:
        articles.append(review)
    return articles, current


def _team_refs(text: str) -> list[str]:
    return re.findall(r"\[\[([a-z0-9-]+)\]\]", text)


def publish(slug: str, reviewer: str, *, confirm: bool, content_dir: Path = CONTENT_DIR, now: datetime | None = None) -> dict[str, Any]:
    if not confirm:
        raise SystemExit("Refusing to publish: pass --confirm-reviewed after a person has read and checked the article.")
    reviewer = reviewer.strip()
    if not reviewer or reviewer == DRAFT_AUTHOR:
        raise SystemExit("Refusing to publish: --reviewer must name the person who reviewed the article.")
    path = article_path(slug, content_dir)
    article = json.loads(path.read_text(encoding="utf-8"))
    if article["status"] == "published":
        raise SystemExit(f"{slug} is already published (reviewed by {article['reviewed_by']}).")
    stamp = (now or datetime.now(timezone.utc)).astimezone(CENTRAL).isoformat(timespec="seconds")
    article.update(status="published", publication_mode="reviewed", author=article.get("author", DRAFT_AUTHOR),
                   reviewed_by=reviewer, reviewed_at=stamp, published_at=stamp)
    problems = validate_article(article, now=now)
    if problems:
        raise SystemExit("Refusing to publish: " + "; ".join(problems))
    path.write_text(json.dumps(article, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return article


def to_markdown(article: dict[str, Any], snapshot: Snapshot | None) -> str:
    def text(value: str) -> str:
        def repl(match: re.Match[str]) -> str:
            ref = match.group(1)
            if ref.startswith("risers-and-fallers:"):
                return "risers and fallers"
            row = snapshot.by_id.get(ref) if snapshot else None
            return row["team"] if row else ref
        return re.sub(r"\[\[([^\]]+)\]\]", repl, value)

    lines = [f"# {article['title']}", "", f"_{article['dek']}_", "",
             f"Status: **{article['status'].upper()}** · Reviewed by: {article.get('reviewed_by') or 'not yet reviewed'} · "
             f"Data: {article['season']} Week {article['week']} snapshot ({article['formula_version']})", ""]
    for section in article["sections"]:
        lines += [f"## {section['heading']}", ""]
        lines += [text(paragraph) + "\n" for paragraph in section.get("paragraphs", [])]
        table = section.get("table")
        if table:
            lines.append("| " + " | ".join(table["columns"]) + " |")
            lines.append("|" + "---|" * len(table["columns"]))
            lines += ["| " + " | ".join(text(cell) for cell in row) + " |" for row in table["rows"]]
            lines.append("")
    lines += ["## Sources", ""] + [f"- [{source['label']}]({source['url']})" for source in article["sources"]]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="MFPI Weekly Analysis drafts and review workflow.")
    parser.add_argument("--data-root", type=Path, default=Path("data"))
    parser.add_argument("--content-dir", type=Path, default=CONTENT_DIR)
    commands = parser.add_subparsers(dest="command", required=True)
    generate = commands.add_parser("generate", help="Write draft articles from published snapshots.")
    generate.add_argument("--season", type=int, default=2026)
    generate.add_argument("--week", type=int, required=True)
    generate.add_argument("--markdown-dir", type=Path, help="Also write reviewable Markdown copies here.")
    auto = commands.add_parser("auto", help="Generate and publish the week's automated analysis.")
    auto.add_argument("--season", type=int)
    auto.add_argument("--week", type=int, help="Defaults to the week in data/current.")
    commands.add_parser("list", help="List articles and their review status.")
    commands.add_parser("validate", help="Check every article's review metadata.")
    publish_cmd = commands.add_parser("publish", help="Mark an article reviewed and published.")
    publish_cmd.add_argument("slug")
    publish_cmd.add_argument("--reviewer", required=True, help="Full name of the person who reviewed the article.")
    publish_cmd.add_argument("--confirm-reviewed", action="store_true")
    args = parser.parse_args(argv)

    if args.command == "generate":
        articles, current = build_articles(args.data_root, args.season, args.week)
        for article in articles:
            path, outcome = save_draft(article, args.content_dir)
            print(f"{outcome}: {path}")
            if args.markdown_dir:
                args.markdown_dir.mkdir(parents=True, exist_ok=True)
                (args.markdown_dir / f"{article['slug']}.md").write_text(to_markdown(article, current), encoding="utf-8")
        return 0

    if args.command == "auto":
        meta = json.loads((args.data_root / "current" / "overall.json").read_text(encoding="utf-8"))["metadata"]
        season = args.season or int(meta["season"])
        week = args.week or int(meta["week"])
        articles, _ = build_articles(args.data_root, season, week)
        for article in articles:
            path, outcome = auto_publish(article, args.content_dir)
            print(f"{outcome}: {path}")
        return 0

    paths = sorted(args.content_dir.glob("*.json"))
    if args.command == "list":
        for path in paths:
            article = json.loads(path.read_text(encoding="utf-8"))
            print(f"{article['status']:<10} {article.get('publication_mode', 'reviewed'):<9} {article['slug']}  "
                  f"reviewed_by={article.get('reviewed_by') or '-'} approved_by={article.get('approved_by') or '-'}")
        return 0
    if args.command == "validate":
        failures = 0
        for path in paths:
            article = json.loads(path.read_text(encoding="utf-8"))
            snapshot = load_week(args.data_root, article["season"], article["week"])
            problems = validate_article(article, set(snapshot.by_id) if snapshot else None)
            for problem in problems:
                failures += 1
                print(f"{article['slug']}: {problem}", file=sys.stderr)
        print(f"{len(paths)} article(s) checked, {failures} problem(s).")
        return 1 if failures else 0
    article = publish(args.slug, args.reviewer, confirm=args.confirm_reviewed, content_dir=args.content_dir)
    print(f"Published {article['slug']} reviewed by {article['reviewed_by']} at {article['reviewed_at']}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
