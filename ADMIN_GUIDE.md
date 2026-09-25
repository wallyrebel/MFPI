# MFPI weekly operator guide

MFPI is intentionally local and file-based. The command line is the admin interface; it is smaller and easier to audit than a login-protected public admin site.

## Tuesday workflow

1. The repository workflow runs every Tuesday at 11:00 a.m. America/Chicago. For a local run at or after that cutoff, run `.\scripts\run_weekly.ps1`. It refreshes MHSAA scores and every paginated Media Rank and Strength of Schedule row automatically, then checks secondary team schedules only for unresolved MHSAA games.
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

## Publication audit

Every live run audits the exact payload it would publish (`mfpi/audit.py`) before anything replaces `data/current`:

- **BLOCKING** — a missing or extra team versus the MHSAA list, a team that disappeared since last week, a score that differs between the two teams' pages, a game missing from one side, a record or average that disagrees with its games, ranks out of order, component arithmetic that does not add up, non-finite numbers, a counted game after the cutoff, or a listing ledger that counts a non-final game. The run becomes `DRAFT`; the previous snapshot stays live; `data/drafts/<run-id>/audit.json` lists every finding.
- **WARNING** — publishable but needs a person: a team with no verified results, a possible identity split (an external opponent whose name is a shorter form of a ranked team), a team credited with two games on one date, a zero average on a team without games.
- **INFO** — investigate only: unusual scores (60+ margin or 110+ total), large rating/rank swings, schedule gaps, forfeits. Never "correct" a valid unusual result.

Run it any time: `python -m mfpi.audit --snapshot data/current --out reports/current`. It writes `data-quality.json`, `team-reconciliation.csv` and `game-ledger-check.csv`. The GitHub deploy refuses to deploy a snapshot with blocking findings.

## Team identity review

Names alone never merge schools. When a source lists an MHSAA program under a different name, add a `ReviewedIdentity` in `mfpi/matching.py` with the source, its stable team ID, the listed name and the listed city; it applies only when all four agree, and the run records `REVIEWED_IDENTITY_APPLIED`. Use `team_id=None` to record that a same-named source team is a different school (for example a Tennessee "Houston"), which keeps it external. The import reports `MULTIPLE_SOURCE_IDS_FOR_TEAM` when one MHSAA team matched several source IDs by name, and `TEAM_DOUBLE_BOOKED` when a team is credited with two games on one date — both are signs of a same-name mix-up. Resolve them with evidence (the opponent's schedule, the school's own schedule, or the MHSAA listing's city), not by deleting a game.

## Weekly Analysis workflow

1. After a week publishes: `python -m mfpi.editorial generate --week N --markdown-dir reports/editorial-drafts`. Drafts go to `content/analysis/*.json` with `status: "draft"`; they are never routed, listed, put in the sitemap or given ads in production.
2. Read the Markdown copy (or `npm run dev` and open `/analysis/preview/<slug>`). Check every number against the rankings, remove anything you would not stand behind, and edit the JSON text if needed. Add notes in `review_notes`.
3. Publish only after that review, in your own name: `python -m mfpi.editorial publish <slug> --reviewer "Full Name" --confirm-reviewed`. The tool stamps `reviewed_at`/`published_at` with the current Central time; it never backdates.
4. `python -m mfpi.editorial validate` (also run by the deploy workflow) rejects published articles without a named reviewer, published before review, dated in the future, or dated before the data they describe.
5. Commit and push; the deploy workflow publishes it. Regenerating never overwrites a published article.

Keep the section small: one weekly analysis, one risers-and-fallers piece, and a performance review once several weeks of pregame snapshots exist. Do not generate pages just to add page count.

## Advertising configuration

See [ADSENSE.md](ADSENSE.md). All values are GitHub Actions **variables** (not secrets; they are public in page source). With none set, the site builds with advertising off.

## Corrections and history

Published `data/<season>/week-XX` directories are immutable. A second ordinary publication raises an error. Ordinary GitHub Actions workflow runs pass `--skip-existing`, which reports `ALREADY_PUBLISHED` and exits successfully when the week's archive is already present; it does not fetch data or change the archive. After reviewing the reason for a historical correction, use `--corrected`; the program writes a numbered revision, marks it `CORRECTED`, links it to the original run in SQLite, and updates `data/current`.

Never delete or edit an original weekly directory to conceal a correction. Formula changes require a new `FORMULA_VERSION`; do not recalculate old published weeks in place.

## Local scheduling

The weekly script is noninteractive and suitable for Windows Task Scheduler. Schedule PowerShell to run:

```text
-NoProfile -ExecutionPolicy Bypass -File "C:\Users\myers\OneDrive\Desktop\MFPI\scripts\run_weekly.ps1"
```

Use Tuesday 11:00 a.m. America/Chicago and set the task's start-in directory to the repository. Pass `-Corrected` only for an audited rerun of a week that already has an immutable publication.

## Repository scheduling and Cloudflare

`.github/workflows/update-rankings.yml` runs each Tuesday at 11:00 a.m. America/Chicago, supports a manual run, validates and rebuilds the project, commits changed ranking data, and deploys the resulting site directly to Cloudflare Workers. GitHub can start scheduled jobs later than the configured time.

`.github/workflows/deploy.yml` deploys code changes pushed to `main` and supports manual deployment. Both workflows share a production queue so they cannot deploy over each other. The weekly workflow deploys even when the week is already published, allowing a retry to recover a failed deployment without recalculating or overwriting that week.

### Deployment credentials

Both workflows read these **repository Actions secrets** from [MFPI Settings > Secrets and variables > Actions](https://github.com/wallyrebel/MFPI/settings/secrets/actions):

- `CLOUDFLARE_API_TOKEN`: a dedicated Cloudflare API token with **Account > Workers Scripts > Edit**, restricted to the account hosting `mississippi-football-power-index`.
- `CLOUDFLARE_ACCOUNT_ID`: that Cloudflare account's ID, available in the dashboard or from `npx wrangler whoami` after signing in locally.

To replace credentials, create a custom token at [Cloudflare API Tokens](https://dash.cloudflare.com/profile/api-tokens), select the permission and account above, and save the token directly into GitHub's `CLOUDFLARE_API_TOKEN` secret. Store the account ID in the other secret. Never commit token values. A local `wrangler login` only signs in this computer; it does not authenticate GitHub Actions. See [Cloudflare's GitHub Actions guide](https://developers.cloudflare.com/workers/ci-cd/external-cicd/github-actions/).

After saving or replacing the secrets, run **Deploy site** from the repository's Actions tab and verify that **Deploy to Cloudflare Workers** succeeds. Run **Update MFPI rankings** to verify the weekly path; leave the correction option off unless intentionally publishing an audited correction. Missing credentials now fail the workflow explicitly before work begins.
