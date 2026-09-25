from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

from .config import CENTRAL, FORMULA_VERSION, Settings, ranking_week
from .byes import confirmed_byes
from .engine import calculate_rankings
from .fixtures import demo_dataset
from .models import ValidationIssue
from .providers import (
    MAXPREPS_RANKINGS_URL,
    MHSAAClassificationProvider,
    MHSAAOfficialScoreProvider,
    MaxPrepsRankingProvider,
    MaxPrepsScoreProvider,
)
from .reconcile import reconcile_external_maxpreps_ratings, reconcile_games, reconcile_maxpreps, supplement_games_with_maxpreps
from .audit import HARD_AUDIT_CODES, audit_snapshot, latest_revision
from .snapshots import (
    game_ledger,
    load_previous,
    preview_payload,
    publish_snapshot,
    write_demo_preview,
    write_draft_report,
    write_provisional_snapshot,
)
from .validation import can_show_provisional, quarantine_games, validate_inputs


def _parse_cutoff(value: str | None, settings: Settings) -> datetime:
    if not value:
        return settings.default_cutoff()
    parsed = datetime.fromisoformat(value)
    return parsed.replace(tzinfo=CENTRAL) if parsed.tzinfo is None else parsed.astimezone(CENTRAL)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Calculate auditable Mississippi Football Power Index rankings.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--live", action="store_true", help="Fetch official MHSAA teams, schedules, and scores.")
    mode.add_argument("--demo", action="store_true", help="Run the deterministic bundled demonstration dataset.")
    parser.add_argument("--week", type=int, help="Ranking week; defaults from the Tuesday 11 a.m. America/Chicago cutoff.")
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--cutoff", help="ISO timestamp; naive values are interpreted in America/Chicago.")
    parser.add_argument("--data-root", type=Path, default=Path("data"))
    parser.add_argument("--refresh-teams", action="store_true")
    parser.add_argument("--corrected", action="store_true", help="Publish an audited correction without overwriting history.")
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Exit successfully when this week's immutable snapshot is already published.",
    )
    parser.add_argument("--no-publish", action="store_true", help="Calculate and validate without updating current rankings.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.skip_existing and (args.corrected or args.no_publish):
        parser.error("--skip-existing cannot be combined with --corrected or --no-publish")

    generated_at = datetime.now(timezone.utc)
    week = args.week or ranking_week(generated_at, args.season)
    existing_archive = args.data_root / str(args.season) / f"week-{week:02d}"
    if args.skip_existing and existing_archive.exists():
        print(
            json.dumps(
                {
                    "formula_version": FORMULA_VERSION,
                    "season": args.season,
                    "week": week,
                    "status": "ALREADY_PUBLISHED",
                    "archive": str(existing_archive),
                },
                indent=2,
            )
        )
        return 0

    settings = replace(Settings(), season=args.season, week=week)
    cutoff = _parse_cutoff(args.cutoff, settings)
    source_meta: list[dict] = []
    prior_issues: list[ValidationIssue] = []
    maxpreps_signals = {}
    bye_team_ids: set[str] = set()

    if args.demo:
        teams, games = demo_dataset()
        source_meta = [
            {"name": "demo_fixture", "retrieved_at": generated_at.isoformat()},
        ]
    else:
        team_provider = MHSAAClassificationProvider()
        official = team_provider.fetch(
            args.data_root / "cache" / "mhsaa_teams_2025_27.json",
            args.refresh_teams,
            fallback_path=(
                Path(__file__).resolve().parent.parent / "data" / "reference" / "mhsaa_teams_2025_27.json"
                if args.season in {2025, 2026} else None
            ),
        )
        maxpreps_fetch = MaxPrepsRankingProvider().fetch(args.data_root / "cache" / "maxpreps" / "latest.json")
        maxpreps_signals, maxpreps_issues = reconcile_maxpreps(official, maxpreps_fetch.rankings)
        prior_issues.extend(maxpreps_issues)
        if maxpreps_fetch.used_cache:
            cache_age = generated_at - maxpreps_fetch.retrieved_at
            prior_issues.append(
                ValidationIssue(
                    "MAXPREPS_CACHE_FALLBACK",
                    "CRITICAL" if cache_age > timedelta(days=8) else "WARNING",
                    f"Used cached media rankings retrieved {maxpreps_fetch.retrieved_at.isoformat()} after the live pull failed.",
                    {"cache_age_hours": round(cache_age.total_seconds() / 3600, 1)},
                )
            )
        scores = MHSAAOfficialScoreProvider().fetch_range(
            datetime.fromisoformat(settings.season_start).date(),
            cutoff.date(),
            args.data_root / "cache" / "mhsaa_scores",
        )
        teams, games, game_issues = reconcile_games(official, scores.games)
        prior_issues.extend(game_issues)
        # Read every Mississippi team's MaxPreps schedule so completed games
        # against out-of-state opponents can inherit a published rating too.
        maxpreps_score_targets = dict(maxpreps_signals)

        maxpreps_score_fetch = MaxPrepsScoreProvider().fetch(
            maxpreps_score_targets,
            args.data_root / "cache" / "maxpreps_scores",
        )
        games, maxpreps_score_issues = supplement_games_with_maxpreps(
            teams,
            games,
            maxpreps_score_fetch.games,
            cutoff,
        )
        prior_issues.extend(maxpreps_score_issues)
        bye_team_ids = confirmed_byes(
            games, maxpreps_score_fetch.games, cutoff,
            set(maxpreps_score_targets) - set(maxpreps_score_fetch.cached_team_ids)
            - set(maxpreps_score_fetch.failed_team_ids),
        )
        external_states = {}
        for observation in maxpreps_score_fetch.games:
            for team_url in (observation.home_url, observation.away_url):
                parts = [part for part in urlparse(team_url).path.split("/") if part]
                if parts and parts[0] != "ms" and len(parts[0]) == 2:
                    external_states.setdefault(parts[0], None)
        rankings_by_state = {
            state: MaxPrepsRankingProvider().fetch_state(
                state, args.data_root / "cache" / "maxpreps" / f"{state}.json"
            )
            for state in external_states
        }
        external_ratings = reconcile_external_maxpreps_ratings(teams, maxpreps_score_fetch.games, rankings_by_state)
        secondary_results_used = sum(
            len(issue.context.get("games", []))
            for issue in maxpreps_score_issues
            if issue.code == "MAXPREPS_SECONDARY_RESULTS_USED"
        )
        secondary_statuses_used = sum(
            len(issue.context.get("games", []))
            for issue in maxpreps_score_issues
            if issue.code == "MAXPREPS_SECONDARY_STATUS_USED"
        )
        if maxpreps_score_fetch.cached_team_ids:
            prior_issues.append(
                ValidationIssue(
                    "MAXPREPS_SCORE_CACHE_FALLBACK",
                    "WARNING",
                    "Used cached secondary team schedules after one or more live score requests failed.",
                    {"team_ids": list(maxpreps_score_fetch.cached_team_ids)},
                )
            )
        if maxpreps_score_fetch.failed_team_ids:
            prior_issues.append(
                ValidationIssue(
                    "MAXPREPS_SCORE_SOURCE_UNAVAILABLE",
                    "WARNING",
                    "Some unresolved MHSAA games could not be checked against the secondary score source and remain unverified.",
                    {"team_ids": list(maxpreps_score_fetch.failed_team_ids)},
                )
            )
        source_meta = [
            {
                "name": "MHSAA official score center",
                "url": "https://scores.misshsaa.com/",
                "retrieved_at": scores.retrieved_at.isoformat(),
            },
            {
                "name": "MHSAA 2025-27 football classifications",
                "url": "https://www.misshsaa.com/2024/11/19/2025-27-football-regions/",
            },
            {
                "name": "Media Rank and Strength of Schedule",
                "url": MAXPREPS_RANKINGS_URL.format(page=1),
                "retrieved_at": maxpreps_fetch.retrieved_at.isoformat(),
                "source_updated_at": maxpreps_fetch.source_updated_at,
                "cached_fallback": maxpreps_fetch.used_cache,
            },
            {
                "name": "Secondary score verification",
                "url": "https://www.maxpreps.com/ms/football/scores/",
                "retrieved_at": maxpreps_score_fetch.retrieved_at.isoformat(),
                "team_schedule_pages_checked": len(maxpreps_score_targets),
                "secondary_results_used": secondary_results_used,
                "secondary_statuses_used": secondary_statuses_used,
                "cached_team_ids": list(maxpreps_score_fetch.cached_team_ids),
                "failed_team_ids": list(maxpreps_score_fetch.failed_team_ids),
            },
        ]

    previous = load_previous(args.data_root, args.season, week)
    games, quarantine_issues = quarantine_games(games, cutoff)
    prior_issues.extend(quarantine_issues)
    report = validate_inputs(teams, games, cutoff, settings, prior_issues)
    result = calculate_rankings(
        teams, games, cutoff, settings, previous, maxpreps_signals,
        external_ratings if not args.demo else None, confirmed_bye_team_ids=bye_team_ids,
    )
    if not result.converged:
        report.issues.append(
            ValidationIssue(
                "SRS_DID_NOT_CONVERGE",
                "CRITICAL",
                f"SRS failed to converge below {settings.convergence_tolerance} in {result.iterations} iterations.",
            )
        )

    audit_summary = None
    if not args.demo:
        # Audit the exact payload readers would see before it can replace the
        # live snapshot. A blocking finding keeps the last valid publication.
        previous_dir = args.data_root / str(args.season) / f"week-{week - 1:02d}"
        previous_payload = (
            json.loads((latest_revision(previous_dir) / "overall.json").read_text(encoding="utf-8"))
            if week > 1 and (previous_dir / "overall.json").exists() else None
        )
        audit = audit_snapshot(
            preview_payload(
                season=args.season, week=week, cutoff=cutoff, generated_at=generated_at,
                status="CORRECTED" if args.corrected else "PUBLISHED",
                teams=teams, games=games, rankings=result.rankings, report=report,
            ),
            snapshot_label="pre-publication",
            reference={"teams": [team.to_dict() for team in teams if team.ranked]},
            previous=previous_payload,
            ledger=game_ledger(teams, games, result.rankings, cutoff),
            external_verification="PIPELINE_SOURCES_ONLY",
        )
        audit_summary = audit.to_dict()
        hard = [issue for issue in audit.blocking if issue.code in HARD_AUDIT_CODES]
        if hard:
            report.issues.append(ValidationIssue(
                "PUBLICATION_AUDIT_BLOCKED", "CRITICAL",
                f"The publication audit found {len(hard)} issue(s) that make the rankings unsound; the previous snapshot stays live.",
                {"codes": sorted({issue.code for issue in hard})},
            ))
        elif audit.blocking:
            report.issues.append(ValidationIssue(
                "PUBLICATION_AUDIT_FINDINGS", "CRITICAL",
                f"The publication audit found {len(audit.blocking)} data issue(s); the week is published as provisional.",
                {"codes": sorted({issue.code for issue in audit.blocking})},
            ))
        elif audit.outcome != "PASS":
            report.issues.append(ValidationIssue(
                "PUBLICATION_AUDIT_WARNINGS", "WARNING",
                "The publication audit passed with warnings; see audit.json.",
                {"counts": audit.summary()["issue_counts"]},
            ))

    run_id = f"{args.season}-week-{week:02d}-{generated_at.strftime('%Y%m%dT%H%M%S%fZ')}"
    summary = {
        "run_id": run_id,
        "formula_version": FORMULA_VERSION,
        "valid": report.valid,
        "coverage": report.coverage,
        "ranked_teams": len(result.rankings),
        "games": len([game for game in games if game.completed and game.date <= cutoff]),
        "srs_iterations": result.iterations,
        "srs_converged": result.converged,
        "bye_adjusted_teams": [
            {"team": row.team.display_name, "mfpi": round(row.mfpi, 1), "rank": row.state_rank}
            for row in result.rankings if row.bye_adjustment
        ],
        "top_five": [
            {"rank": row.state_rank, "team": row.team.display_name, "mfpi": round(row.mfpi, 1)}
            for row in result.rankings[:5]
        ],
    }

    if args.demo:
        if report.valid and not args.no_publish:
            preview = write_demo_preview(
                args.data_root,
                season=args.season,
                week=week,
                cutoff=cutoff,
                generated_at=generated_at,
                rankings=result.rankings,
                report=report,
                sources=source_meta,
            )
            summary["status"] = "DEMO"
            summary["preview"] = str(preview)
        else:
            summary["status"] = "DEMO_VALIDATED" if report.valid else "DEMO_INVALID"
    elif report.valid and not args.no_publish:
        archive = publish_snapshot(
            args.data_root,
            season=args.season,
            week=week,
            cutoff=cutoff,
            generated_at=generated_at,
            teams=teams,
            games=games,
            rankings=result.rankings,
            report=report,
            sources=source_meta,
            corrected=args.corrected,
            audit=audit_summary,
        )
        summary["status"] = "CORRECTED" if args.corrected else "PUBLISHED"
        summary["archive"] = str(archive)
    elif report.valid:
        summary["status"] = "VALIDATED"
    elif not args.no_publish and can_show_provisional(report):
        draft = write_provisional_snapshot(
            args.data_root,
            run_id=run_id,
            season=args.season,
            week=week,
            cutoff=cutoff,
            generated_at=generated_at,
            teams=teams,
            games=games,
            rankings=result.rankings,
            report=report,
            sources=source_meta,
            audit=audit_summary,
            corrected=args.corrected,
        )
        summary["status"] = "PROVISIONAL"
        summary["draft"] = str(draft)
    else:
        draft = write_draft_report(args.data_root, run_id, report)
        if audit_summary is not None:
            (draft / "audit.json").write_text(json.dumps(audit_summary, indent=2) + "\n", encoding="utf-8")
        summary["status"] = "DRAFT"
        summary["draft"] = str(draft)
    if audit_summary is not None:
        summary["audit"] = {key: audit_summary[key] for key in ("outcome", "blocking", "warnings", "info")}
    print(json.dumps(summary, indent=2))
    return 0 if report.valid or summary["status"] == "PROVISIONAL" else 2


if __name__ == "__main__":
    sys.exit(main())
