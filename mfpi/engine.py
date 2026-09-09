from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

from .config import BYE_PREVIOUS_WEIGHT, COMPONENTS, Settings, class_prior_points, weights_for_games
from .byes import result_fingerprint, unchanged_results
from .models import ComponentValue, Game, MaxPrepsSignal, RankingRow, Team
from .normalize import robust_percentiles
from .srs import adjusted_margin, perspective, solve_srs


@dataclass(frozen=True)
class EngineResult:
    rankings: list[RankingRow]
    srs: dict[str, float]
    iterations: int
    converged: bool


def _result_value(points_for: int, points_against: int) -> float:
    if points_for > points_against:
        return 1.0
    if points_for == points_against:
        return 0.5
    return 0.0


def _prior_strength(games_played: int, ranked: bool) -> float:
    if not ranked:
        return 1.0
    if games_played <= 2:
        return 2.0
    if games_played <= 5:
        return 1.0
    return 0.25


def _class_number(team: Team | None) -> int | None:
    if team and team.classification and len(team.classification) == 2 and team.classification[0].isdigit():
        return int(team.classification[0])
    return None


def _head_to_head_score(team_id: str, tied_ids: set[str], games: list[Game]) -> float:
    score = 0.0
    for game in games:
        if not game.completed or {game.home_team_id, game.away_team_id} - tied_ids:
            continue
        if team_id not in {game.home_team_id, game.away_team_id}:
            continue
        _, points_for, points_against, _ = perspective(game, team_id)
        score += _result_value(points_for, points_against)
    return score


def _apply_tie_breakers(rows: list[RankingRow], games: list[Game]) -> list[RankingRow]:
    rows.sort(
        key=lambda row: (
            -row.mfpi,
            -row.components["performance"].normalized,
            -row.components["sos"].normalized,
            row.team.display_name,
        )
    )
    output: list[RankingRow] = []
    index = 0
    while index < len(rows):
        end = index + 1
        key = (
            rows[index].mfpi,
            rows[index].components["performance"].normalized,
            rows[index].components["sos"].normalized,
        )
        while end < len(rows):
            candidate = (
                rows[end].mfpi,
                rows[end].components["performance"].normalized,
                rows[end].components["sos"].normalized,
            )
            if any(abs(a - b) > 1e-10 for a, b in zip(key, candidate)):
                break
            end += 1
        group = rows[index:end]
        tied_ids = {row.team.team_id for row in group}
        group.sort(
            key=lambda row: (
                -_head_to_head_score(row.team.team_id, tied_ids, games),
                -row.capped_margin,
                row.team.display_name,
            )
        )
        output.extend(group)
        index = end
    return output


