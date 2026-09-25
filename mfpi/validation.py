from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime

from .config import Settings
from .dates import calendar_date
from .models import Game, Team, ValidationIssue, ValidationReport


PROVISIONAL_SAFE_CRITICAL_CODES = frozenset({"LOW_GAME_COVERAGE"})


def can_show_provisional(report: ValidationReport) -> bool:
    """Allow a live preview only when missing finals are the sole blocking issue."""

    critical_codes = {issue.code for issue in report.issues if issue.severity == "CRITICAL"}
    return bool(critical_codes) and critical_codes <= PROVISIONAL_SAFE_CRITICAL_CODES


def validate_inputs(
    teams: list[Team],
    games: list[Game],
    cutoff: datetime,
    settings: Settings,
    prior_issues: list[ValidationIssue] | None = None,
) -> ValidationReport:
    issues = list(prior_issues or [])
    ranked_ids = {team.team_id for team in teams if team.ranked}

    aliases: Counter[str] = Counter(alias for team in teams if team.ranked for alias in team.aliases)
    for alias, count in aliases.items():
        if count > 1:
            issues.append(ValidationIssue("DUPLICATE_TEAM_ALIAS", "CRITICAL", f"Alias {alias!r} belongs to {count} teams."))

    ids = Counter(game.game_id for game in games)
    for game_id, count in ids.items():
        if count > 1:
            issues.append(ValidationIssue("DUPLICATE_GAME_ID", "CRITICAL", f"Game {game_id} appears {count} times."))

    matchup_keys: Counter[tuple[str, str, str]] = Counter()
    expected: list[Game] = []
    verified: list[Game] = []
    for game in games:
        if game.home_team_id == game.away_team_id:
            issues.append(ValidationIssue("SELF_GAME", "CRITICAL", f"Game {game.game_id} lists the same team twice."))
        if game.date > cutoff and game.completed:
            issues.append(ValidationIssue("FUTURE_COMPLETED_GAME", "CRITICAL", f"Game {game.game_id} is completed after the cutoff."))
        for score in (game.home_score, game.away_score):
            if score is not None and (score < 0 or score > 150):
                issues.append(ValidationIssue("IMPOSSIBLE_SCORE", "CRITICAL", f"Game {game.game_id} has score {score}."))
        if game.completed:
            key = (game.date.date().isoformat(), *sorted((game.home_team_id, game.away_team_id)))
            matchup_keys[key] += 1

        contest = (game.contest_type or "").lower()
        excluded = any(label in contest for label in ("jamboree", "scrimmage"))
        touches_ranked_team = game.home_team_id in ranked_ids or game.away_team_id in ranked_ids
        cancelled = game.status in {"CANCELLED", "POSTPONED"}
        if touches_ranked_team and game.date <= cutoff and not excluded and not cancelled:
            expected.append(game)
            if game.completed and game.verified:
                verified.append(game)

    booked: dict[tuple[str, str], list[str]] = defaultdict(list)
    for game in games:
        if game.completed and game.date <= cutoff:
            day = calendar_date(game.date).isoformat()
            for team_id in (game.home_team_id, game.away_team_id):
                if team_id in ranked_ids:
                    booked[(team_id, day)].append(game.game_id)
    for (team_id, day), game_ids in sorted(booked.items()):
        if len(game_ids) > 1:
            issues.append(ValidationIssue(
                "TEAM_DOUBLE_BOOKED", "WARNING",
                f"{team_id} is credited with {len(game_ids)} completed games on {day}; one may belong to a same-named school.",
                {"team_id": team_id, "date": day, "game_ids": game_ids},
            ))

    for key, count in matchup_keys.items():
        if count > 1:
            issues.append(ValidationIssue("DUPLICATE_MATCHUP", "CRITICAL", f"Duplicate same-day matchup: {key}."))

    coverage = len(verified) / len(expected) if expected else 0.0
    missing_ids = [game.game_id for game in expected if not (game.completed and game.verified)]
    if coverage < settings.coverage_threshold:
        issues.append(
            ValidationIssue(
                "LOW_GAME_COVERAGE",
                "CRITICAL",
                f"Verified game coverage is {coverage:.1%}; {settings.coverage_threshold:.1%} is required.",
                {"missing_game_ids": missing_ids},
            )
        )
    elif missing_ids:
        issues.append(
            ValidationIssue(
                "UNVERIFIED_GAMES_REMAIN",
                "WARNING",
                f"Published coverage is {coverage:.1%}, with {len(missing_ids)} unresolved game listings retained.",
                {"missing_game_ids": missing_ids},
            )
        )

    return ValidationReport(
        issues=issues,
        expected_games=len(expected),
        verified_games=len(verified),
        missing_games=len(expected) - len(verified),
        coverage=coverage,
    )
