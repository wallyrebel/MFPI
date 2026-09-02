from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from .models import Game, RankingRow, Team, ValidationReport

SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS teams (
  team_id TEXT PRIMARY KEY, canonical_name TEXT NOT NULL, display_name TEXT NOT NULL,
  classification TEXT, region TEXT, city TEXT, state TEXT NOT NULL,
  aliases_json TEXT NOT NULL, active INTEGER NOT NULL, season INTEGER NOT NULL,
  source_team_id TEXT
);
CREATE TABLE IF NOT EXISTS games (
  game_id TEXT PRIMARY KEY, date TEXT NOT NULL, home_team_id TEXT NOT NULL,
  away_team_id TEXT NOT NULL, home_score INTEGER, away_score INTEGER,
  neutral_site INTEGER NOT NULL, overtime INTEGER NOT NULL, forfeit INTEGER NOT NULL,
  source TEXT NOT NULL, source_timestamp TEXT, verified INTEGER NOT NULL,
  status TEXT NOT NULL, expected_status TEXT, contest_type TEXT,
  FOREIGN KEY(home_team_id) REFERENCES teams(team_id),
  FOREIGN KEY(away_team_id) REFERENCES teams(team_id)
);
CREATE TABLE IF NOT EXISTS ranking_runs (
  run_id TEXT PRIMARY KEY, season INTEGER NOT NULL, week INTEGER NOT NULL,
  generated_at TEXT NOT NULL, cutoff_at TEXT NOT NULL, formula_version TEXT NOT NULL,
  status TEXT NOT NULL, validation_json TEXT NOT NULL, correction_of TEXT
);
CREATE TABLE IF NOT EXISTS rankings (
  run_id TEXT NOT NULL, team_id TEXT NOT NULL, state_rank INTEGER NOT NULL,
  class_rank INTEGER NOT NULL, mfpi REAL NOT NULL, record TEXT NOT NULL,
  previous_state_rank INTEGER, previous_class_rank INTEGER, previous_mfpi REAL,
  explanation TEXT NOT NULL, maxpreps_state_rank INTEGER, maxpreps_rating REAL,
  maxpreps_strength REAL, PRIMARY KEY(run_id, team_id),
  FOREIGN KEY(run_id) REFERENCES ranking_runs(run_id),
  FOREIGN KEY(team_id) REFERENCES teams(team_id)
);
CREATE TABLE IF NOT EXISTS component_scores (
  run_id TEXT NOT NULL, team_id TEXT NOT NULL, component TEXT NOT NULL,
  raw_value REAL, normalized_value REAL NOT NULL, weight REAL NOT NULL,
  contribution REAL NOT NULL, PRIMARY KEY(run_id, team_id, component),
  FOREIGN KEY(run_id, team_id) REFERENCES rankings(run_id, team_id)
);
"""


def save_run(
    path: Path,
    *,
    run_id: str,
    season: int,
    week: int,
    generated_at: datetime,
    cutoff: datetime,
    formula_version: str,
    status: str,
    report: ValidationReport,
    teams: list[Team],
    games: list[Game],
    rankings: list[RankingRow],
    correction_of: str | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.executescript(SCHEMA)
        ranking_columns = {row[1] for row in connection.execute("PRAGMA table_info(rankings)")}
        for name, data_type in (
            ("maxpreps_state_rank", "INTEGER"),
            ("maxpreps_rating", "REAL"),
            ("maxpreps_strength", "REAL"),
        ):
            if name not in ranking_columns:
                connection.execute(f"ALTER TABLE rankings ADD COLUMN {name} {data_type}")
        connection.executemany(
            """INSERT INTO teams VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(team_id) DO UPDATE SET canonical_name=excluded.canonical_name,
               display_name=excluded.display_name, classification=excluded.classification,
               region=excluded.region, city=excluded.city, aliases_json=excluded.aliases_json,
               active=excluded.active, season=excluded.season, source_team_id=excluded.source_team_id""",
            [
                (
                    team.team_id, team.canonical_name, team.display_name, team.classification,
                    team.region, team.city, team.state, json.dumps(team.aliases), int(team.active),
                    team.season, team.source_team_id,
                )
                for team in teams
            ],
        )
        connection.executemany(
            """INSERT INTO games VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(game_id) DO UPDATE SET date=excluded.date,
               home_score=excluded.home_score, away_score=excluded.away_score,
               source_timestamp=excluded.source_timestamp, verified=excluded.verified,
               status=excluded.status, expected_status=excluded.expected_status""",
            [
                (
                    game.game_id, game.date.isoformat(), game.home_team_id, game.away_team_id,
                    game.home_score, game.away_score, int(game.neutral_site), int(game.overtime),
                    int(game.forfeit), game.source,
                    game.source_timestamp.isoformat() if game.source_timestamp else None,
                    int(game.verified), game.status, game.expected_status, game.contest_type,
                )
                for game in games
            ],
        )
        connection.execute(
            "INSERT INTO ranking_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id, season, week, generated_at.isoformat(), cutoff.isoformat(), formula_version,
                status, json.dumps(report.to_dict(), sort_keys=True), correction_of,
            ),
        )
        connection.executemany(
            """INSERT INTO rankings (
                   run_id, team_id, state_rank, class_rank, mfpi, record,
                   previous_state_rank, previous_class_rank, previous_mfpi, explanation,
                   maxpreps_state_rank, maxpreps_rating, maxpreps_strength
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    run_id, row.team.team_id, row.state_rank, row.class_rank, row.mfpi,
                    row.record, row.previous_state_rank, row.previous_class_rank,
                    row.previous_mfpi, row.explanation, row.maxpreps_state_rank,
                    row.maxpreps_rating, row.maxpreps_strength,
                )
                for row in rankings
            ],
        )
        connection.executemany(
            "INSERT INTO component_scores VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    run_id, row.team.team_id, name, value.raw, value.normalized,
                    value.weight, value.contribution,
                )
                for row in rankings
                for name, value in row.components.items()
            ],
        )
