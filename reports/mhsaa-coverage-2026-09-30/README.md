# MHSAA football coverage investigation — September 30, 2026

All 225 active programs in the freshly retrieved official 2025–27 classification
list are already present in MFPI. Northside is the only program with zero results
in the saved Week 5 snapshot. No additional ranked team needs to be created.

## Confirmed corrections

The official score center calls Northside **Broad Street**, stable team ID
**243751**, city **Shelby, MS**. All four official games exactly match both
participants' current MaxPreps schedules. MFPI previously kept that source team
external, so Northside received none of the results while its opponents did.
The reviewed mapping requires the exact source, ID, listed name and city. It
links the existing official games; it does not create duplicate games.

| Date | Opponent | Northside result | Official game ID |
|---|---|---|---|
| Aug 28 | Jefferson County | W 27–6 | 7810684 |
| Sep 11 | Shaw | W 44–0 | 7731756 |
| Sep 18 | Leflore County | L 14–16 | 7731878 |
| Sep 25 | West Bolivar | W 34–8 | 7731796 |

Northside's corrected record is **3–1**, PF **119**, PA **30**. Evidence is saved
in `tests/fixtures/northside_2026.json` as four official-feed nodes and eight
secondary observations. The official API is
<https://api.scorebooklive.com/v2/graphql>; the source schedule is
<https://www.maxpreps.com/ms/shelby/north-side-gators/football/schedule/>.

Leake's active successor profile now uses
<https://www.maxpreps.com/ms/carthage/leake-gators/football/>. Its schedule's
`schoolId` remains **80480779-619d-4cd9-9feb-c26005e4201f**, the same UUID already
recognized by MFPI's query-URL rule. The old rule selected the retired 0–0
Leake Central profile after this URL change. Both verified URL forms are now
recognized; the retired profile is excluded only when the reviewed successor
is also present and the old record is exactly 0–0.

## Statewide evidence and remaining gaps

`team-coverage.csv` contains every active program, its official source identity,
imported result count, snapshot/replayed/media records, and secondary profile.
`coverage.json` contains exact evidence URLs and all remaining discrepancies.
The initial audit fetched 225 readable schedules and all official score dates
from August 27 through September 29. It compared newly retrieved sources at the
September 29 cutoff; it is not a historical reconstruction of media inputs.

After the identity/profile fixes, no active program remains without results.
Eleven primary listings remain unresolved, affecting 17 ranked teams:

| Game ID | Date | Matchup |
|---|---|---|
| 7731608 | Aug 28 | Humphreys County – Yazoo City |
| 7808266 | Sep 5 | Greenwood Christian Academy – Kosciusko |
| 7212436 | Sep 11 | DeSoto Central – Jonesboro |
| 7587001 | Sep 11 | South Panola – Southaven |
| 7614774 | Sep 11 | Myrtle – Belmont |
| 7614790 | Sep 11 | New Albany – Itawamba Agricultural |
| 7731841 | Sep 18 | South Pike – Greenville Christian |
| 7614853 | Sep 25 | Coffeeville – Vardaman |
| 7614888 | Sep 25 | Leake County – Heidelberg |
| 7614890 | Sep 25 | West Tallahatchie – Ashland |
| 7731800 | Sep 25 | Central Holmes Christian – French Camp |

Two secondary-only listings need further verification: Hazlehurst's Aug 28
76–0 against a placeholder **Varsity Opponent**, and Wilkinson County's Sep 11
64–0 against **Helix Mentorship & Maritime Academy**. Neither result is invented
or added by this patch. Four media-record discrepancies remain (Booneville,
Hazlehurst, North Panola, Resurrection). Eleven official/secondary final-score
discrepancies and twelve disagreements between secondary schedule views are
also recorded. The latter include one view with a final and another still
showing a preview; they are not all contradictory final scores. Official finals
remain authoritative.

The weekly pipeline now compares full fresh schedules against its imported
ledger. It reports missing listings and source disagreements without changing
results. Identity checks use exact matched profile URLs, separating the two
Enterprise schools and out-of-state same-name opponents. A page with no
readable events enters the existing cache/outage reporting path instead of
silently replacing a good cache.

## Verification

- Full Python suite: **130 tests passed** (113 at baseline).
- Site display/ad tests: **17 passed**.
- ESLint passed.
- Northside evidence regression verifies four games, 3–1, 119–30 points, exact
  source identity guards, idempotence and no double counting.
- Leake tests cover both URL forms, both row orders and duplicate-match guards.
- Core ranking formula, weights, SRS and bye logic are unchanged.

Reproduce the statewide audit with:

```sh
python -m mfpi.coverage --snapshot data/current --cache-root work/coverage-cache --output reports/coverage-current --fetch
```

Omit `--fetch` to replay the saved audit cache. This command never publishes rankings.

The published correction reuses the completed September 30 live source pulls,
preserving their retrieval timestamps. The snapshot audit passes with zero
blocking findings; 567 of 578 primary listings are verified (98.10%).
An audit-only regression accepts rounding uncertainty of half the last stored
eight-decimal place, while incorrect display values remain blocked. Automated
articles and their publication gates are unchanged.
