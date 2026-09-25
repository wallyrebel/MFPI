# MFPI improvement handoff — 2026-09-25

Branch `claude/gracious-wright-7kgs3u`, based on `main` at `971bd3c` ("Update MFPI weekly rankings").
**Nothing is deployed.** The branch is pushed; production changes only when it is merged to `main`
(see §8). No AdSense account action and no review submission were taken.

## 0. Baseline and access

| Item | Value |
|---|---|
| Stack | vinext (Vite + Next App Router API) on Cloudflare Workers; Python 3.12 ranking engine; GitHub Actions for weekly runs and deploys |
| Published data | `data/2026/week-01…04` (+ audited revisions for weeks 1 and 2), `data/current` = Week 4, run `2026-week-04-20260922T161926783618Z`, formula `MFPI-3.2`, 225 teams, 458/465 games verified (98.5%) |
| Tests at baseline | 61 Python tests passing; lint clean; build OK. `tsc` reports a pre-existing error in `vite.config.ts` (not used by the build) |
| Season / clock | 2026 season; Tuesday 11:00 a.m. America/Chicago cutoff (DST-aware in `mfpi/config.py`; nothing new hard-codes today's date) |
| **Network** | The environment's egress policy blocked the live site, misshsaa.com, scores.misshsaa.com (Scorebook Live), maxpreps.com, ahsfhs.org and support.google.com. Google documentation was rechecked through search results. **No external re-verification of teams or scores was possible**; every "verified" in this handoff means "verified by the site's own pipeline at publication", and reports say `external_verification: NOT_PERFORMED`. |
| Data backup | Published snapshots are immutable and in git; this work modified none of them (`git diff main -- data` is empty). |

## 1. What changed and why

**Accuracy fixes (all teams, shared rendering)**
- *Friday games shown as Saturday.* Pages formatted Central timestamps with `new Date()` on a UTC server, and the score center's 23:59-Pacific "time not published" marker was stored as 01:59 Central the next day. Dates now come from `calendarDate()` (`app/lib/format.ts`) / `mfpi/dates.py`; new snapshots also publish `calendar_date`. Falkner's Aug 28 game (was "Aug 29") and every 7 p.m. Friday game now show the right day.
- *Cleveland Central 0–0 / 0.0.* Pages now say **"Season data incomplete / results unavailable"**, show "—" for record and averages, label the rating **Provisional**, and never claim "no ranked wins". Same for Northside. New snapshots publish `pf_per_game: null` instead of 0.0 and a `data_status` of `complete | partial | unavailable | preseason`.
- *Root cause for Cleveland Central.* The official score feed lists a team named "Cleveland" (source ID 241722) that played Clarksdale, Greenwood, Amanda Elzy and Grenada; MFPI treated it as an external opponent. A reviewed identity mapping (`mfpi/matching.py`) now links it **only when source, source ID, name and city ("Cleveland") all agree**; otherwise it stays external with a warning. It takes effect at the next weekly run. **Owner please confirm** (§3).
- *Tupelo "unchanged" beside +3.0.* Rank movement and rating change are now computed and worded separately everywhere ("State ranking: unchanged at No. 1." / "MFPI rating: increased 3.1 points to 96.2."). Rating change is displayed-rating minus displayed-previous-rating, so 93.1 → 96.2 reads +3.1 (the old table showed +3.0 from unrounded values). No "−0.0".
- *Wrong cutoff label.* The home page said "Wed · 1:00 PM CT"; it now shows the snapshot's real cutoff (Tue 11:00 AM CDT) and coverage.
- *Scoring averages.* Public PF/G and PA/G exclude forfeits and match the CSV export exactly (Python-style rounding; a test checks all 225 teams).
- *Houston double-booking.* Houston is credited with two 7 p.m. games on Sept. 11 (vs Corinth 21–24, vs Tupelo 13–42). One is probably a same-named school (e.g., Houston High School, Germantown TN). Houston's, Tupelo's and Corinth's pages now flag it **"Under review"**. No data was changed. **Owner please confirm** (§3).
- *D'Iberville.* Shown as "D'Iberville High School" instead of the source abbreviation "Diberville Senior High Sch" (display only).
- *Eligibility.* Completed jamborees/scrimmages can no longer count (none exist in current data).

**Validation and safe publishing (`mfpi/audit.py`, `mfpi/game_status.py`, `mfpi/snapshots.py`, `mfpi/cli.py`)**
- A publication audit runs on the exact payload before it can replace `data/current`: team universe vs the MHSAA list, disappeared teams, both-sides game agreement, duplicates, same-day double bookings, records/averages vs games, NaN/∞, rank order, class ranks, component sums (with bye adjustments), display rounding, movement baselines, and the listing ledger. BLOCKING → DRAFT and the last valid snapshot stays; WARNING/INFO are recorded (`audit.json`). Severity rules are in `ADMIN_GUIDE.md`.
- One status vocabulary for listings (final, forfeit, scheduled, in progress, postponed, canceled, suspended, no contest, exhibition, unresolved). Each new snapshot writes `games.json` with every listing, its category, `counts_toward_record`, `counts_toward_scoring`, source and timestamp; team pages then show pending/postponed listings instead of hiding them.
- `data/current` is now written in a staging directory and swapped in, so a crash cannot leave a half-updated snapshot.
- Import-time detection: `MULTIPLE_SOURCE_IDS_FOR_TEAM`, `TEAM_DOUBLE_BOOKED`, reviewed identities (link or keep external).
- CI: the deploy workflow now runs site tests, the audit (blocking findings stop the deploy) and editorial validation.

**Content and transparency**
- Team pages: a "Why … is ranked here" section built only from verified data — strongest win (defined: the defeated MHSAA opponent with the best *current* rank), last three results, schedule strength and class path, what changed (largest component changes vs last week, bye adjustment), limitations.
- New **Weekly Analysis** (`/analysis`) with draft → review → publish; **archive** of every published week (`/archive`, `/archive/2026/week-04`), preserving originals and noting corrections; **Corrections and editorial standards** (`/corrections`) with the correction log and current known data issues; proper 404 page.
- About, Contact, Methodology, Privacy and Advertise rewritten to state who runs the site (operator name left for the owner), what MFPI calculates, the named sources (MHSAA, MHSAA score center, MaxPreps), no endorsement, update cadence, provisional meaning, and human vs automated steps. Privacy now matches what actually loads.
- Mobile: the site navigation was hidden under 600px; it is now a scrollable row. Tables are keyboard-focusable regions; class tabs expose `aria-pressed`.

**Advertising** — see `ADSENSE.md`. Integration is complete but **off** (no publisher ID exists in the repo). Ads.txt now returns plain text.

**Unchanged by design:** formula, weights, class prior, bye rule, tie-breaks, URLs (`/`, `/teams`, `/team/<slug>`, policy pages), the Casey Lott sponsor placement, the "Advertise Here" banner, GA4, exports, the weekly schedule.

**Proof that ratings did not change:** `scripts/engine_regression.py` ran the original (`971bd3c`) and new engines on identical inputs rebuilt from Week 4 plus the demo fixture — all 225 ranks, ratings (10 decimals) and records identical. Intentional output differences are limited to: explanation wording, new snapshot fields (`data_status`, `pending_games`, `calendar_date`, `game_id`, `source`, `games.json`, `audit.json`), `pf/pa_per_game: null` for teams without games, the display-consistent `mfpi_change`, and — from the next run — Cleveland Central's linked games (an input correction, which will legitimately move it and its opponents).

## 2. Team and record reconciliation

- `reports/2026-week-04/team-reconciliation.csv` (225 rows): team ID, name, class/region vs the MHSAA reference, prior record, record at cutoff, games counted, cutoff, ledger status, internal consistency, external verification, source links, correction made, unresolved issue. Same report for every published week and revision under `reports/`.
- Universe: 226 schools in the 2025–27 MHSAA list, 225 active programs ranked (Thrasher inactive by existing rule), 0 missing, 0 duplicates, 0 class/region mismatches, 0 unexpected teams, no team lost between weeks.
- Games (Week 4): 458 counted games; 406 between two ranked teams all agree from both sides; 52 against non-MHSAA/out-of-state opponents (42 named). 7 listings due by the cutoff still lack verified scores (IDs 7731608, 7808266, 7212436, 7587001, 7614774, 7614790, 7731841); they count as unavailable, never as results.
- **Not done:** comparison with current MaxPreps records and AHSFHS, and a fresh MHSAA pull — sources unreachable. Nothing is marked externally verified.

## 3. Data-quality findings (Week 4, audited 2026-09-25 14:52 UTC)

Outcome PASS_WITH_WARNINGS — 0 blocking, 10 warnings, 22 info (`reports/2026-week-04/data-quality.json`).

| Finding | Teams | Status / needed |
|---|---|---|
| No verified results through Week 4 | Cleveland Central, Northside | Cleveland Central: likely feed name "Cleveland" (ID 241722); mapping ready, **confirm**. Northside: cause unknown; confirm whether the program is playing and how the feed names it. |
| Two games on Sept. 11 | Houston (+ Tupelo, Corinth) | **Confirm** which opponent Houston (MS) played; if the Tupelo game was a Tennessee "Houston", add a `ReviewedIdentity(..., team_id=None, ...)` for that source ID and publish a correction. |
| Legacy 0.0 averages | Cleveland Central, Northside | Fixed on the site; new snapshots publish null. |
| Unusual scores (flag only) | 10 games, e.g. 60–58 Kosciusko/Hernando | Check against a second source if convenient; do not alter. |
| Forfeit | 1 | Confirm the official ruling. |
| Large moves | 9 rank moves ≥ 40, 1 rating move ≥ 15 (Simmons +25.6) | Informational. |

Weeks 1–2 originals predate per-game rows (record/two-sided checks skipped, noted in reports). Week 2 revision: 33 game rows against external opponents had no opponent display name at the time (fixed later by the existing pipeline).

## 4. Files, migrations, configuration

New: `mfpi/audit.py`, `mfpi/dates.py`, `mfpi/game_status.py`, `mfpi/explain.py`, `mfpi/editorial.py`; `app/lib/{format,ads,articles}.ts`, `app/ads/*`, `app/ads.txt/route.ts`, `app/archive-data.ts`, `app/analysis/**`, `app/archive/**`, `app/corrections/page.tsx`, `app/not-found.tsx`; `content/analysis/*.json` (3 drafts); `tests/test_{audit,editorial,pipeline_safety,methodology_sync}.py`; `tests-js/*`; `tests-e2e/site.e2e.mjs`; `scripts/engine_regression.py`; `reports/**`; `ADSENSE.md`, `HANDOFF.md`.
Changed: `mfpi/{byes,cli,engine,matching,models,reconcile,snapshots,validation}.py`; team, home, dashboard, about, contact, privacy, methodology, advertise, teams, sitemap, layout, nav, analytics, site config, CSS; both workflows; `package.json` scripts; README, ADMIN_GUIDE, DATA_SOURCES, METHODOLOGY.
Migrations: none. Snapshot JSON gains optional fields; older snapshots still render (tested on all six).
Configuration (GitHub Actions **variables**, all optional, all public): `NEXT_PUBLIC_ADSENSE_CLIENT`, `NEXT_PUBLIC_ADS_ENABLED`, `NEXT_PUBLIC_GOOGLE_CMP`, `NEXT_PUBLIC_ADSENSE_SLOT_{RANKINGS_TOP,RANKINGS_BOTTOM,TEAM_MID,TEAM_BOTTOM,ARTICLE_MID,ARTICLE_BOTTOM}`, `NEXT_PUBLIC_ADS_TXT_EXTRA`, `NEXT_PUBLIC_PUBLISHER_NAME`. No secrets added.

## 5. Tests and evidence

- Python: **106 passed** (61 before). Includes same-name schools in different states, duplicate imports from both teams, missing/conflicting/future/rescheduled results, no contest/canceled/forfeit/suspended/scrimmage, preseason vs unknown, out-of-state opponents, wrong-season baseline, source outage (team disappears → draft, live snapshot untouched), rank-unchanged/rating-up and the reverse, missing previous snapshot, rounding and ties, cutoff checks, idempotent imports, corrected games on both sides, human-review not fabricated, methodology/code agreement.
- Site logic (`npm run test:site`): **16 passed**, including Tupelo/Cleveland Central regressions against real data and page/CSV parity for all teams.
- Browser (`tests-e2e/site.e2e.mjs`): **16/16** default build (no ad/CMP code anywhere, rankings filter/sort/expand, ads.txt plain text, 404, no horizontal scroll and visible nav at 390px, keyboard) and **16/16** ads test build with a synthetic ID and stubbed Google scripts (two labelled slots away from controls, unfilled and blocked collapse, consent defaults before analytics, withdrawal link, no ad code on 9 excluded pages, verification tag and ads.txt).
- Engine regression: identical (see §1). Lint clean; build OK.
- Screenshots: `reports/screenshots/` — before/after for Tupelo, Cleveland Central, Falkner, mobile home; after for Houston, Ripley, Walnut, corrections, archive (mobile), home; and the ads test build.

Representative pages were checked in every class (Tupelo 7A, Warren Central 6A, Cleveland Central and Pontotoc 5A, Ripley and Houston 4A, Noxubee County 3A, Walnut and East Webster 2A, Falkner and Leflore County 1A), plus external opponents (Christ Presbyterian Academy, Middleton).

## 6. Editorial drafts awaiting review

All three are `status: "draft"`, not public, not in the sitemap, and ad-free. Reviewable Markdown is in `reports/editorial-drafts/`.

1. `2026-week-04-weekly-analysis` — top 10, class leaders, largest rating gains with results, schedule strength, data notes.
2. `2026-week-04-risers-and-fallers` — eight biggest moves each way with the results behind them; rank vs rating moving separately.
3. `2026-rankings-performance-review-weeks-1-3` — using only rankings published before kickoff, the higher-rated team won 216 of 304 games between ranked MHSAA teams (71.1%): Week 1 ranking 64.4%, Week 2 71.1%, Week 3 77.7%; 85.5% when the pregame gap was 15+ points. Exclusions (33 non-MHSAA games, 2 under-review games) are disclosed.

To publish: read the Markdown, verify the figures against the rankings/archive, edit the JSON if needed, then
`python -m mfpi.editorial publish <slug> --reviewer "Your Full Name" --confirm-reviewed`, commit, push to `main`.
Before publishing the analysis pieces, decide how to present Houston's Sept. 11 listing (the drafts already disclose it).

## 7. AdSense readiness

See `ADSENSE.md` for the full checklist. In short: completed and tested — configuration, verification tag, ads.txt, central eligibility, placement limits, collapse on unfilled/blocked, consent-mode defaults, CMP hooks, privacy policy. Not verifiable here — real ad rendering, the real Google CMP flows, the live host. Owner actions — set the publisher ID, verify the site, configure Privacy & messaging, create ad units, keep Auto ads off (or add exclusions), set the publisher name, review/publish analysis, then submit. No code blocker remains.

## 8. Deployment and rollback

Status: **not deployed**. To deploy: open a pull request from this branch to `main`, review, merge. `deploy.yml` then lints, runs site tests, audits `data/current`, validates articles, builds and deploys to Cloudflare Workers. Merge before Tuesday 11:00 a.m. CT if the Week 5 run should use the new pipeline (it will apply the Cleveland mapping only if the feed's city matches).

Rollback: revert the merge commit on `main` and run **Actions → Deploy site**, or in Cloudflare → Workers → `mississippi-football-power-index` → Deployments, roll back to the previous version (`npx wrangler rollback`). No data migration to undo; published snapshots were not modified. Snapshot data is bundled into each Worker build, so a Cloudflare rollback restores old code and old data together and is the safe option. Do **not** revert only the code in git after the new pipeline has published a snapshot: new snapshots use `null` for averages of teams without games, which the old dashboard cannot render. In that case revert the snapshot commit too, or keep the new code.

## 9. Going forward

- **Imports:** unchanged schedule (Tuesday 11:00 CT). Each run validates inputs, audits the output, and publishes only if nothing is blocking; `audit.json` travels with each snapshot and in the workflow artifacts.
- **Validation:** read `data/current/audit.json` (or the workflow artifact) every week. Resolve warnings by evidence; add reviewed identities rather than aliases for same-name problems.
- **Corrections:** confirmed errors in a published week → fix the input, `python calculate_rankings.py --live --week N --corrected`; the site's correction log updates automatically.
- **Editorial:** generate drafts after each run, review, publish under your name; keep to a few substantive pieces a week.
- **Ads:** every new page type must pass through `pageAds()`; add a new `PageKind` to `app/lib/ads.ts` and decide eligibility there, not in the page.
