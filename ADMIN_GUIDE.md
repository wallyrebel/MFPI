# MFPI weekly operator guide

MFPI is intentionally local and file-based. The command line is the admin interface; it is smaller and easier to audit than a login-protected public admin site.

## Wednesday workflow

1. At or after 1:00 p.m. America/Chicago, run `.\scripts\run_weekly.ps1`. It refreshes MHSAA scores and every paginated Media Rank and Strength of Schedule row automatically, then checks secondary team schedules only for unresolved MHSAA games.
2. Read the printed report. `PUBLISHED` means the immutable week and `data/current` were written. `PROVISIONAL` means all teams were ranked but verified score coverage is still below 95%. `DRAFT` means a data-integrity problem blocked the dashboard update.
3. For a provisional or blocked run, open the reported `data/drafts/<run-id>/validation.json`. A low-coverage issue lists every missing source game ID. Accepted secondary fallbacks and any conflicting reports are listed separately with event URLs.
4. Correct the upstream data or add a reviewed alias in `mfpi/matching.py`; rerun tests and then rerun the week. Never label a scoreless listing cancelled unless a source explicitly does so.
5. Refresh the local browser. The dashboard reads `data/current/overall.json` at build/dev time.

Run calculation without publishing:

```powershell
python calculate_rankings.py --live --no-publish
```

Force an explicit cutoff for an audit:

```powershell
python calculate_rankings.py --live --week 1 --cutoff "2026-09-02T13:00:00-05:00" --no-publish
```

## Validation rules

Low verified-game coverage by itself produces a complete, visibly labeled provisional dashboard. Missing or duplicate media-ranking team matches, a media-ranking cache older than eight days, conflicting secondary score reports, duplicate game IDs or matchups, same-team games, impossible or future scores, duplicate aliases, ambiguous source matches, and SRS non-convergence remain hard blockers and cannot replace `data/current`. A recent media cache may be used during a short source outage and is recorded as a warning.

## Corrections and history

Published `data/<season>/week-XX` directories are immutable. A second ordinary publication raises an error. Ordinary GitHub Actions workflow runs pass `--skip-existing`, which reports `ALREADY_PUBLISHED` and exits successfully when the week's archive is already present; it does not fetch data or change the archive. After reviewing the reason for a historical correction, use `--corrected`; the program writes a numbered revision, marks it `CORRECTED`, links it to the original run in SQLite, and updates `data/current`.

Never delete or edit an original weekly directory to conceal a correction. Formula changes require a new `FORMULA_VERSION`; do not recalculate old published weeks in place.

## Local scheduling

The weekly script is noninteractive and suitable for Windows Task Scheduler. Schedule PowerShell to run:

```text
-NoProfile -ExecutionPolicy Bypass -File "C:\Users\myers\OneDrive\Desktop\MFPI\scripts\run_weekly.ps1"
```

Use Wednesday 1:10 p.m. America/Chicago and set the task's start-in directory to the repository. Pass `-Corrected` only for an audited rerun of a week that already has an immutable publication.

## Repository scheduling and Cloudflare

`.github/workflows/update-rankings.yml` is the preferred hosted schedule. It runs at 1:10 p.m. America/Chicago each Wednesday, supports a manual run, validates and rebuilds the project, and commits only changed ranking data. Connect the repository's `main` branch to a Cloudflare Workers Builds project so that commit becomes the deployment trigger. MFPI is a Workers/vinext build, not a static Cloudflare Pages export.
