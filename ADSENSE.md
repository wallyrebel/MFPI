# AdSense setup

## Connection installed September 28, 2026

The owner supplied publisher ID `ca-pub-3245500092050206` and this seller record:

```text
google.com, pub-3245500092050206, DIRECT, f08c47fec0942fa0
```

- `app/site.ts` defaults to that public publisher ID. An optional build-time
  `NEXT_PUBLIC_ADSENSE_CLIENT` overrides it; both `pub-` and `ca-pub-` formats work.
- The root layout includes the supplied asynchronous AdSense connection script
  in the head on every page, once, plus the ownership verification meta tag.
- `/ads.txt` serves the matching seller line as plain text.
- Consent defaults precede Google's scripts. `ExternalScript` prevents React
  from hoisting external scripts ahead of those defaults.
- The privacy policy discloses the connection script and Google's technical requests.
- Manual display units remain disabled until approval and real slot IDs are supplied.
  Auto ads are controlled independently in the AdSense account.

## Finish in AdSense

1. Add **mississippifootballrankings.com** without `www`, a protocol, a slash,
   or spaces. The “valid top-level domain” message concerns the input format.
   Keep HTTPS enabled on the website.
2. After deployment, confirm the code is installed and click **Verify** or
   **Request review**. Both script and meta-tag verification are supported.
3. Check ads.txt status. Both the bare domain and www reach the same file.
   Google may take time to recrawl it.
4. In **Privacy & messaging**, publish the applicable consent messages, including
   a European regulations message for EEA/UK/Switzerland. Enable its consent-mode
   integration. Set `NEXT_PUBLIC_GOOGLE_CMP=true` at build time and redeploy after
   configuring Google's CMP. Test consent and the footer's privacy settings link.
5. After Google approves the site, either enable **Auto ads** or create responsive
   display units for the existing manual placements described below.

The connection script runs sitewide. For Auto ads, configure account-side page
exclusions for utility pages (`/privacy`, `/contact`, `/about`, `/advertise`,
`/corrections`, `/teams`), error pages, and unavailable team pages. Exclude `/analysis`
exactly (not every article underneath it) and exclude unreviewed articles individually.
Manual slot eligibility does not restrict Auto ads.

## Optional manual placements

Set `NEXT_PUBLIC_ADS_ENABLED=true` and the real display-unit IDs in these public
GitHub Actions repository variables, then deploy:

- `NEXT_PUBLIC_ADSENSE_SLOT_RANKINGS_TOP`, `NEXT_PUBLIC_ADSENSE_SLOT_RANKINGS_BOTTOM`
- `NEXT_PUBLIC_ADSENSE_SLOT_TEAM_MID`, `NEXT_PUBLIC_ADSENSE_SLOT_TEAM_BOTTOM`
- `NEXT_PUBLIC_ADSENSE_SLOT_ARTICLE_MID`, `NEXT_PUBLIC_ADSENSE_SLOT_ARTICLE_BOTTOM`

At most two manual units appear per page. They are labelled Advertisement and
kept out of tables and controls. Unavailable team pages, utility/error pages and
unreviewed articles receive no manual units. Missing slot IDs render no units.
Other authorized sellers can be added through `NEXT_PUBLIC_ADS_TXT_EXTRA`.

## Deployment and checks

Push to main to run the existing Deploy site workflow. Public AdSense settings
are used by both normal and weekly builds. Local edits alone do not publish.

Run `npm run test:site`, `npm run lint`, and `npm run build`. Browser tests in
`tests-e2e/site.e2e.mjs` stub Google requests and never click real ads. Default
`MODE=off` means manual ads off, with the production connection script installed;
`MODE=ads` uses a synthetic publisher ID and configured test slots. Never deploy
synthetic credentials.

Public checks on September 28 confirmed the apex redirects to the HTTPS www
site and both `/ads.txt` addresses are reachable. Google approval, live ad fill,
and the account's CMP configuration must be checked separately.

References: [connect a site](https://support.google.com/adsense/answer/7584263),
[domain format](https://support.google.com/adsense/answer/2784438),
[consent requirements](https://support.google.com/adsense/answer/13554116),
[Auto ads exclusions](https://support.google.com/adsense/answer/9262311).
