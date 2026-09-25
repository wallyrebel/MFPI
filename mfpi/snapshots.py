from __future__ import annotations

import csv
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import FORMULA_VERSION
from .database import save_run
from .dates import calendar_date
from .game_status import counts_toward_record, counts_toward_scoring, status_category
from .models import Game, RankingRow, Team, ValidationReport

MHSAA_SCORE_CENTER_URL = "https://scores.misshsaa.com/"


def load_previous(data_root: Path, season: int, week: int) -> dict[str, dict[str, Any]]:
    if week <= 1:
        return {}
    path = data_root / str(season) / f"week-{week - 1:02d}" / "overall.json"
    if not path.exists():
        return {}
    # Week N must inherit the latest audited publication of week N-1, never
    # the current week's earlier revision (which would repeatedly compound).
    revisions = sorted((path.parent / "corrections").glob("revision-*/overall.json"))
    if revisions:
        path = revisions[-1]
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {row["team_id"]: row for row in payload.get("rankings", [])}


def _payload(metadata: dict[str, Any], rankings: list[RankingRow]) -> dict[str, Any]:
    return {"metadata": metadata, "rankings": [row.to_dict() for row in rankings]}


def _write_json_csv(directory: Path, metadata: dict[str, Any], rankings: list[RankingRow]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    groups: dict[str, list[RankingRow]] = {"overall": rankings}
    for class_number in range(1, 8):
        class_name = f"{class_number}A"
        groups[class_name.lower()] = [row for row in rankings if row.team.classification == class_name]
    for name, rows in groups.items():
        (directory / f"{name}.json").write_text(json.dumps(_payload(metadata, rows), indent=2) + "\n", encoding="utf-8")
        with (directory / f"{name}.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "state_rank", "class_rank", "team", "classification", "record", "mfpi",
                    "state_rank_change", "class_rank_change", "mfpi_change", "sos", "pf_per_game",
                    "pa_per_game", "maxpreps_state_rank", "maxpreps_rating", "maxpreps_strength",
                    "schedule_direction", "class_schedule_delta", "up_games",
                    "same_class_games", "down_games",
                ],
            )
            writer.writeheader()
            for row in rows:
                item = row.to_dict()
                writer.writerow(
                    {
                        **{key: item.get(key) for key in writer.fieldnames},
                        "sos": round(row.components["sos"].normalized, 1),
                    }
                )


def _opponent_names(teams: list[Team], games: list[Game], rankings: list[RankingRow]) -> dict[str, str]:
    """Display names for opponents that appear in a schedule but are not ranked.

    Out-of-state and non-MHSAA opponents carry synthetic ids such as
    "external-254111". Published team pages list opponents by name, so without
    this map the raw id would surface on the public site.
    """
    ranked = {row.team.team_id for row in rankings}
    played = {game.home_team_id for game in games} | {game.away_team_id for game in games}
    known = {team.team_id: team.display_name for team in teams}
    return {
        team_id: known[team_id]
        for team_id in sorted(played - ranked)
        if known.get(team_id)
    }


def preview_payload(
    *, season: int, week: int, cutoff: datetime, generated_at: datetime, status: str,
    teams: list[Team], games: list[Game], rankings: list[RankingRow], report: ValidationReport,
) -> dict[str, Any]:
    """The overall.json payload a run would publish, built without writing it."""

    return _payload(
        {
            "season": season,
            "week": week,
            "generated_at": generated_at.isoformat(),
            "cutoff_at": cutoff.isoformat(),
            "formula_version": FORMULA_VERSION,
            "status": status,
            "coverage_percentage": round(report.coverage * 100, 2),
            "expected_games": report.expected_games,
            "verified_games": report.verified_games,
            "missing_games": report.missing_games,
            "opponent_names": _opponent_names(teams, games, rankings),
        },
        rankings,
    )


