from __future__ import annotations

from collections import defaultdict
from dataclasses import replace

from .dates import calendar_date
from .matching import TeamMatcher, normalize_name, reviewed_game_side, reviewed_identity, team_slug
from .models import (
    Game,
    MaxPrepsRanking,
    MaxPrepsScoreObservation,
    MaxPrepsSignal,
    RawGame,
    Team,
    ValidationIssue,
)
from urllib.parse import parse_qs, urljoin, urlparse
from .providers import MAXPREPS_ROOT


def reconcile_games(
    official_teams: list[Team], raw_games: list[RawGame]
) -> tuple[list[Team], list[Game], list[ValidationIssue]]:
    matcher = TeamMatcher(official_teams)
    teams_by_id = {team.team_id: team for team in official_teams}
    external: dict[str, Team] = {}
    issues: list[ValidationIssue] = []

    reported_identities: set[tuple[str, str]] = set()
    source_ids_by_team: dict[str, dict[str, set[str]]] = defaultdict(dict)

    def resolve(name: str, source_id: str | None, city: str, source: str) -> Team:
        identity = reviewed_identity(source, source_id, name)
        if identity is not None and identity.team_id is None:
            external_id = f"external-{source_id}"
            if ("not", str(source_id)) not in reported_identities:
                reported_identities.add(("not", str(source_id)))
                issues.append(ValidationIssue(
                    "REVIEWED_EXTERNAL_IDENTITY", "WARNING",
                    f"Kept source team {name!r} ({source} {source_id}) external: reviewed as a different school.",
                    {"source_team_id": source_id, "incoming": name, "evidence": identity.evidence},
                ))
            return external.setdefault(external_id, Team(
                team_id=external_id, canonical_name=normalize_name(name), display_name=name,
                classification=None, city=city, active=True, source_team_id=source_id,
            ))
        if identity is not None:
            official = teams_by_id.get(identity.team_id)
            corroborated = identity.city is None or (bool(city) and normalize_name(city) == normalize_name(identity.city))
            key = (identity.source_team_id, "applied" if corroborated and official else "skipped")
            if official is not None and official.ranked and corroborated:
                if key not in reported_identities:
                    reported_identities.add(key)
                    issues.append(ValidationIssue(
                        "REVIEWED_IDENTITY_APPLIED", "WARNING",
                        f"Linked source team {name!r} ({source} {source_id}, {city}) to {official.display_name}.",
                        {"team_id": official.team_id, "source": source, "source_team_id": source_id,
                         "incoming": name, "city": city, "evidence": identity.evidence},
                    ))
                if not official.source_team_id or not official.city:
                    teams_by_id[official.team_id] = replace(
                        official, city=official.city or city,
                        source_team_id=official.source_team_id or source_id,
                    )
                return teams_by_id[official.team_id]
            if key not in reported_identities:
                reported_identities.add(key)
                issues.append(ValidationIssue(
                    "REVIEWED_IDENTITY_NOT_CORROBORATED", "WARNING",
                    f"Source team {name!r} ({source} {source_id}) matches a reviewed identity for "
                    f"{identity.team_id}, but its city {city!r} does not confirm it; kept as an external opponent.",
                    {"team_id": identity.team_id, "source_team_id": source_id, "incoming": name, "city": city},
                ))
        team, confidence, method = matcher.match(name)
        if team is not None:
            if source_id:
                source_ids_by_team[team.team_id].setdefault(str(source_id), set()).add(f"{name} | {city}")
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
    def reviewed_external(raw: RawGame, side_name: str, source_id: str | None, city: str) -> Team | None:
        side = reviewed_game_side(raw.source, calendar_date(raw.date).isoformat(), raw.home_name, raw.away_name)
        if side is None or normalize_name(side_name) != side.external_name:
            return None
        external_id = f"external-{source_id}-{team_slug(side.display_name)}" if source_id else f"external-{team_slug(side.display_name)}"
        issues.append(ValidationIssue(
            "REVIEWED_EXTERNAL_GAME_SIDE", "WARNING",
            f"Kept {side_name!r} in game {raw.game_id} external: reviewed as a different school.",
            {"game_id": raw.game_id, "source_team_id": source_id, "evidence": side.evidence},
        ))
        return external.setdefault(external_id, Team(
            team_id=external_id, canonical_name=normalize_name(side.display_name), display_name=side.display_name,
            classification=None, city=city, active=True, source_team_id=source_id,
        ))

    for raw in raw_games:
        home = reviewed_external(raw, raw.home_name, raw.home_source_id, raw.home_city) \
            or resolve(raw.home_name, raw.home_source_id, raw.home_city, raw.source)
        away = reviewed_external(raw, raw.away_name, raw.away_source_id, raw.away_city) \
            or resolve(raw.away_name, raw.away_source_id, raw.away_city, raw.source)
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
    teams_in_game = {game.game_id: (game.home_team_id, game.away_team_id) for game in games}
    for team_id, source_ids in sorted(source_ids_by_team.items()):
        if len(source_ids) > 1:
            # One MHSAA program matched by name from several source team IDs is
            # how a same-named school from another state gets merged into a
            # Mississippi team's schedule. Report it; do not guess which is right.
            issues.append(ValidationIssue(
                "MULTIPLE_SOURCE_IDS_FOR_TEAM", "WARNING",
                f"{teams_by_id[team_id].display_name} matched {len(source_ids)} different source team IDs by name.",
                {"team_id": team_id, "source_ids": {key: sorted(value) for key, value in source_ids.items()},
                 "games": [
                     {"game_id": raw.game_id, "date": raw.date.isoformat(),
                      "home": raw.home_name, "home_source_id": raw.home_source_id,
                      "away": raw.away_name, "away_source_id": raw.away_source_id}
                     for raw in raw_games
                     if team_id in teams_in_game.get(raw.game_id, ())
                 ]},
            ))
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

    # The consolidated 2026 Leake program has a new media profile. The old
    # Leake Central page remains in the table with a 0-0 record. Only retire
    # that exact placeholder when the verified successor is also present.
    leake_successors = [
        row for row in rankings
        if row.team_name == "Leake"
        and parse_qs(urlparse(row.team_url).query).get("schoolid")
        == ["80480779-619d-4cd9-9feb-c26005e4201f"]
    ]
    for row in rankings:
        if (
            len(leake_successors) == 1
            and row.team_name == "Leake Central"
            and row.record == "0-0"
            and urlparse(row.team_url).path.rstrip("/") == "/ms/carthage/leake-central-gators/football"
        ):
            issues.append(ValidationIssue(
                "RETIRED_MAXPREPS_PROFILE", "WARNING",
                "Used the consolidated Leake program's media profile instead of its retired 0-0 listing.",
                {"team_id": "leake-central", "retired_url": row.team_url,
                 "active_url": leake_successors[0].team_url},
            ))
            continue
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
            # A rescheduled contest can leave an unfinished old listing next
            # to the official final under a new ID. Corroborate the actual
            # date and score before discarding only the stale listing.
            official_finals = [
                other for other in games
                if other.game_id != game.game_id and other.completed and other.verified
                and {other.home_team_id, other.away_team_id} == primary_pair
                and other.date.date() == observation.date.date()
            ]
            if len(official_finals) == 1:
                final = official_finals[0]
                official_scores = {final.home_team_id: final.home_score, final.away_team_id: final.away_score}
                secondary_scores = {home_id: observation.home_score, away_id: observation.away_score}
                if official_scores == secondary_scores and final.forfeit == observation.forfeit:
                    issues.append(ValidationIssue(
                        "STALE_RESCHEDULED_LISTING", "WARNING",
                        f"Excluded stale MHSAA listing {game.game_id}; official final {final.game_id} is independently corroborated.",
                        {**audit, "retained_mhsaa_game_id": final.game_id,
                         "home_score": observation.home_score, "away_score": observation.away_score},
                    ))
                    continue
                issues.append(ValidationIssue(
                    "MAXPREPS_SCORE_CONFLICT", "CRITICAL",
                    f"Secondary evidence for {game.game_id} conflicts with official final {final.game_id}.",
                    {**audit, "official_game_id": final.game_id,
                     "official_scores": official_scores, "secondary_scores": secondary_scores},
                ))
                output.append(game)
                continue
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


def reconcile_external_maxpreps_ratings(
    teams: list[Team], observations: list[MaxPrepsScoreObservation], rankings_by_state: dict[str, list[MaxPrepsRanking]]
) -> dict[str, float]:
    """Attach published MaxPreps ratings to non-Mississippi opponents."""
    by_name = {normalize_name(team.display_name): team for team in teams if not team.ranked}
    ratings: dict[str, float] = {}
    for observation in observations:
        for name, team_url in ((observation.home_name, observation.home_url), (observation.away_name, observation.away_url)):
            absolute = urljoin(MAXPREPS_ROOT, team_url)
            parts = [part for part in urlparse(absolute).path.split("/") if part]
            if len(parts) < 2 or parts[0].lower() == "ms":
                continue
            state = parts[0].lower()
            team = by_name.get(normalize_name(name))
            if team is None or not team_url:
                continue
            target = urlparse(absolute).path.rstrip("/").lower()
            matches = [row for row in rankings_by_state.get(state, []) if urlparse(urljoin(MAXPREPS_ROOT, row.team_url)).path.rstrip("/").lower() == target]
            if matches:
                ratings[team.team_id] = matches[0].rating
    return ratings
