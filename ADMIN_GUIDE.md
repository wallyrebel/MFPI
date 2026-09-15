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