def game_ledger(teams: list[Team], games: list[Game], rankings: list[RankingRow], cutoff: datetime) -> dict[str, Any]:
    """Every listing that touches a ranked team, with its status category.

    Team pages use this to distinguish a verified result from a listing that
    is scheduled, postponed, cancelled, or still waiting for a score.
    """

    ranked = {row.team.team_id for row in rankings}
    names = {team.team_id: team.display_name for team in teams}
    rows = []
    for game in sorted(games, key=lambda item: (item.date, item.game_id)):
        if game.home_team_id not in ranked and game.away_team_id not in ranked:
            continue
        category = status_category(game, cutoff)
        scored = game.completed and game.verified and category in {"final", "forfeit"}
        rows.append({
            "game_id": game.game_id,
            "calendar_date": calendar_date(game.date).isoformat(),
            "kickoff": game.date.isoformat(),
            "home": game.home_team_id,
            "away": game.away_team_id,
            "home_name": names.get(game.home_team_id, game.home_team_id),
            "away_name": names.get(game.away_team_id, game.away_team_id),
            "neutral": game.neutral_site,
            # A score is published only for a verified result. An unscored
            # listing stays null; it is never rendered as 0-0.
            "home_score": game.home_score if scored else None,
            "away_score": game.away_score if scored else None,
            "status": game.status,
            "status_category": category,
            "counts_toward_record": counts_toward_record(game, cutoff),
            "counts_toward_scoring": counts_toward_scoring(game, cutoff),
            "overtime": game.overtime,
            "forfeit": game.forfeit,
            "verified": game.verified,
            "source": game.source,
            "source_url": MHSAA_SCORE_CENTER_URL if game.source == "mhsaa_score_center" else None,
            "source_timestamp": game.source_timestamp.isoformat() if game.source_timestamp else None,
        })
    return {"cutoff_at": cutoff.isoformat(), "games": rows}


def _write_ledger(directory: Path, ledger: dict[str, Any] | None) -> None:
    if ledger is not None:
        (directory / "games.json").write_text(json.dumps(ledger, indent=1) + "\n", encoding="utf-8")


def _replace_current(data_root: Path, write: Any) -> None:
    """Write data/current in a staging directory, then swap it in.

    A failure part-way through leaves the previous current snapshot intact
    instead of a mix of old and new files.
    """

    current = data_root / "current"
    staging = data_root / ".current-staging"
    retired = data_root / ".current-retired"
    for leftover in (staging, retired):
        if leftover.exists():
            shutil.rmtree(leftover)
    staging.mkdir(parents=True)
    write(staging)
    if current.exists():
        os.replace(current, retired)
    os.replace(staging, current)
    if retired.exists():
        shutil.rmtree(retired)


