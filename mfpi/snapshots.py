from __future__ import annotations

import csv
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .config import FORMULA_VERSION
from .database import save_run
from .models import Game, RankingRow, Team, ValidationReport


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
    ranked = {row.team_id for row in rankings}
    played = {game.home_team_id for game in games} | {game.away_team_id for game in games}
    known = {team.team_id: team.display_name for team in teams}
    return {
        team_id: known[team_id]
        for team_id in sorted(played - ranked)
        if known.get(team_id)
    }


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
    _write_json_csv(archive, metadata, rankings)
    (archive / "validation.json").write_text(json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8")
    current = data_root / "current"
    _write_json_csv(current, metadata, rankings)
    (current / "validation.json").write_text(json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8")
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
    _write_json_csv(draft, metadata, rankings)
    (draft / "validation.json").write_text(json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8")

    current = data_root / "current"
    _write_json_csv(current, metadata, rankings)
    (current / "validation.json").write_text(json.dumps(report.to_dict(), indent=2) + "\n", encoding="utf-8")
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
