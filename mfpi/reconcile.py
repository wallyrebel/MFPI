from __future__ import annotations

from dataclasses import replace

from .matching import TeamMatcher, normalize_name, team_slug
from .models import (
    Game,
    MaxPrepsRanking,
    MaxPrepsScoreObservation,
    MaxPrepsSignal,
    RawGame,
    Team,
    ValidationIssue,
)


def reconcile_games(
    official_teams: list[Team], raw_games: list[RawGame]
) -> tuple[list[Team], list[Game], list[ValidationIssue]]:
    matcher = TeamMatcher(official_teams)
    teams_by_id = {team.team_id: team for team in official_teams}
    external: dict[str, Team] = {}
    issues: list[ValidationIssue] = []

    def resolve(name: str, source_id: str | None, city: str) -> Team:
        team, confidence, method = matcher.match(name)
        if team is not None:
            if method == "fuzzy":
                issues.append(
                    ValidationIssue(
                        "FUZZY_TEAM_MATCH",
                        "WARNING",
                        f"Matched {name!r} to {team.display_name!r} at {confidence:.3f} confidence.",
                        {"incoming": name, "team_id": team.team_id, "confidence": confidence},
                    )
                )
            if (not team.city and city) or (not team.source_team_id and source_id):
                updated = replace(team, city=team.city or city, source_team_id=team.source_team_id or source_id)
                teams_by_id[team.team_id] = updated
                return updated
            return teams_by_id[team.team_id]
        external_id = f"external-{source_id}" if source_id else f"external-{team_slug(name)}"
        if method == "ambiguous":
            issues.append(
                ValidationIssue(
                    "AMBIGUOUS_TEAM_MATCH",
                    "CRITICAL",
                    f"Could not confidently match {name!r} to the official MHSAA list.",
                    {"incoming": name, "confidence": confidence},
                )
            )
        elif confidence >= 0.78:
            issues.append(
                ValidationIssue(
                    "POSSIBLE_UNMATCHED_MHSAA_TEAM",
                    "WARNING",
                    f"Kept {name!r} as an external opponent; review the official alias list.",
                    {"incoming": name, "confidence": confidence},
                )
            )
        external.setdefault(
            external_id,
            Team(
                team_id=external_id,
                canonical_name=normalize_name(name),
                display_name=name,
                classification=None,
                city=city,
                active=True,
                source_team_id=source_id,
            ),
        )
        return external[external_id]

    games: list[Game] = []
    for raw in raw_games:
        home = resolve(raw.home_name, raw.home_source_id, raw.home_city)
        away = resolve(raw.away_name, raw.away_source_id, raw.away_city)
        if not home.ranked and not away.ranked:
            continue
        games.append(
            Game(
                game_id=raw.game_id,
                date=raw.date,
                home_team_id=home.team_id,
                away_team_id=away.team_id,
                home_score=raw.home_score,
                away_score=raw.away_score,
                neutral_site=raw.neutral_site,
                overtime=raw.overtime,
                forfeit=raw.forfeit,
                source=raw.source,
                source_timestamp=raw.source_timestamp,
                verified=raw.status == "COMPLETED" and raw.home_score is not None and raw.away_score is not None,
                status=raw.status,
                expected_status=raw.expected_status,
                contest_type=raw.contest_type,
            )
        )
    all_teams = list(teams_by_id.values()) + list(external.values())
    return all_teams, games, issues


def reconcile_maxpreps(
    official_teams: list[Team], rankings: list[MaxPrepsRanking]
) -> tuple[dict[str, MaxPrepsSignal], list[ValidationIssue]]:
    """Match the statewide media table to active MHSAA programs exactly once."""

    matcher = TeamMatcher(official_teams)
    ranked_ids = {team.team_id for team in official_teams if team.ranked}
    signals: dict[str, MaxPrepsSignal] = {}
    issues: list[ValidationIssue] = []

    for row in rankings:
        incoming_name = row.team_name
        normalized = normalize_name(row.team_name)
        location = row.team_url.lower()
        if normalized == "enterprise":
            if "/brookhaven/" in location:
                incoming_name = "Enterprise Brookhaven"
            elif "/enterprise/" in location:
                incoming_name = "Enterprise Clarke"
        team, confidence, method = matcher.match(incoming_name)
        if team is None or team.team_id not in ranked_ids:
            continue
        if team.team_id in signals:
            issues.append(
                ValidationIssue(
                    "DUPLICATE_MAXPREPS_TEAM",
                    "CRITICAL",
                    f"More than one media-ranking row matched {team.display_name}.",
                    {"team_id": team.team_id, "incoming": row.team_name},
                )
            )
            continue
        if method == "fuzzy":
            issues.append(
                ValidationIssue(
                    "FUZZY_MAXPREPS_TEAM_MATCH",
                    "WARNING",
                    f"Matched media-ranking team {row.team_name!r} to {team.display_name!r} at {confidence:.3f} confidence.",
                    {"team_id": team.team_id, "incoming": row.team_name, "confidence": confidence},
                )
            )
        signals[team.team_id] = MaxPrepsSignal(
            team_id=team.team_id,
            state_rank=row.state_rank,
            rating=row.rating,
            strength=row.strength,
            source_name=row.team_name,
            source_url=row.team_url,
        )

    missing = sorted(ranked_ids - signals.keys())
    if missing:
        issues.append(
            ValidationIssue(
                "MISSING_MAXPREPS_TEAMS",
                "CRITICAL",
                f"Media-ranking data matched {len(signals)} of {len(ranked_ids)} active MHSAA teams.",
                {"missing_team_ids": missing},
            )
        )
    return signals, issues


