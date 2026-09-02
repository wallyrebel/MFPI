from __future__ import annotations

from datetime import datetime, timezone

import pytest

from mfpi.models import Game, Team


@pytest.fixture
def cutoff() -> datetime:
    return datetime(2026, 9, 2, 20, 30, tzinfo=timezone.utc)


def make_team(name: str, classification: str = "4A") -> Team:
    slug = name.lower().replace(" ", "-")
    return Team(slug, name.lower(), name, classification, "1", aliases=(name,))


def make_game(
    game_id: str,
    home: str,
    away: str,
    home_score: int,
    away_score: int,
    *,
    forfeit: bool = False,
) -> Game:
    return Game(
        game_id=game_id,
        date=datetime(2026, 8, 28, 19, 0, tzinfo=timezone.utc),
        home_team_id=home,
        away_team_id=away,
        home_score=home_score,
        away_score=away_score,
        verified=True,
        forfeit=forfeit,
        source_timestamp=datetime(2026, 8, 29, tzinfo=timezone.utc),
    )
