# MFPI methodology — version 3.2

MFPI asks: based on whom a team played and how it performed, how strong is that team right now? Eighty percent of the answer comes from MHSAA classifications, schedules, and scores. Twenty percent comes from statewide Media Rank and Strength of Schedule inputs.

## Final components

Each raw component becomes a robust statewide percentile among active MHSAA 1A–7A teams. Ties receive average rank; missing early-season values are transparently neutral. The weighted sum is constrained to 1.0–100.0 and displayed to one decimal, while ranking uses full precision.

| Component | Weight | What it measures |
|---|---:|---|
| Opponent-adjusted performance | 35% | Margin of victory/loss adjusted for opponent and site |
| MFPI strength of schedule | 20% | Average current SRS of completed opponents |
| Media Rank | 10% | Statewide ordinal rank, converted to a higher-is-better percentile |
| Media Strength of Schedule | 10% | Published schedule-strength field; `0.0` is treated as unavailable/neutral |
| Points scored | 8% | PF/game, capped at 49 in each game |
| Points allowed | 8% | Defensive value from PA/game, capped at 49 |
| Record | 5% | Wins plus half credit for ties |
| Recent form | 4% | Last three opponent-adjusted performances |

## Enrollment-class starting assumption

Before the statewide game graph is well connected, MFPI assumes larger enrollment classes are stronger on average. The class prior is expressed in football points:

```text
7A +7.5   6A +5.0   5A +2.5   4A 0.0
3A −2.5   2A −5.0   1A −7.5
```

This is not a permanent bonus added to the final MFPI. It is a fading prior inside SRS: 2.0 equivalent games through two games played, 1.0 through five, and 0.25 afterward. Real margins and opponent chains progressively replace it. An excellent lower-class team can pass higher-class teams; the model simply starts from the requested assumption when evidence is sparse.

Playing up/down follows directly. If a 4A team faces 7A, the opponent starts three class steps higher and strengthens both that game's opponent-adjusted performance and schedule. Facing 1A does the reverse. Output stores average class differential and counts of up, same-class, and down games. Opponents with no MHSAA class do not affect those counts, but their learned SRS still affects SOS.

## Opponent-adjusted margin and SRS

From each team's perspective:

```text
adjusted margin = 42 × tanh((points for − points against) / 42)
game performance = opponent SRS + adjusted margin + site adjustment
```

A road team receives +2 performance points and a home team −2; the recorded score never changes. The hyperbolic tangent gives blowouts diminishing returns. The SRS repeatedly averages game performances plus the fading class prior until every team's largest change is below 0.01 or 100 iterations are reached, then centers the MHSAA distribution at zero.

## Other calculations

- **SOS:** average current SRS of all completed opponents, normalized statewide. It is not opponent win percentage.
- **Record:** `(wins + 0.5 × ties) / games played`.
- **Offense:** season average of `min(points scored, 49)`; displayed PF/G remains actual.
- **Defense:** season average of `49 − min(points allowed, 49)`; displayed PA/G remains actual.
- **Recent form:** opponent-adjusted game performances from the last three games, weighted 1.00, 0.70, and 0.50 newest-first.
- **Media Rank:** the weekly statewide ordering after filtering to active MHSAA 1A–7A teams. The rating is stored for audit, but the rank percentile is the formula input.
- **Media Strength of Schedule:** the weekly published schedule-strength value normalized statewide. A `0.0` opening value is neutral instead of being treated as the state's weakest schedule.
- **Out-of-state opponents:** when a Mississippi schedule includes a non-Mississippi team, MFPI checks that opponent's MaxPreps team URL and state ranking when available. Its published rating becomes a capped, fading SRS prior (rather than a Mississippi ranking or class assignment), so a game against a highly rated Alabama, Tennessee, Arkansas, or Louisiana team receives appropriate opponent credit even before that opponent has a connected local schedule.

## Ranking and ties

### Confirmed bye-week stability

On a confirmed bye with unchanged verified results, the final score is
`0.90 × previous week's published MFPI + 0.10 × current recalculated MFPI`.
The adjustment is symmetric for increases and decreases. It protects the score,
not a rank position: other teams may pass an idle team. Playing teams keep the
normal formula. Teams with no previous games receive no protection.

A fresh secondary team schedule must contain entries before and after the
weekly cutoff window, with no contest during it. Any official game in that
window, unresolved historical listing, cached/failed team schedule, or changed
result prevents protection. Future snapshots store game-level fingerprints to
detect corrections. Legacy snapshots without fingerprints are eligible only
with one previous game and matching recorded scores, record, capped scoring
components, and class-schedule statistics.

Component values continue to describe the unsmoothed recalculation. The JSON
and team details separately disclose the previous score, recalculated score,
90% weight, and adjustment so the final score remains auditable. Corrections
always compare with the latest audited snapshot of the *previous week*, never
with an earlier run of the same week.

State and class lists use the same final MFPI score; class scores are never recalculated. Order is unrounded MFPI, opponent-adjusted performance, SOS, head-to-head when applicable, capped season scoring margin, then team name for deterministic output. Weekly movement compares the latest audited prior-week snapshot. A team absent from that snapshot is `NEW`.
