// The apex domain has no DNS record; www is the host that actually serves.
export const siteUrl =
  process.env.NEXT_PUBLIC_SITE_URL ||
  'https://www.mississippifootballrankings.com';

// GA4 measurement IDs are public — they ship in the page source — so the
// production ID is the default and the env var only exists to point a local
// or preview build somewhere else (or at '' to switch analytics off).
export const gaMeasurementId =
  process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID ??
  'G-Y623H9Z0KC';
