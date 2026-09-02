from __future__ import annotations

from datetime import datetime, timezone

from .models import Game, Team


def demo_dataset() -> tuple[list[Team], list[Game]]:
    specs = [
        ("tupelo", "Tupelo", "7A", "1"),
        ("oxford", "Oxford", "7A", "2"),
        ("starkville", "Starkville", "7A", "2"),
        ("oak-grove", "Oak Grove", "7A", "3"),
        ("hattiesburg", "Hattiesburg", "6A", "3"),
        ("laurel", "Laurel", "5A", "3"),
        ("louisville", "Louisville", "4A", "4"),
        ("west-point", "West Point", "5A", "1"),
        ("ripley", "Ripley", "4A", "3"),
        ("mooreville", "Mooreville", "4A", "2"),
    ]
    teams = [
        Team(team_id=slug, canonical_name=name.lower(), display_name=name, classification=classification, region=region, aliases=(name,))
        for slug, name, classification, region in specs
    ]
    game_specs = [
        ("demo-1", "tupelo", "oxford", 28, 14),
        ("demo-2", "oak-grove", "starkville", 15, 17),
        ("demo-3", "hattiesburg", "laurel", 31, 18),
        ("demo-4", "west-point", "louisville", 6, 21),
        ("demo-5", "ripley", "mooreville", 34, 23),
    ]
    game_date = datetime(2026, 8, 28, 19, 0, tzinfo=timezone.utc)
    games = [
        Game(
            game_id=game_id,
            date=game_date,
            home_team_id=home,
            away_team_id=away,
            home_score=home_score,
            away_score=away_score,
            source="demo_fixture",
            source_timestamp=game_date,
            verified=True,
        )
        for game_id, home, away, home_score, away_score in game_specs
    ]
    return teams, games
