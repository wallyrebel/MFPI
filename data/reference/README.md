# MHSAA reference classifications

`mhsaa_teams_2025_27.json` preserves the official 2025–27 football classifications
retrieved on September 2, 2026. The source URL and retrieval timestamp are in the
file. Its active team IDs, classifications, and regions match the published
2026 week-1 team universe; provider-level inactive-program overrides still apply.

For the 2025 and 2026 seasons, the CLI uses this reference when the local source
cache is absent. Weekly scores and media rankings continue to refresh live.
`--refresh-teams` explicitly bypasses both saved copies and fetches MHSAA again.
Review and update the reference when MHSAA changes classifications; do not use
this two-year reference for later seasons.