def calculate_rankings(
    teams: list[Team],
    games: list[Game],
    cutoff: datetime,
    settings: Settings,
    previous: dict[str, dict] | None = None,
    maxpreps: dict[str, MaxPrepsSignal] | None = None,
    external_ratings: dict[str, float] | None = None,
    confirmed_bye_team_ids: set[str] | None = None,
) -> EngineResult:
    maxpreps = maxpreps or {}
    external_ratings = external_ratings or {}
    ranked_teams = [team for team in teams if team.ranked]
    ranked_ids = {team.team_id for team in ranked_teams}
    completed_games = [game for game in games if game.completed and game.verified and game.date <= cutoff]
    by_team: dict[str, list[Game]] = defaultdict(list)
    for game in completed_games:
        by_team[game.home_team_id].append(game)
        by_team[game.away_team_id].append(game)
    for team_games in by_team.values():
        team_games.sort(key=lambda game: (game.date, game.game_id))

    teams_by_id = {team.team_id: team for team in teams}
    priors = {team.team_id: class_prior_points(team.classification) for team in teams}
    prior_strengths = {
        team.team_id: _prior_strength(len(by_team.get(team.team_id, [])), team.ranked) for team in teams
    }
    external_priors = {
        team_id: max(-20.0, min(20.0, (rating - 50.0) * 0.4))
        for team_id, rating in external_ratings.items()
        if team_id in teams_by_id
    }
    for team_id in external_priors:
        prior_strengths[team_id] = 2.0
    srs, iterations, converged = solve_srs(
        [team.team_id for team in teams],
        completed_games,
        priors,
        prior_strengths,
        ranked_ids,
        external_priors,
        margin_scale=settings.margin_scale,
        home_field=settings.home_field_points,
        tolerance=settings.convergence_tolerance,
        max_iterations=settings.max_iterations,
    )

    raw: dict[str, dict[str, float | None]] = {component: {} for component in COMPONENTS}
    stats: dict[str, dict[str, float | int]] = {}
    custom_sos: dict[str, float | None] = {}

    for team in ranked_teams:
        team_games = by_team.get(team.team_id, [])
        wins = losses = ties = points_for = points_against = capped_pf = 0
        game_performances: list[tuple[datetime, float]] = []
        opponent_ratings: list[float] = []
        class_deltas: list[int] = []
        up_games = same_class_games = down_games = 0
        capped_margin_total = 0.0
        for game in team_games:
            opponent_id, pf, pa, location = perspective(game, team.team_id)
            result = _result_value(pf, pa)
            wins += int(result == 1.0)
            losses += int(result == 0.0)
            ties += int(result == 0.5)
            points_for += pf
            points_against += pa
            capped_pf += min(pf, settings.offense_cap)
            margin = adjusted_margin(pf - pa, location, settings.margin_scale, settings.home_field_points)
            capped_margin_total += margin
            opponent_rating = srs.get(opponent_id, 0.0)
            opponent_ratings.append(opponent_rating)
            game_performance = opponent_rating + margin
            game_performances.append((game.date, game_performance))
            team_class = _class_number(team)
            opponent_class = _class_number(teams_by_id.get(opponent_id))
            if team_class is not None and opponent_class is not None:
                delta = opponent_class - team_class
                class_deltas.append(delta)
                up_games += int(delta > 0)
                same_class_games += int(delta == 0)
                down_games += int(delta < 0)

        played = len(team_games)
        record_value = (wins + 0.5 * ties) / played if played else None
        raw["performance"][team.team_id] = srs.get(team.team_id, 0.0)
        raw["record"][team.team_id] = record_value
        raw["offense"][team.team_id] = capped_pf / played if played else None
        raw["defense"][team.team_id] = (
            sum(settings.defense_cap - min(perspective(game, team.team_id)[2], settings.defense_cap) for game in team_games) / played
            if played
            else None
        )
        recent = list(reversed(game_performances[-3:]))
        if recent:
            used_weights = settings.recent_weights[: len(recent)]
            raw["recent"][team.team_id] = sum(value * weight for (_, value), weight in zip(recent, used_weights)) / sum(used_weights)
        else:
            raw["recent"][team.team_id] = None
        custom_sos[team.team_id] = statistics.fmean(opponent_ratings) if opponent_ratings else None
        raw["sos"][team.team_id] = custom_sos[team.team_id]
        maxpreps_signal = maxpreps.get(team.team_id)
        raw["maxpreps_rank"][team.team_id] = -float(maxpreps_signal.state_rank) if maxpreps_signal else None
        raw["maxpreps_sos"][team.team_id] = (
            maxpreps_signal.strength if maxpreps_signal and maxpreps_signal.strength != 0.0 else None
        )
        stats[team.team_id] = {
            "games": played,
            "wins": wins,
            "losses": losses,
            "ties": ties,
            "pf": points_for,
            "pa": points_against,
            "capped_pf": capped_pf,
            "capped_margin": capped_margin_total,
            "up_games": up_games,
            "same_class_games": same_class_games,
            "down_games": down_games,
            "class_schedule_delta": statistics.fmean(class_deltas) if class_deltas else 0.0,
        }

    normalized = {name: robust_percentiles(values) for name, values in raw.items()}

    rows: list[RankingRow] = []
    for team in ranked_teams:
        team_id = team.team_id
        weights = weights_for_games(int(stats[team_id]["games"]))
        components: dict[str, ComponentValue] = {}
        mfpi = 0.0
        for name in COMPONENTS:
            norm = normalized[name][team_id]
            contribution = norm * weights[name]
            components[name] = ComponentValue(raw=raw[name][team_id], normalized=norm, weight=weights[name], contribution=contribution)
            mfpi += contribution
        mfpi = min(100.0, max(1.0, mfpi))
        rows.append(
            RankingRow(
                team=team,
                games_played=int(stats[team_id]["games"]),
                wins=int(stats[team_id]["wins"]),
                losses=int(stats[team_id]["losses"]),
                ties=int(stats[team_id]["ties"]),
                points_for=int(stats[team_id]["pf"]),
                points_against=int(stats[team_id]["pa"]),
                capped_points_for=int(stats[team_id]["capped_pf"]),
                capped_margin=float(stats[team_id]["capped_margin"]),
                up_games=int(stats[team_id]["up_games"]),
                same_class_games=int(stats[team_id]["same_class_games"]),
                down_games=int(stats[team_id]["down_games"]),
                class_schedule_delta=float(stats[team_id]["class_schedule_delta"]),
                components=components,
                mfpi=mfpi,
                game_results=result_fingerprint(by_team.get(team_id, [])),
                maxpreps_state_rank=maxpreps.get(team_id).state_rank if team_id in maxpreps else None,
                maxpreps_rating=maxpreps.get(team_id).rating if team_id in maxpreps else None,
                maxpreps_strength=maxpreps.get(team_id).strength if team_id in maxpreps else None,
            )
        )

    previous = previous or {}
    for row in rows:
        old = previous.get(row.team.team_id)
        if row.team.team_id not in (confirmed_bye_team_ids or set()) or not old or not unchanged_results(row, old):
            continue
        old_score = old.get("mfpi_unrounded", old.get("mfpi"))
        if not isinstance(old_score, (int, float)) or not 1 <= old_score <= 100:
            continue
        recalculated = row.mfpi
        row.mfpi = BYE_PREVIOUS_WEIGHT * old_score + (1 - BYE_PREVIOUS_WEIGHT) * recalculated
        row.bye_adjustment = {
            "previous_weight": BYE_PREVIOUS_WEIGHT, "previous_mfpi": old_score,
            "recalculated_mfpi": recalculated, "adjustment": row.mfpi - recalculated,
            "reason": "Confirmed bye; no new or changed verified results.",
        }
    rows = _apply_tie_breakers(rows, completed_games)
    class_counts: dict[str, int] = defaultdict(int)
    previous = previous or {}
    for state_rank, row in enumerate(rows, 1):
        row.state_rank = state_rank
        class_name = row.team.classification or ""
        class_counts[class_name] += 1
        row.class_rank = class_counts[class_name]
        old = previous.get(row.team.team_id)
        if old:
            row.previous_state_rank = old.get("state_rank")
            row.previous_class_rank = old.get("class_rank")
            row.previous_mfpi = old.get("mfpi_unrounded", old.get("mfpi"))
            movement = row.previous_state_rank - row.state_rank if row.previous_state_rank else 0
            direction = "rose" if movement > 0 else "fell" if movement < 0 else "held"
            row.explanation = (
                f"{row.team.display_name} {direction} to No. {row.state_rank} with an MFPI of {row.mfpi:.1f}. "
                f"Its opponent-adjusted performance is {row.components['performance'].normalized:.1f}, SOS is "
                f"{row.components['sos'].normalized:.1f}, Media Rank is "
                f"{f'No. {row.maxpreps_state_rank}' if row.maxpreps_state_rank else 'unavailable'}, and its schedule "
                f"includes {row.up_games} game(s) up in class."
            )
        else:
            row.explanation = (
                f"{row.team.display_name} enters at No. {row.state_rank} with an MFPI of {row.mfpi:.1f}; "
                f"opponent-adjusted performance contributes {row.components['performance'].contribution:.2f} points and "
                f"Media Rank and Strength of Schedule contribute {row.components['maxpreps_rank'].contribution + row.components['maxpreps_sos'].contribution:.2f} "
                f"points. The schedule has {row.up_games} up, {row.same_class_games} same-class, and {row.down_games} down game(s)."
            )
        if row.bye_adjustment:
            row.explanation += " Confirmed bye: MFPI retains 90% of last week's score plus 10% of this week's recalculation."
    return EngineResult(rows, srs, iterations, converged)
