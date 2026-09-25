// Central advertising configuration and page-level eligibility.
//
// Every Google ad on the site goes through `adEligibility`. A page that is not
// eligible renders no ad slot AND does not load the AdSense script, so Auto ads
// (if ever turned on in the AdSense account) have no tag to run from on it.
// Account-side Auto ads page exclusions are still required; see ADSENSE.md.
//
// This file has no imports so the Node test runner can load it directly.

export type AdsConfig = {
  /** AdSense client ID, `ca-pub-` followed by 16 digits. Empty = not configured. */
  client: string;
  /** Serve Google ad slots. Verification and ads.txt work without this. */
  enabled: boolean;
  slots: Partial<Record<AdPlacement, string>>;
  /** Google Privacy & messaging (certified CMP) tag is on and configured in the account. */
  googleCmp: boolean;
  /** Extra authorized-seller lines for ads.txt, one per line. */
  adsTxtExtra: string;
};

export type AdPlacement = 'rankings-top' | 'rankings-bottom' | 'team-mid' | 'team-bottom' | 'article-mid' | 'article-bottom';

export type PageKind =
  | 'rankings'
  | 'team'
  | 'article'
  | 'archive'
  | 'directory'
  | 'methodology'
  | 'utility' // about, contact, privacy, advertise, corrections
  | 'analysis-index'
  | 'error'
  | 'draft'
  | 'admin'
  | 'search';

export type PageAdContext = {
  kind: PageKind;
  /** The page carries substantive publisher content (not loading, empty or placeholder). */
  substantive: boolean;
  /** Team pages: data status for the team (see lib/format.ts dataStatus). */
  teamDataStatus?: string;
  /** Articles: review status. Only human-reviewed, published articles are eligible. */
  reviewStatus?: string;
  reviewedBy?: string | null;
};

export type Eligibility = { eligible: boolean; reason: string };

const CLIENT_PATTERN = /^ca-pub-\d{16}$/;

export function parseAdsConfig(env: Record<string, string | undefined>): AdsConfig {
  const client = (env.NEXT_PUBLIC_ADSENSE_CLIENT ?? '').trim();
  const valid = CLIENT_PATTERN.test(client);
  return {
    client: valid ? client : '',
    enabled: valid && env.NEXT_PUBLIC_ADS_ENABLED === 'true',
    slots: {
      'rankings-top': env.NEXT_PUBLIC_ADSENSE_SLOT_RANKINGS_TOP || undefined,
      'rankings-bottom': env.NEXT_PUBLIC_ADSENSE_SLOT_RANKINGS_BOTTOM || undefined,
      'team-mid': env.NEXT_PUBLIC_ADSENSE_SLOT_TEAM_MID || undefined,
      'team-bottom': env.NEXT_PUBLIC_ADSENSE_SLOT_TEAM_BOTTOM || undefined,
      'article-mid': env.NEXT_PUBLIC_ADSENSE_SLOT_ARTICLE_MID || undefined,
      'article-bottom': env.NEXT_PUBLIC_ADSENSE_SLOT_ARTICLE_BOTTOM || undefined,
    },
    googleCmp: valid && env.NEXT_PUBLIC_GOOGLE_CMP === 'true',
    adsTxtExtra: env.NEXT_PUBLIC_ADS_TXT_EXTRA ?? '',
  };
}

/** Pages we keep ad-free as a conservative site choice, not a Google rule. */
const AD_FREE_KINDS: PageKind[] = ['utility', 'error', 'draft', 'admin', 'search', 'analysis-index', 'directory'];

export function adEligibility(config: AdsConfig, page: PageAdContext): Eligibility {
  if (!config.client) return { eligible: false, reason: 'no AdSense publisher ID configured' };
  if (!config.enabled) return { eligible: false, reason: 'ads disabled by configuration' };
  if (AD_FREE_KINDS.includes(page.kind)) return { eligible: false, reason: `${page.kind} pages are ad-free` };
  if (!page.substantive) return { eligible: false, reason: 'page lacks substantive content' };
  if (page.kind === 'team' && page.teamDataStatus === 'unavailable') {
    return { eligible: false, reason: 'team results unavailable; page kept ad-free until data is complete' };
  }
  if (page.kind === 'article' && (page.reviewStatus !== 'published' || !page.reviewedBy)) {
    return { eligible: false, reason: 'article not yet human-reviewed and published' };
  }
  return { eligible: true, reason: 'eligible' };
}

/** Slots to render, capped at two per page (our design preference). */
export function slotsFor(config: AdsConfig, eligibility: Eligibility, placements: AdPlacement[]): AdPlacement[] {
  if (!eligibility.eligible) return [];
  return placements.filter((placement) => Boolean(config.slots[placement])).slice(0, 2);
}

export function adsTxt(config: AdsConfig): string {
  const lines = ['# ads.txt for www.mississippifootballrankings.com', '# Authorized digital sellers (IAB Tech Lab ads.txt).'];
  if (config.client) {
    lines.push(`google.com, ${config.client.replace(/^ca-/, '')}, DIRECT, f08c47fec0942fa0`);
  } else {
    lines.push('# No advertising system is authorized yet.');
  }
  for (const line of config.adsTxtExtra.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (trimmed) lines.push(trimmed);
  }
  return `${lines.join('\n')}\n`;
}

/** EEA, UK and Switzerland (ISO 3166-1): consent defaults to denied here. */
export const CONSENT_REGIONS = [
  'AT', 'BE', 'BG', 'HR', 'CY', 'CZ', 'DK', 'EE', 'FI', 'FR', 'DE', 'GR', 'HU', 'IE', 'IT', 'LV', 'LT', 'LU',
  'MT', 'NL', 'PL', 'PT', 'RO', 'SK', 'SI', 'ES', 'SE', 'IS', 'LI', 'NO', 'GB', 'CH',
];

/** Inline script run before any Google tag: Consent Mode v2 defaults. */
export function consentDefaultsScript(): string {
  return [
    'window.dataLayer=window.dataLayer||[];',
    'function gtag(){dataLayer.push(arguments);}',
    `gtag('consent','default',{ad_storage:'denied',ad_user_data:'denied',ad_personalization:'denied',analytics_storage:'denied',region:${JSON.stringify(CONSENT_REGIONS)},wait_for_update:500});`,
  ].join('');
}