def publish_snapshot(
    data_root: Path,
    *,
    season: int,
    week: int,
    cutoff: datetime,
    generated_at: datetime,
    teams: list[Team],
    games: list[Game],
    rankings: list[RankingRow],
    report: ValidationReport,
    sources: list[dict[str, Any]],
    audit: dict[str, Any] | None = None,
    corrected: bool = False,
) -> Path:
    if not report.valid:
        raise ValueError("Refusing to publish an invalid ranking run")
    base_archive = data_root / str(season) / f"week-{week:02d}"
    correction_of: str | None = None
    status = "PUBLISHED"
    archive = base_archive
    if base_archive.exists():
        if not corrected:
            raise FileExistsError(f"Immutable snapshot already exists: {base_archive}")
        corrections = base_archive / "corrections"
        revision = 1
        while (corrections / f"revision-{revision:02d}").exists():
            revision += 1
        archive = corrections / f"revision-{revision:02d}"
        correction_of = f"{season}-week-{week:02d}"
        status = "CORRECTED"
    run_id = f"{season}-week-{week:02d}-{generated_at.strftime('%Y%m%dT%H%M%S%fZ')}"
    metadata = {
        "season": season,
        "week": week,
        "generated_at": generated_at.isoformat(),
        "cutoff_at": cutoff.isoformat(),
        "formula_version": FORMULA_VERSION,
        "status": status,
        "run_id": run_id,
        "data_sources": sources,
        "validation_status": "VALIDATED",
        "coverage_percentage": round(report.coverage * 100, 2),
        "expected_games": report.expected_games,
        "verified_games": report.verified_games,
        "missing_games": report.missing_games,
        "opponent_names": _opponent_names(teams, games, rankings),
    }
    ledger = game_ledger(teams, games, rankings, cutoff)

    def write(directory: Path) -> None:
        _write_json_csv(directory, metadata, rankings)
        (directory / "validation.json").write_text(json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8")
        _write_ledger(directory, ledger)
        if audit is not None:
            (directory / "audit.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")

    write(archive)
    _replace_current(data_root, write)
    save_run(
        data_root / "mfpi.sqlite3",
        run_id=run_id,
        season=season,
        week=week,
        generated_at=generated_at,
        cutoff=cutoff,
        formula_version=FORMULA_VERSION,
        status=status,
        report=report,
        teams=teams,
        games=games,
        rankings=rankings,
        correction_of=correction_of,
    )
    return archive


def write_provisional_snapshot(
    data_root: Path,
    *,
    run_id: str,
    season: int,
    week: int,
    cutoff: datetime,
    generated_at: datetime,
    teams: list[Team],
    games: list[Game],
    rankings: list[RankingRow],
    report: ValidationReport,
    sources: list[dict[str, Any]],
    audit: dict[str, Any] | None = None,
    corrected: bool = False,
) -> Path:
    """Show a complete live ranking while a small number of finals remain unverified."""

    if report.valid:
        raise ValueError("A valid run should be published, not marked provisional")
    metadata = {
        "season": season,
        "week": week,
        "generated_at": generated_at.isoformat(),
        "cutoff_at": cutoff.isoformat(),
        "formula_version": FORMULA_VERSION,
        "status": "PROVISIONAL",
        "run_id": run_id,
        "data_sources": sources,
        "validation_status": "PROVISIONAL",
        "coverage_percentage": round(report.coverage * 100, 2),
        "expected_games": report.expected_games,
        "verified_games": report.verified_games,
        "missing_games": report.missing_games,
        "opponent_names": _opponent_names(teams, games, rankings),
    }
    draft = data_root / "drafts" / run_id
    ledger = game_ledger(teams, games, rankings, cutoff)

    def write(directory: Path) -> None:
        _write_json_csv(directory, metadata, rankings)
        (directory / "validation.json").write_text(json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8")
        _write_ledger(directory, ledger)
        if audit is not None:
            (directory / "audit.json").write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")

    write(draft)
    # Archive the week too, so the weekly archive, movement and analysis keep
    # working. An existing archive is never overwritten: a correction run adds
    # a revision, and an ordinary rerun only refreshes data/current.
    base_archive = data_root / str(season) / f"week-{week:02d}"
    if not base_archive.exists():
        write(base_archive)
    elif corrected:
        revision = 1
        while (base_archive / "corrections" / f"revision-{revision:02d}").exists():
            revision += 1
        write(base_archive / "corrections" / f"revision-{revision:02d}")
    _replace_current(data_root, write)
    save_run(
        data_root / "mfpi.sqlite3",
        run_id=run_id,
        season=season,
        week=week,
        generated_at=generated_at,
        cutoff=cutoff,
        formula_version=FORMULA_VERSION,
        status="PROVISIONAL",
        report=report,
        teams=teams,
        games=games,
        rankings=rankings,
    )
    return draft


def write_demo_preview(
    data_root: Path,
    *,
    season: int,
    week: int,
    cutoff: datetime,
    generated_at: datetime,
    rankings: list[RankingRow],
    report: ValidationReport,
    sources: list[dict[str, Any]],
) -> Path:
    """Refresh local sample data without creating or replacing official history."""

    if not report.valid:
        raise ValueError("Refusing to write an invalid demo preview")
    current = data_root / "current"
    existing = current / "overall.json"
    if existing.exists():
        payload = json.loads(existing.read_text(encoding="utf-8"))
        if payload.get("metadata", {}).get("status") not in {"DEMO", "PUBLISHED"}:
            raise FileExistsError("Refusing to replace an unrecognized current snapshot with demo data")
        if payload.get("metadata", {}).get("status") == "PUBLISHED" and not any(
            source.get("name") == "demo_fixture" for source in payload.get("metadata", {}).get("data_sources", [])
        ):
            raise FileExistsError("Refusing to replace an official current snapshot with demo data")
    metadata = {
        "season": season,
        "week": week,
        "generated_at": generated_at.isoformat(),
        "cutoff_at": cutoff.isoformat(),
        "formula_version": FORMULA_VERSION,
        "status": "DEMO",
        "run_id": f"demo-{generated_at.strftime('%Y%m%dT%H%M%S%fZ')}",
        "data_sources": sources,
        "validation_status": "DEMO_VALIDATED",
        "coverage_percentage": round(report.coverage * 100, 2),
    }
    _write_json_csv(current, metadata, rankings)
    (current / "validation.json").write_text(json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8")
    return current


def write_draft_report(data_root: Path, run_id: str, report: ValidationReport) -> Path:
    path = data_root / "drafts" / run_id
    path.mkdir(parents=True, exist_ok=True)
    (path / "validation.json").write_text(json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8")
    return path
