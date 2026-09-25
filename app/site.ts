import { parseAdsConfig } from './lib/ads';

// The apex domain has no DNS record; www is the host that actually serves.
export const siteUrl =
  process.env.NEXT_PUBLIC_SITE_URL ||
  'https://www.mississippifootballrankings.com';

export const advertisingEmail = 'editor@sportsmississippi.com';
export const editorEmail = 'editor@sportsmississippi.com';

// Publisher identity shown on the About page. Leave a field empty rather than
// guess: the site states only what the owner has confirmed. See HANDOFF.md.
export const publisher = {
  /** Person or business legally responsible for the site, as the owner wants it shown. */
  operatorName: process.env.NEXT_PUBLIC_PUBLISHER_NAME ?? '',
  /** Person who handles corrections, if different from the operator. */
  correctionsContact: editorEmail,
};

// GA4 measurement IDs are public — they ship in the page source — so the
// production ID is the default and the env var only exists to point a local
// or preview build somewhere else (or at '' to switch analytics off).
export const gaMeasurementId =
  process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID ??
  'G-Y623H9Z0KC';

// Google AdSense. Every value is public (it ships in page source), but none is
// invented here: without a real `ca-pub-` ID the integration stays off.
// Each variable is referenced by name so the build can inline it.
export const adsConfig = parseAdsConfig({
  NEXT_PUBLIC_ADSENSE_CLIENT: process.env.NEXT_PUBLIC_ADSENSE_CLIENT,
  NEXT_PUBLIC_ADS_ENABLED: process.env.NEXT_PUBLIC_ADS_ENABLED,
  NEXT_PUBLIC_ADSENSE_SLOT_RANKINGS_TOP: process.env.NEXT_PUBLIC_ADSENSE_SLOT_RANKINGS_TOP,
  NEXT_PUBLIC_ADSENSE_SLOT_RANKINGS_BOTTOM: process.env.NEXT_PUBLIC_ADSENSE_SLOT_RANKINGS_BOTTOM,
  NEXT_PUBLIC_ADSENSE_SLOT_TEAM_MID: process.env.NEXT_PUBLIC_ADSENSE_SLOT_TEAM_MID,
  NEXT_PUBLIC_ADSENSE_SLOT_TEAM_BOTTOM: process.env.NEXT_PUBLIC_ADSENSE_SLOT_TEAM_BOTTOM,
  NEXT_PUBLIC_ADSENSE_SLOT_ARTICLE_MID: process.env.NEXT_PUBLIC_ADSENSE_SLOT_ARTICLE_MID,
  NEXT_PUBLIC_ADSENSE_SLOT_ARTICLE_BOTTOM: process.env.NEXT_PUBLIC_ADSENSE_SLOT_ARTICLE_BOTTOM,
  NEXT_PUBLIC_GOOGLE_CMP: process.env.NEXT_PUBLIC_GOOGLE_CMP,
  NEXT_PUBLIC_ADS_TXT_EXTRA: process.env.NEXT_PUBLIC_ADS_TXT_EXTRA,
});
