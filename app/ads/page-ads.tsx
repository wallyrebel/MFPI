import { adsConfig } from '../site';
import { adEligibility, slotsFor, type AdPlacement, type PageAdContext } from '../lib/ads';
import { AdSlot } from './ad-slot';

/**
 * Resolve a page's ad eligibility once. The AdSense script is only emitted on
 * eligible pages, so an ineligible page has no ad code at all.
 */
export function pageAds(context: PageAdContext, placements: AdPlacement[]) {
  const eligibility = adEligibility(adsConfig, context);
  const allowed = new Set(slotsFor(adsConfig, eligibility, placements));
  return {
    eligibility,
    script: allowed.size > 0 ? <AdsenseScript /> : null,
    slot(placement: AdPlacement) {
      const slot = adsConfig.slots[placement];
      return allowed.has(placement) && slot ? <AdSlot client={adsConfig.client} slot={slot} placement={placement} /> : null;
    },
  };
}

function AdsenseScript() {
  return (
    <script
      async
      src={`https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=${adsConfig.client}`}
      crossOrigin="anonymous"
    />
  );
}
