from __future__ import annotations

import csv
import json
import sqlite3
from dataclasses import replace

import pytest

from mfpi.config import Settings
from mfpi.engine import calculate_rankings
from mfpi.snapshots import publish_snapshot, write_provisional_snapshot
from mfpi.validation import validate_inputs

from conftest import make_game, make_team


@pytest.mark.parametrize("provisional", [False, True], ids=["published", "provisional"])
def test_snapshot_writes_real_rankings_and_external_opponent_names(tmp_path, cutoff, provisional) -> None:
    teams = [
        make_team("Alpha"),
        make_team("Beta"),
        replace(make_team("External Away"), classification=None, state="AL"),
        replace(make_team("External Home"), classification=None, state="TN"),
        replace(make_team("Unused Opponent"), classification=None),
    ]
    games = [
        make_game("home-game", "alpha", "external-away", 28, 14),
        make_game("away-game", "external-home", "beta", 7, 21),
    ]
    if provisional:
        games[1] = replace(games[1], home_score=None, away_score=None, status="UPCOMING", verified=False)
    settings = Settings()
    result = calculate_rankings(teams, games, cutoff, settings)
    report = validate_inputs(teams, games, cutoff, settings)
    assert result.converged
    assert report.valid is not provisional

    arguments = dict(
        season=2026,
        week=1,
        cutoff=cutoff,
        generated_at=cutoff,
        teams=teams,
        games=games,
        rankings=result.rankings,
        report=report,
        sources=[],
    )
    if provisional:
        archive = write_provisional_snapshot(tmp_path, run_id="provisional-test", **arguments)
    else:
        archive = publish_snapshot(tmp_path, **arguments)

    expected_status = "PROVISIONAL" if provisional else "PUBLISHED"
    for directory in (archive, tmp_path / "current"):
        for group in ("overall", "4a"):
            payload = json.loads((directory / f"{group}.json").read_text(encoding="utf-8"))
            assert payload["metadata"]["status"] == expected_status
            assert payload["metadata"]["opponent_names"] == {
                "external-away": "External Away",
                "external-home": "External Home",
            }
            assert {row["team_id"] for row in payload["rankings"]} == {"alpha", "beta"}
            with (directory / f"{group}.csv").open(encoding="utf-8", newline="") as handle:
                assert {row["team"] for row in csv.DictReader(handle)} == {"Alpha", "Beta"}
        assert json.loads((directory / "validation.json").read_text(encoding="utf-8")) == report.to_dict()

    with sqlite3.connect(tmp_path / "mfpi.sqlite3") as connection:
        assert connection.execute("SELECT status FROM ranking_runs").fetchone() == (expected_status,)
        assert connection.execute("SELECT COUNT(*) FROM rankings").fetchone() == (2,)
