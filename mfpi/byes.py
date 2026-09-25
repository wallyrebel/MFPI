from __future__ import annotations

from datetime import datetime, timedelta

from .config import CENTRAL
from .dates import calendar_date
from .models import Game, MaxPrepsScoreObservation, RankingRow


def confirmed_byes(
    games: list[Game], observations: list[MaxPrepsScoreObservation],
    cutoff: datetime, fresh_team_ids: set[str],
) -> set[str]:
    """A fresh team schedule must bracket an empty week; feed absence alone is not a bye."""
    start = cutoff - timedelta(days=7)
    eligible = set()
    for team_id in fresh_team_ids:
        schedule = [item for item in observations if item.observed_from_team_id == team_id]
        if not any(item.date <= start for item in schedule) or not any(item.date > cutoff for item in schedule):
            continue
        # Even a cancellation/postponement is not automatically a confirmed bye.
        if any(start < item.date <= cutoff for item in schedule):
            continue
        primary = [game for game in games if team_id in {game.home_team_id, game.away_team_id}]
        if any(start < game.date <= cutoff for game in primary):
            continue
        if any(game.date <= cutoff and not (game.completed and game.verified) for game in primary):
            continue
        eligible.add(team_id)
    return eligible


# Football facts compared for bye protection. Snapshot rows also carry the
# game ID, source and calendar date for display and auditing; those are
# provenance, not results, and never break a bye comparison.
FINGERPRINT_FACTS = ("date", "home", "away", "home_score", "away_score", "neutral", "overtime", "forfeit")


def result_fingerprint(games: list[Game]) -> list[dict]:
    return sorted([
        {"date": game.date.astimezone(CENTRAL).isoformat(),
         "home": game.home_team_id, "away": game.away_team_id,
         "home_score": game.home_score, "away_score": game.away_score,
         "neutral": game.neutral_site, "overtime": game.overtime, "forfeit": game.forfeit,
         "calendar_date": calendar_date(game.date).isoformat(),
         "game_id": game.game_id, "source": game.source}
        for game in games
    ], key=lambda item: (item["date"], item["home"], item["away"]))


def _facts(rows: list[dict]) -> list[dict]:
    return [{key: row.get(key) for key in FINGERPRINT_FACTS} for row in rows]


def unchanged_results(row: RankingRow, previous: dict) -> bool:
    if row.games_played == 0 or previous.get("games_played") != row.games_played:
        return False
    if "game_results" in previous:
        return _facts(previous["game_results"]) == _facts(row.game_results)
    # Legacy week-one snapshots lack game-level evidence. Limit migration to
    # one game, where recorded averages are exact scores, and require every
    # available result/schedule statistic to agree. Later snapshots use the
    # complete fingerprint above, including opponent and corrected game facts.
    if row.games_played != 1:
        return False
    current = row.to_dict()
    fields = ("record", "pf_per_game", "pa_per_game", "up_games", "same_class_games",
              "down_games", "class_schedule_delta")
    return all(previous.get(key) == current[key] for key in fields) and all(
        previous.get("components", {}).get(name, {}).get("raw") == current["components"][name]["raw"]
        for name in ("record", "offense", "defense")
    )
