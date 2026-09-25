# AdSense readiness

This file separates what Google's policies require from choices this site makes
to be conservative. Nothing here guarantees approval; approval is decided by
Google on the live site. Rechecked against Google's documentation on
2026-09-25 (via search results; direct fetches were blocked from the build
environment):
[eligibility](https://support.google.com/adsense/answer/9724?hl=en),
[add a site](https://support.google.com/adsense/answer/12169212?hl=en),
[ads.txt guide](https://support.google.com/adsense/answer/12171612?hl=en),
[consent requirements for the EEA, UK and Switzerland](https://support.google.com/adsense/answer/13554116?hl=en),
[consent revocation link](https://support.google.com/adsense/answer/10959060?hl=en),
[Auto ads page exclusions](https://support.google.com/adsense/answer/9262311?hl=en).

## How it is wired

| Piece | Where | Behaviour |
|---|---|---|
| Configuration | `app/site.ts`, `app/lib/ads.ts` | Build-time `NEXT_PUBLIC_*` variables. No valid `ca-pub-` + 16 digits ⇒ everything below is off. |
| Site verification | `app/layout.tsx` | `<meta name="google-adsense-account">` on every page when the client ID is set. Loads no ad code. |
| ads.txt | `app/ads.txt/route.ts` | Always `text/plain`. With an ID: `google.com, pub-…, DIRECT, f08c47fec0942fa0`, plus any `NEXT_PUBLIC_ADS_TXT_EXTRA` lines. Without: comments only. |
| Eligibility | `adEligibility()` in `app/lib/ads.ts` | Single decision for every page. Ineligible pages get no slot **and no AdSense script**. |
| Slots | `app/ads/ad-slot.tsx`, `app/ads/page-ads.tsx` | Max two per page, labelled "Advertisement", reserved height, collapse when unfilled or when the script never answers (blocked). |
| Consent defaults | `app/ads/consent.tsx`, `app/analytics.tsx` | Consent Mode v2: `ad_storage`, `ad_user_data`, `ad_personalization`, `analytics_storage` = denied in EEA/UK/CH before any Google tag. |
| Certified CMP | `GoogleCmpTag` | Google Privacy & messaging tag on every page (ad-free pages too) when `NEXT_PUBLIC_GOOGLE_CMP=true`. Footer "Privacy and cookie settings" calls `googlefc.showRevocationMessage`. |

Placements: rankings — after the introduction (separated from filters by the
weekly-signal cards) and after the full table; team pages — after the
"Why … is ranked here" section and after the rating breakdown; reviewed
articles — mid-article between complete sections and at the end. Never inside
ranking rows, beside tabs/sort, in the stat card, or in a score table.

Ad-free (site choice): about, contact, privacy, advertise, corrections,
analysis index, team directory, 404, draft previews, team pages whose results
are unavailable, unreviewed articles.

## Checklist

### Completed and tested
- Publisher ID never invented; integration off without it (`tests-js/ads.test.mjs`).
- `/ads.txt` returns `text/plain`, not the HTML 404 fallback (e2e, both builds).
- Verification meta tag separate from serving (unit + e2e in ads build).
- Central eligibility; no ad script on privacy/contact/about/advertise/corrections/analysis/teams/404 or a results-unavailable team page (e2e, ads build).
- Max two slots; not inside rows or controls; top slot >150px from filters (e2e).
- Unfilled and blocked ad scripts collapse the slot; rankings, filters, sort and row expansion still work (e2e).
- Consent Mode defaults are pushed before the analytics `config` command (e2e).
- Consent revocation button calls the CMP API (e2e with a stubbed CMP).
- Default production build contains no AdSense or CMP requests (e2e).
- Privacy policy describes what is actually loaded and states the current ad status.
- Substantive content: rankings, 225 team pages with explanations, weekly archive, methodology, corrections log. Drafts are never public.

### Implemented but not verifiable with current access
- Real AdSense rendering, fill, and layout shift with live creatives (needs a real publisher ID and a deployed site).
- Google Privacy & messaging behaviour: the message, regional targeting, Accept/Reject/Manage flows and consent-mode signalling from the real CMP (tested only with a stub).
- Live `https://www.mississippifootballrankings.com/ads.txt`, apex→www redirect and crawler access (the live site was unreachable from this environment).

### Requires owner action
1. **Publisher ID.** In AdSense → Account → Account information, copy the `pub-` ID. In GitHub → Settings → Secrets and variables → Actions → **Variables**, set `NEXT_PUBLIC_ADSENSE_CLIENT=ca-pub-XXXXXXXXXXXXXXXX`. Redeploy (Actions → Deploy site). This turns on the meta tag and the ads.txt line only.
2. **Add the site in AdSense** (Sites → Add site → `mississippifootballrankings.com`), choose **Meta tag** verification, and use **Check for updates** on ads.txt after the deploy.
3. **Existing sellers.** If any other ad network or the Casey Lott sponsorship requires ads.txt lines, put them (one per line) in `NEXT_PUBLIC_ADS_TXT_EXTRA`. None were found in the repository.
4. **Consent.** In AdSense → Privacy & messaging, create a European regulations (GDPR) message for EEA/UK/Switzerland, enable Google consent mode integration for your tags, publish it, then set `NEXT_PUBLIC_GOOGLE_CMP=true` and redeploy. Test Accept, Reject/Do not consent, Manage options, and the footer link from an EEA location (VPN) before enabling ads.
5. **Ad units.** Create display units (responsive) and set `NEXT_PUBLIC_ADSENSE_SLOT_RANKINGS_TOP`, `…_RANKINGS_BOTTOM`, `…_TEAM_MID`, `…_TEAM_BOTTOM`, `…_ARTICLE_MID`, `…_ARTICLE_BOTTOM`. Set `NEXT_PUBLIC_ADS_ENABLED=true` only after approval.
6. **Auto ads.** Leave Auto ads **off**. If you turn it on, add AdSense page exclusions ("All pages under this section") for `/privacy`, `/contact`, `/about`, `/advertise`, `/corrections`, `/analysis` (index), `/teams`, and the team pages listed as results-unavailable on `/corrections`. The site already omits the AdSense tag on those pages, but a client-side navigation from an eligible page keeps the tag loaded, so account-side exclusions are still needed.
7. **Publisher identity.** Set `NEXT_PUBLIC_PUBLISHER_NAME` to the person or business that operates the site as you want it shown on About. It is blank because it could not be verified from the repository.
8. **Review and publish at least the Week 4 analysis drafts** (see HANDOFF.md) so the Weekly Analysis section has reviewed content.
9. **Submit for review** in AdSense. Not done here.

### Unresolved blockers
- None in code. Approval depends on the owner actions above and on Google's review of the live site.
- Data issues that a reviewer could notice and that need owner confirmation: Houston's two Sept. 11 games; Cleveland Central and Northside showing results unavailable (see HANDOFF.md §3).

## Testing locally

```bash
# default build: advertising off
npm run build && npx vinext start --port 4321
BASE=http://localhost:4321 MODE=off node tests-e2e/site.e2e.mjs

# ads build with a synthetic ID (never deploy this build)
NEXT_PUBLIC_ADSENSE_CLIENT=ca-pub-0000000000000000 NEXT_PUBLIC_ADS_ENABLED=true NEXT_PUBLIC_GOOGLE_CMP=true \
NEXT_PUBLIC_ADSENSE_SLOT_RANKINGS_TOP=1 NEXT_PUBLIC_ADSENSE_SLOT_RANKINGS_BOTTOM=2 \
NEXT_PUBLIC_ADSENSE_SLOT_TEAM_MID=3 NEXT_PUBLIC_ADSENSE_SLOT_TEAM_BOTTOM=4 npm run build
npx vinext start --port 4322 & BASE=http://localhost:4322 MODE=ads node tests-e2e/site.e2e.mjs
```

The e2e script stubs Google's scripts; it never loads or clicks a live ad.
It needs Playwright (`PLAYWRIGHT_MODULE=/path/to/playwright` if not installed locally).
