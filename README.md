# Mississippi Football Power Index

MFPI is a local-first weekly computer ranking for every active MHSAA Class 1A–7A football team. It pulls the official MHSAA team list and scoreboard data plus statewide Media Rank and Strength of Schedule inputs, validates every match, and writes reproducible JSON/CSV snapshots. The dashboard works locally at `http://localhost:4321` and can also be deployed from a Git repository to Cloudflare Workers.

## What is built

- Official 2025–27 MHSAA classification importer and canonical team/alias model
- Official MHSAA score-center adapter with date caches, finals, scores, home/away, overtime, forfeits, and contest status
- Conservative secondary-score fallback for unresolved MHSAA listings, including one-day reschedules, explicit forfeits, and cancellation/postponement labels
- Statewide Media Rank and Strength of Schedule importer with complete-team matching, cache fallback, and source timestamps
- Iterative SRS with a fading 7A-to-1A class prior, custom SOS, capped scoring, record, and recent form
- Explicit playing-up/down metrics: average class differential plus up/same/down game counts
- Validation that labels incomplete-score runs provisional and blocks corrupt inputs such as impossible scores, duplicates, future results, or SRS failure
- Immutable weekly snapshots, audited corrections, CSV/JSON outputs, SQLite calculation ledger, deterministic explanations
- Responsive local ranking viewer with class filters, sorting, movement, and expandable component math
- Deterministic fixture data and a comprehensive Python test suite

## Setup

Requirements: Python 3.12+, Node.js 22.13+, and npm.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
npm install
python -m pytest -q
npm run build
```

Start the local viewer:

```powershell
npm run dev
```

Generate safe sample rankings at any time:

```powershell
python calculate_rankings.py --demo --no-publish
```

## Official weekly run

At or after the weekly cutoff, run:

```powershell
.\scripts\run_weekly.ps1
```

The ranking week is selected automatically at the Wednesday 1:00 p.m. America/Chicago boundary, including daylight-saving-time changes. The scheduled repository workflow starts at 1:10 p.m. Central so the cutoff has passed before data collection begins. Each live run refreshes the statewide media ranking pages and all recent MHSAA score dates. For an MHSAA listing that should be final but has no score, MFPI checks a secondary public schedule source. It accepts only the exact team pair on the same date or a one-day reschedule; conflicting reports block the run, and a missing result is never guessed to be a cancellation. Use `--week 3` only for an intentional rerun. If verified coverage remains below 95%, the full statewide ranking is written to `data/current` as `PROVISIONAL` and its audit copy is stored under `data/drafts/<run-id>`. A fully validated run also writes the immutable `data/2026/week-01` publication. Missing media-ranking teams or other critical data-integrity failures do not replace the dashboard.

For an audited correction to an already-published week:

```powershell
python calculate_rankings.py --live --week 1 --corrected
```

This creates `data/2026/week-01/corrections/revision-01`; it never overwrites the original snapshot.

## Git and Cloudflare Workers

The repository is already configured as a vinext application that builds a Cloudflare Worker and its static assets. After creating the Git repository and connecting it in Cloudflare Workers Builds, use:

- Build command: `npm run build`
- Deploy command: `npx wrangler deploy --config dist/server/wrangler.json`
- Production branch: `main`

The Wednesday workflow in `.github/workflows/update-rankings.yml` tests the engine, pulls the live data after the cutoff, rebuilds the site, and commits changed ranking snapshots. A push to `main` then gives Cloudflare's Git integration a new revision to deploy. The workflow needs repository `contents: write` permission; a protected branch must also allow the workflow bot to push, or the commit step must be changed to open a pull request.

For a local Cloudflare-compatible preview or an authenticated manual deployment:

```powershell
npm run preview
npm run deploy
```

## Repository map

```text
app/                         local ranking dashboard
mfpi/                        providers, matching, validation, SRS, formula, storage
tests/                       unit, integration, and ranking-scenario tests
scripts/run_weekly.ps1       one-command local weekly workflow
data/current/                viewer's latest live or validated rankings
data/2026/week-XX/           immutable official snapshots
calculate_rankings.py        CLI entry point
METHODOLOGY.md               formula in plain language and exact weights
DATA_SOURCES.md              source contracts, permissions, and limitations
ADMIN_GUIDE.md               validation, corrections, and weekly operation
```

## Formula and auditability

Every component stores its raw value, normalized score, effective weight, and contribution. The unrounded contributions sum to MFPI; display values are rounded only at the edge. Formula version `MFPI-3.1` is stored in every snapshot and database run. Media Rank and Strength of Schedule contribute 10% each; MFPI's score-based model contributes the remaining 80%. Out-of-state opponents receive a published-rating SRS prior when available. See [METHODOLOGY.md](METHODOLOGY.md) for the full calculation.

## Tests

```powershell
python -m pytest -q
```

The suite covers margin diminishing returns, home field, SRS convergence, robust normalization, SOS, quality wins, weak schedules, close elite losses, recent form, dynamic/stale weights, aliases, ties, forfeits, zero-game teams, missing data, tie breakers, movement, class filtering, provider parsing, validation, and the 70-point-win scenario.

## Provisional rankings

The official MHSAA score center sometimes leaves completed-looking scheduled games without a verified final. MFPI checks a secondary public source only for those gaps, records every secondary result in the validation audit, and continues to prefer an official MHSAA final whenever one exists. MFPI still ranks every 1A–7A team from the verified results available and clearly marks the run provisional until at least 95% of expected games have verified scores. Impossible scores, conflicting secondary reports, ambiguous teams, duplicates, future results, and failed SRS convergence remain hard blockers.
