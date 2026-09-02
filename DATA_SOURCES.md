# Data sources

MFPI has no upload step. It automatically reads official MHSAA classification and scoreboard data plus MaxPreps statewide football rankings under the owner's media-partner permission.

## MHSAA teams and classifications

MFPI loads the official [2025–27 MHSAA football regions](https://www.misshsaa.com/2024/11/19/2025-27-football-regions/). Only teams on that list in Classes 1A–7A are ranked. MAIS, homeschool, out-of-state, and other teams may exist as opponents for schedule calculations but never enter the official ranking table.

Classification is also the early-season connectivity prior. MFPI records whether each classified opponent is above, equal to, or below the team's class. It never trusts classification metadata from another source.

## MHSAA schedules and results

Schedules and scores come from the official [MHSAA score center](https://scores.misshsaa.com/) through the same public Scorebook Live GraphQL service used by the score-center frontend. MFPI requests only varsity football dates, caches raw daily responses, and retains source IDs/timestamps. A result counts only when status is `COMPLETED` and both scores exist. Jamborees and scrimmages are excluded from expected-game coverage.

## MaxPreps ranking and strength

MFPI starts at the public [MaxPreps Mississippi football rankings](https://www.maxpreps.com/ms/football/rankings/1/) and follows every numbered statewide page. It stores the statewide rank, computer rating, displayed `Str.` value, record, team URL, retrieval timestamp, and MaxPreps update date. Only active schools from the official MHSAA 1A–7A list enter MFPI; MAIS and other schools are ignored.

Team names are matched conservatively to the MHSAA list, with explicit location handling for the two Enterprise programs and the 2026 Leake consolidation. Stale MaxPreps listings for discontinued or consolidated programs are ignored. A weekly dataset must match every active MHSAA team exactly once. Missing or duplicate matches block the update rather than assigning an external value to the wrong school. A displayed MaxPreps strength of `0.0` is retained for audit but treated as unavailable/neutral in the formula, consistent with the attached opening-week report.

## MaxPreps scores as a secondary source

MHSAA remains the primary schedule and result source. MFPI contacts MaxPreps team schedule pages only for MHSAA games that are past the cutoff but still lack a completed score. A MaxPreps result is accepted only when both teams resolve to the same MHSAA matchup and the reported date is the scheduled date or one day earlier/later. The one-day window handles weather and calendar moves without opening broad fuzzy-date matching.

When both team pages report the game, their terminal facts must agree. Conflicting scores or statuses are critical and the MHSAA listing stays unresolved. Explicit MaxPreps forfeits use the displayed 2–0 result and retain the forfeit flag. Cancellation or postponement is accepted only when MaxPreps labels it explicitly; an absent score or stale preview is not treated as evidence that a game was cancelled. Each accepted fallback keeps the MHSAA game ID while recording the MaxPreps event URL, timestamp, actual date, and `maxpreps_secondary` provenance.

## Reconciliation and provenance

Names are normalized through explicit aliases plus conservative fuzzy matching. Ambiguous near-matches are critical because attaching a score to the wrong school would contaminate both teams' opponent chains. External opponents remain unclassified and unranked but retain a learned SRS from their games against MHSAA teams.

Every snapshot includes source URLs and timestamps. SQLite stores the exact teams, games, MaxPreps rank/rating/strength values, secondary-result provenance, component values, formula version, and validation report needed to reproduce a published week.