def supplement_games_with_maxpreps(
    teams: list[Team],
    games: list[Game],
    observations: list[MaxPrepsScoreObservation],
    cutoff,
) -> tuple[list[Game], list[ValidationIssue]]:
    """Fill only unresolved MHSAA listings from exact secondary matchup evidence."""

    matcher = TeamMatcher(teams)
    resolved_observations: list[tuple[MaxPrepsScoreObservation, str, str]] = []
    issues: list[ValidationIssue] = []

    for observation in observations:
        home, _, _ = matcher.match(observation.home_name)
        away, _, _ = matcher.match(observation.away_name)
        if home is None or away is None or home.team_id == away.team_id:
            continue
        resolved_observations.append((observation, home.team_id, away.team_id))

    recovered: list[dict] = []
    terminal_statuses: list[dict] = []
    used_event_ids: dict[str, str] = {}
    output: list[Game] = []

    for game in games:
        unresolved = (
            game.date <= cutoff
            and not game.completed
            and game.status not in {"CANCELLED", "POSTPONED"}
        )
        if not unresolved:
            output.append(game)
            continue

        primary_pair = {game.home_team_id, game.away_team_id}
        candidates = [
            (observation, home_id, away_id)
            for observation, home_id, away_id in resolved_observations
            if {home_id, away_id} == primary_pair
            and abs((observation.date.date() - game.date.date()).days) <= 1
            and (
                observation.status in {"CANCELLED", "POSTPONED"}
                or observation.status == "COMPLETED"
                and observation.home_score is not None
                and observation.away_score is not None
            )
        ]
        if not candidates:
            output.append(game)
            continue

        def fact(candidate: tuple[MaxPrepsScoreObservation, str, str]):
            observation, home_id, away_id = candidate
            if observation.status != "COMPLETED":
                return (observation.status,)
            scores = tuple(
                sorted(
                    (
                        (home_id, observation.home_score),
                        (away_id, observation.away_score),
                    )
                )
            )
            return (observation.status, observation.forfeit, scores)

        facts = {fact(candidate) for candidate in candidates}
        if len(facts) != 1:
            issues.append(
                ValidationIssue(
                    "MAXPREPS_SCORE_CONFLICT",
                    "CRITICAL",
                    f"The secondary source has conflicting terminal results for MHSAA game {game.game_id}.",
                    {
                        "mhsaa_game_id": game.game_id,
                        "observations": [candidate[0].to_dict() for candidate in candidates],
                    },
                )
            )
            output.append(game)
            continue

        candidates.sort(
            key=lambda candidate: (
                abs((candidate[0].date.date() - game.date.date()).days),
                candidate[0].source_url,
            )
        )
        observation, home_id, away_id = candidates[0]
        previous_use = used_event_ids.get(observation.game_id)
        if previous_use is not None and previous_use != game.game_id:
            issues.append(
                ValidationIssue(
                    "MAXPREPS_EVENT_REUSED",
                    "CRITICAL",
                    f"Secondary event {observation.game_id} matched more than one MHSAA listing.",
                    {"first_mhsaa_game_id": previous_use, "second_mhsaa_game_id": game.game_id},
                )
            )
            output.append(game)
            continue
        used_event_ids[observation.game_id] = game.game_id

        source_urls = sorted({candidate[0].source_url for candidate in candidates})
        audit = {
            "mhsaa_game_id": game.game_id,
            "maxpreps_game_id": observation.game_id,
            "original_date": game.date.isoformat(),
            "maxpreps_date": observation.date.isoformat(),
            "home_team_id": home_id,
            "away_team_id": away_id,
            "source_urls": source_urls,
        }
        if observation.status == "COMPLETED":
            updated = replace(
                game,
                date=observation.date,
                home_team_id=home_id,
                away_team_id=away_id,
                home_score=observation.home_score,
                away_score=observation.away_score,
                forfeit=observation.forfeit,
                source="maxpreps_secondary",
                source_timestamp=observation.retrieved_at,
                verified=True,
                status="COMPLETED",
            )
            recovered.append(
                {
                    **audit,
                    "home_score": observation.home_score,
                    "away_score": observation.away_score,
                    "forfeit": observation.forfeit,
                }
            )
        else:
            updated = replace(
                game,
                date=observation.date,
                home_team_id=home_id,
                away_team_id=away_id,
                home_score=None,
                away_score=None,
                source="maxpreps_secondary",
                source_timestamp=observation.retrieved_at,
                verified=False,
                status=observation.status,
            )
            terminal_statuses.append({**audit, "status": observation.status})
        output.append(updated)

    if recovered:
        issues.append(
            ValidationIssue(
                "MAXPREPS_SECONDARY_RESULTS_USED",
                "WARNING",
                f"Used exact secondary matchup evidence for {len(recovered)} MHSAA listings without official finals.",
                {"games": recovered},
            )
        )
    if terminal_statuses:
        issues.append(
            ValidationIssue(
                "MAXPREPS_SECONDARY_STATUS_USED",
                "WARNING",
                f"Used secondary-source cancellation/postponement status for {len(terminal_statuses)} MHSAA listings.",
                {"games": terminal_statuses},
            )
        )
    return output, issues
