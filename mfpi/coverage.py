"""Compare the entire secondary schedule with imported games, without changing results.

Aggregate coverage only measures listings the primary feed returned. This check
also exposes games absent from that feed and legacy opponents kept external.
Ranked identities come from exact reconciled profile URLs, never fuzzy names.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from urllib.parse import urljoin, urlparse

from .dates import calendar_date
from .models import Game, MaxPrepsScoreObservation, MaxPrepsSignal, Team, ValidationIssue


def profile_key(url: str) -> str | None:
    parsed = urlparse(urljoin("https://www.maxpreps.com", url))
    if parsed.scheme != "https" or parsed.hostname != "www.maxpreps.com":
        return None
    path = parsed.path.rstrip("/").lower()
    # A local/team query URL cannot establish a canonical profile identity.
    return path if path.endswith("/football") else None


def audit_schedule_coverage(
    teams: list[Team], games: list[Game], observations: list[MaxPrepsScoreObservation],
    signals: dict[str, MaxPrepsSignal], cutoff: datetime, season_start: date,
    fresh_team_ids: set[str],
) -> list[ValidationIssue]:
    ranked_ids = {team.team_id for team in teams if team.ranked}
    profile_ids: dict[str, set[str]] = defaultdict(set)
    for team_id, signal in signals.items():
        key = profile_key(signal.source_url)
        if key and team_id in ranked_ids:
            profile_ids[key].add(team_id)

    def resolve(url: str) -> str | None:
        ids = profile_ids.get(profile_key(url), set())
        return next(iter(ids)) if len(ids) == 1 else None

    events: dict[str, list[MaxPrepsScoreObservation]] = defaultdict(list)
    for item in observations:
        if (item.observed_from_team_id in fresh_team_ids
                and season_start <= calendar_date(item.date) <= calendar_date(cutoff)
                and item.date <= cutoff):
            events[item.game_id].append(item)

    issues: list[ValidationIssue] = []
    for event_id, reports in sorted(events.items()):
        item = reports[0]
        home, away = resolve(item.home_url), resolve(item.away_url)
        pair = {home, away}
        if item.observed_from_team_id not in pair or home == away:
            continue
        facts = {
            (calendar_date(r.date), profile_key(r.home_url), profile_key(r.away_url),
             r.status, r.home_score, r.away_score, r.forfeit)
            for r in reports
        }
        evidence = {
            "secondary_game_id": event_id,
            "date": calendar_date(item.date).isoformat(),
            "home": home or item.home_name, "away": away or item.away_name,
            "home_url": item.home_url, "away_url": item.away_url,
            "source_urls": sorted({r.source_url for r in reports}),
            "observed_from_team_ids": sorted({r.observed_from_team_id for r in reports}),
            "status": item.status, "home_score": item.home_score, "away_score": item.away_score,
        }
        if len(facts) > 1:
            issues.append(ValidationIssue(
                "SECONDARY_SCHEDULE_DISAGREEMENT", "WARNING",
                f"Secondary schedule reports disagree for event {event_id}; review the source facts.",
                {**evidence, "reports": [r.to_dict() for r in reports]},
            ))
            continue
        # External opponents have no media-table identity. A primary listing
        # containing the known ranked side on this date still establishes
        # coverage; it does not justify assigning the external name to a team.
        if home is None or away is None:
            known = home or away
            listings = [g for g in games if known in {g.home_team_id, g.away_team_id}
                        and abs((calendar_date(g.date) - calendar_date(item.date)).days) <= 1]
            if not listings:
                issues.append(ValidationIssue(
                    "SECONDARY_OPPONENT_UNRESOLVED", "WARNING",
                    f"A secondary listing for {known} has no primary listing and no verified opponent identity.", evidence,
                ))
            continue
        listings = [g for g in games if {g.home_team_id, g.away_team_id} == pair
                    and abs((calendar_date(g.date) - calendar_date(item.date)).days) <= 1]
        if not listings:
            issues.append(ValidationIssue(
                "MISSING_PRIMARY_SCHEDULE_GAME",
                "WARNING" if item.status in {"CANCELLED", "POSTPONED"} else "CRITICAL",
                f"Secondary event {event_id} between {home} and {away} has no imported primary listing.", evidence,
            ))
            continue
        if item.status != "COMPLETED" or item.home_score is None or item.away_score is None:
            continue
        for game in listings:
            if not (game.completed and game.verified):
                continue
            primary_scores = {game.home_team_id: game.home_score, game.away_team_id: game.away_score}
            if primary_scores != {home: item.home_score, away: item.away_score} or game.forfeit != item.forfeit:
                issues.append(ValidationIssue(
                    "PRIMARY_SECONDARY_SCORE_DISAGREEMENT", "WARNING",
                    f"Imported final {game.game_id} disagrees with secondary event {event_id}; primary result retained.",
                    {**evidence, "primary_game_id": game.game_id, "primary_scores": primary_scores},
                ))
    return issues


def main(argv: list[str] | None = None) -> int:
    """Write a statewide coverage report to an isolated output directory."""
    import argparse
    import csv
    import json
    from pathlib import Path
    from datetime import timezone

    from .config import Settings
    from .game_status import counts_toward_record, expected_by_cutoff
    from .models import MaxPrepsRanking
    from .providers import MHSAAClassificationProvider, MHSAAOfficialScoreProvider, MaxPrepsRankingProvider, MaxPrepsScoreProvider
    from .reconcile import reconcile_games, reconcile_maxpreps, supplement_games_with_maxpreps
    from .validation import quarantine_games

    parser = argparse.ArgumentParser(description="Audit all active MHSAA teams against complete secondary schedules; never publish rankings.")
    parser.add_argument("--snapshot", type=Path, default=Path("data/current"))
    parser.add_argument("--cache-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fetch", action="store_true", help="Refresh public sources into the isolated audit cache.")
    args = parser.parse_args(argv)
    payload = json.loads((args.snapshot / "overall.json").read_text())
    cutoff = datetime.fromisoformat(payload["metadata"]["cutoff_at"])
    start = date.fromisoformat(Settings(season=payload["metadata"]["season"]).season_start)
    root = args.cache_root
    official = MHSAAClassificationProvider().fetch(root / "official.json", refresh=args.fetch)
    if args.fetch:
        ranking_fetch = MaxPrepsRankingProvider().fetch(root / "rankings.json")
        rows = ranking_fetch.rankings
    else:
        rows = [MaxPrepsRanking(**r) for r in json.loads((root / "rankings.json").read_text())["rankings"]]
    signals, media_issues = reconcile_maxpreps(official, rows)
    failed: set[str] = set()
    cached: set[str] = set()
    if args.fetch:
        score_fetch = MHSAAOfficialScoreProvider().fetch_range(start, cutoff.date(), root / "official-scores", refresh_recent_days=9999)
        raw = score_fetch.games
        secondary = MaxPrepsScoreProvider().fetch(signals, root / "schedules")
        observations = secondary.games
        failed, cached = set(secondary.failed_team_ids), set(secondary.cached_team_ids)
    else:
        raw = []
        for file in sorted((root / "official-scores").glob("*.json")):
            source = json.loads(file.read_text())
            if start <= date.fromisoformat(source["date"]) <= cutoff.date():
                raw.extend(MHSAAOfficialScoreProvider.parse_nodes(source["nodes"], datetime.fromisoformat(source["retrieved_at"])))
        observations = []
        for team_id in signals:
            file = root / "schedules" / f"{team_id}.json"
            if file.exists():
                parsed, _ = MaxPrepsScoreProvider._read_cache(file)
                observations.extend(parsed)
                if not parsed:
                    failed.add(team_id)
            else:
                failed.add(team_id)
    raw = list({g.game_id: g for g in raw}.values())
    teams, games, identity_issues = reconcile_games(official, raw)
    games, fallback_issues = supplement_games_with_maxpreps(teams, games, observations, cutoff)
    games, quarantine_issues = quarantine_games(games, cutoff)
    findings = audit_schedule_coverage(teams, games, observations, signals, cutoff, start, set(signals) - failed - cached)
    args.output.mkdir(parents=True, exist_ok=True)
    snapshot_rows = {r["team_id"]: r for r in payload["rankings"]}
    media_rows = {(r.team_name, r.team_url): r for r in rows}
    team_rows = []
    for team in sorted((t for t in teams if t.ranked), key=lambda t: t.team_id):
        listed = [g for g in games if team.team_id in {g.home_team_id, g.away_team_id} and expected_by_cutoff(g, cutoff)]
        finals = [g for g in listed if counts_toward_record(g, cutoff)]
        wins = losses = ties = 0
        for game in finals:
            scored, conceded = ((game.home_score, game.away_score) if game.home_team_id == team.team_id else (game.away_score, game.home_score))
            wins += scored > conceded
            losses += scored < conceded
            ties += scored == conceded
        signal = signals.get(team.team_id)
        media = media_rows.get((signal.source_name, signal.source_url)) if signal else None
        team_rows.append({
            "team_id": team.team_id, "team": team.display_name, "classification": team.classification,
            "region": team.region, "source_team_id": team.source_team_id or "", "source_city": team.city,
            "snapshot_record": snapshot_rows.get(team.team_id, {}).get("record", "MISSING"),
            "replayed_record": f"{wins}-{losses}" + (f"-{ties}" if ties else ""),
            "media_record": media.record if media else "UNMATCHED",
            "expected_listings": len(listed), "verified_results": len(finals), "unresolved_listings": len(listed) - len(finals),
            "secondary_schedule_readable": team.team_id not in failed,
            "secondary_profile": signal.source_url if signal else "",
        })
    with (args.output / "team-coverage.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(team_rows[0]))
        writer.writeheader()
        writer.writerows(team_rows)
    unresolved = [{"game_id": g.game_id, "date": calendar_date(g.date).isoformat(),
                   "home": g.home_team_id, "away": g.away_team_id, "status": g.status}
                  for g in games if expected_by_cutoff(g, cutoff) and not counts_toward_record(g, cutoff)]
    summary = {
        "audited_at": datetime.now(timezone.utc).isoformat(), "cutoff": cutoff.isoformat(),
        "snapshot_run_id": payload["metadata"]["run_id"],
        "official_listed_teams": len(official), "active_teams": len(team_rows),
        "missing_ranked_team_ids": sorted({r["team_id"] for r in team_rows} - snapshot_rows.keys()),
        "unexpected_ranked_team_ids": sorted(snapshot_rows.keys() - {r["team_id"] for r in team_rows}),
        "teams_without_results_after_fix": [r["team_id"] for r in team_rows if not r["verified_results"]],
        "unresolved_primary_games": unresolved,
        "record_disagreements_after_fix": [r for r in team_rows if r["replayed_record"] != r["media_record"]],
        "unreadable_schedule_team_ids": sorted(failed), "cached_schedule_team_ids": sorted(cached),
        "findings": [i.to_dict() for i in findings],
        "reconciliation_issues": [i.to_dict() for i in media_issues + identity_issues + fallback_issues + quarantine_issues],
        "scope": "Freshly retrieved sources compared at the saved cutoff; media inputs are not a historical reconstruction. No rankings published.",
    }
    (args.output / "coverage.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({k: summary[k] for k in ("active_teams", "missing_ranked_team_ids", "teams_without_results_after_fix", "unreadable_schedule_team_ids")}, indent=2))
    print(f"Unresolved primary games: {len(unresolved)}; schedule findings: {len(findings)}; record discrepancies: {len(summary['record_disagreements_after_fix'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
