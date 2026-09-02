from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Iterable, Mapping

from .models import Game


def adjusted_margin(raw_margin: float, location: str, margin_scale: float = 42.0, home_field: float = 2.0) -> float:
    capped = margin_scale * math.tanh(float(raw_margin) / margin_scale)
    if location == "HOME":
        return capped - home_field
    if location == "AWAY":
        return capped + home_field
    return capped


def perspective(game: Game, team_id: str, margin_scale: float = 42.0, home_field: float = 2.0) -> tuple[str, int, int, str]:
    if not game.completed:
        raise ValueError("Cannot evaluate an incomplete game")
    if game.home_team_id == team_id:
        location = "NEUTRAL" if game.neutral_site else "HOME"
        return game.away_team_id, int(game.home_score), int(game.away_score), location
    if game.away_team_id == team_id:
        location = "NEUTRAL" if game.neutral_site else "AWAY"
        return game.home_team_id, int(game.away_score), int(game.home_score), location
    raise ValueError(f"Team {team_id!r} did not play game {game.game_id!r}")


def solve_srs(
    team_ids: Iterable[str],
    games: Iterable[Game],
    priors: Mapping[str, float],
    prior_strengths: Mapping[str, float],
    ranked_team_ids: set[str],
    external_priors: Mapping[str, float] | None = None,
    *,
    margin_scale: float = 42.0,
    home_field: float = 2.0,
    tolerance: float = 0.01,
    max_iterations: int = 100,
) -> tuple[dict[str, float], int, bool]:
    ids = sorted(set(team_ids))
    by_team: dict[str, list[Game]] = defaultdict(list)
    for game in games:
        if game.completed:
            by_team[game.home_team_id].append(game)
            by_team[game.away_team_id].append(game)

    external_priors = external_priors or {}
    ratings = {team_id: float(external_priors.get(team_id, priors.get(team_id, 0.0))) for team_id in ids}
    if not ids:
        return ratings, 0, True

    converged = False
    for iteration in range(1, max_iterations + 1):
        updated: dict[str, float] = {}
        for team_id in ids:
            prior_weight = max(0.0, float(prior_strengths.get(team_id, 1.0)))
            prior_value = external_priors.get(team_id, priors.get(team_id, 0.0))
            numerator = prior_weight * float(prior_value)
            denominator = prior_weight
            for game in by_team.get(team_id, []):
                opponent_id, points_for, points_against, location = perspective(game, team_id)
                margin = adjusted_margin(points_for - points_against, location, margin_scale, home_field)
                numerator += ratings.get(opponent_id, 0.0) + margin
                denominator += 1.0
            updated[team_id] = numerator / denominator if denominator else 0.0

        center_values = [updated[team_id] for team_id in ranked_team_ids if team_id in updated]
        center = sum(center_values) / len(center_values) if center_values else 0.0
        updated = {team_id: value - center for team_id, value in updated.items()}
        max_change = max(abs(updated[team_id] - ratings.get(team_id, 0.0)) for team_id in ids)
        ratings = updated
        if max_change < tolerance:
            converged = True
            return ratings, iteration, converged
    return ratings, max_iterations, converged
