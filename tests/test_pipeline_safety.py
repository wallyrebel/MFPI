"""End-to-end safety of the weekly pipeline with stubbed (synthetic) sources."""

from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone

import pytest

from conftest import make_team
from mfpi import cli
from mfpi.config import CENTRAL
from mfpi.models import RawGame
from mfpi.providers import MaxPrepsFetch, MaxPrepsScoreFetch, ScoreFetch


def raw(game_id, home, away, day, score):
    return RawGame(
        game_id=game_id, date=datetime(2026, 8, day, 19, tzinfo=CENTRAL), home_name=home, away_name=away,
        home_source_id=None, away_source_id=None, home_score=score[0], away_score=score[1], status="COMPLETED",
    )


@pytest.fixture
def stub_sources(monkeypatch):
    state = {
        "teams": [make_team("Alpha"), make_team("Beta"), make_team("Gamma"), make_team("Delta")],
        "games": [raw("1", "Alpha", "Beta", 28, (21, 7)), raw("2", "Gamma", "Delta", 28, (14, 10))],
    }
    now = datetime(2026, 9, 1, 17, tzinfo=timezone.utc)

    class Classifications:
        def fetch(self, *args, **kwargs):
            return list(state["teams"])

    class MediaRankings:
        def fetch(self, *args, **kwargs):
            return MaxPrepsFetch([], now, None)

        def fetch_state(self, *args, **kwargs):
            return []

    class Scores:
        def fetch_range(self, *args, **kwargs):
            return ScoreFetch(list(state["games"]), now, [])

    class SecondaryScores:
        def fetch(self, *args, **kwargs):
            return MaxPrepsScoreFetch([], now, [])

    monkeypatch.setattr(cli, "MHSAAClassificationProvider", Classifications)
    monkeypatch.setattr(cli, "MaxPrepsRankingProvider", MediaRankings)
    monkeypatch.setattr(cli, "MHSAAOfficialScoreProvider", Scores)
    monkeypatch.setattr(cli, "MaxPrepsScoreProvider", SecondaryScores)
    monkeypatch.setattr(cli, "reconcile_maxpreps", lambda teams, rows: ({}, []))
    return state


def run(tmp_path, week, capsys):
    code = cli.main(["--live", "--week", str(week), "--data-root", str(tmp_path)])
    return code, json.loads(capsys.readouterr().out)


def test_valid_run_publishes_ledger_and_audit(tmp_path, stub_sources, capsys) -> None:
    code, summary = run(tmp_path, 1, capsys)
    assert code == 0 and summary["status"] == "PUBLISHED"
    assert summary["audit"]["blocking"] == 0
    current = tmp_path / "current"
    ledger = json.loads((current / "games.json").read_text())
    assert {game["calendar_date"] for game in ledger["games"]} == {"2026-08-28"}
    assert json.loads((current / "audit.json").read_text())["outcome"] in {"PASS", "PASS_WITH_WARNINGS"}
    assert (tmp_path / "2026" / "week-01" / "games.json").exists()
    assert not (tmp_path / ".current-staging").exists()


def test_team_disappearing_from_a_source_keeps_last_valid_snapshot(tmp_path, stub_sources, capsys) -> None:
    assert run(tmp_path, 1, capsys)[1]["status"] == "PUBLISHED"
    before = (tmp_path / "current" / "overall.json").read_text()

    # A partial classification response drops a team. It must not vanish from the site.
    stub_sources["teams"] = stub_sources["teams"][:3]
    stub_sources["games"] = stub_sources["games"][:1]
    code, summary = run(tmp_path, 2, capsys)
    assert code == 2 and summary["status"] == "DRAFT"
    assert (tmp_path / "current" / "overall.json").read_text() == before
    draft_audit = json.loads((Path(summary["draft"]) / "audit.json").read_text())
    assert "TEAM_DISAPPEARED" in {issue["code"] for issue in draft_audit["issues"]}
    assert not (tmp_path / "2026" / "week-02").exists()


def test_rerun_of_published_week_is_refused_not_overwritten(tmp_path, stub_sources, capsys) -> None:
    run(tmp_path, 1, capsys)
    archived = (tmp_path / "2026" / "week-01" / "overall.json").read_text()
    with pytest.raises(FileExistsError):
        cli.main(["--live", "--week", "1", "--data-root", str(tmp_path)])
    capsys.readouterr()
    assert (tmp_path / "2026" / "week-01" / "overall.json").read_text() == archived


def test_conflicting_duplicate_listing_still_publishes_the_week(tmp_path, stub_sources, capsys) -> None:
    # Two listings of the same game disagree on the score: the week still
    # publishes (provisional), the game is not counted, and the week is archived.
    stub_sources["games"] = stub_sources["games"] + [
        RawGame(game_id="1b", date=datetime(2026, 8, 28, 19, tzinfo=CENTRAL), home_name="Alpha", away_name="Beta",
                home_source_id=None, away_source_id=None, home_score=28, away_score=7, status="COMPLETED"),
    ]
    code, summary = run(tmp_path, 1, capsys)
    assert code == 0 and summary["status"] == "PROVISIONAL"
    archived = json.loads((tmp_path / "2026" / "week-01" / "overall.json").read_text())
    assert archived["metadata"]["status"] == "PROVISIONAL"
    rows = {row["team_id"]: row for row in archived["rankings"]}
    assert rows["alpha"]["games_played"] == 0 and rows["gamma"]["record"] == "1-0"
    validation = json.loads((tmp_path / "current" / "validation.json").read_text())
    assert "QUARANTINED_CONFLICTING_MATCHUP" in {issue["code"] for issue in validation["issues"]}


def test_provisional_week_feeds_the_next_weeks_movement(tmp_path, stub_sources, capsys) -> None:
    unscored = RawGame(game_id="9", date=datetime(2026, 8, 29, 19, tzinfo=CENTRAL), home_name="Beta", away_name="Delta",
                       home_source_id=None, away_source_id=None, home_score=None, away_score=None, status="UPCOMING")
    stub_sources["games"] = stub_sources["games"] + [unscored]
    assert run(tmp_path, 1, capsys)[1]["status"] == "PROVISIONAL"  # 2 of 3 games verified
    stub_sources["games"] = stub_sources["games"][:2]
    code, summary = run(tmp_path, 2, capsys)
    assert code == 0 and summary["status"] == "PUBLISHED"
    current = json.loads((tmp_path / "current" / "overall.json").read_text())
    assert all(row["previous_state_rank"] is not None for row in current["rankings"])
