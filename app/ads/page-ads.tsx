import { adsConfig } from '../site';
import { adEligibility, slotsFor, type AdPlacement, type PageAdContext } from '../lib/ads';
import { AdSlot } from './ad-slot';

/**
 * Resolve manual slot eligibility. The root layout loads the AdSense script once.
 * Account-side page exclusions control Auto ads independently.
 */
export function pageAds(context: PageAdContext, placements: AdPlacement[]) {
  const eligibility = adEligibility(adsConfig, context);
  const allowed = new Set(slotsFor(adsConfig, eligibility, placements));
  return {
    eligibility,

    slot(placement: AdPlacement) {
      const slot = adsConfig.slots[placement];
      return allowed.has(placement) && slot ? <AdSlot client={adsConfig.client} slot={slot} placement={placement} /> : null;
    },
  };
}
