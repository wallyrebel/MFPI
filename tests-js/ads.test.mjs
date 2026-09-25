import { test } from 'node:test';
import assert from 'node:assert/strict';
import { adEligibility, adsTxt, consentDefaultsScript, parseAdsConfig, slotsFor } from '../app/lib/ads.ts';

const REAL_LOOKING = 'ca-pub-0000000000000000'; // synthetic test value, not a real account
const on = parseAdsConfig({
  NEXT_PUBLIC_ADSENSE_CLIENT: REAL_LOOKING, NEXT_PUBLIC_ADS_ENABLED: 'true',
  NEXT_PUBLIC_ADSENSE_SLOT_RANKINGS_TOP: '1', NEXT_PUBLIC_ADSENSE_SLOT_RANKINGS_BOTTOM: '2',
  NEXT_PUBLIC_ADSENSE_SLOT_TEAM_MID: '3', NEXT_PUBLIC_ADSENSE_SLOT_TEAM_BOTTOM: '4',
  NEXT_PUBLIC_ADSENSE_SLOT_ARTICLE_MID: '5', NEXT_PUBLIC_ADSENSE_SLOT_ARTICLE_BOTTOM: '6',
});

test('no publisher ID means no ads, and an invalid ID is ignored', () => {
  assert.equal(parseAdsConfig({}).client, '');
  assert.equal(parseAdsConfig({ NEXT_PUBLIC_ADSENSE_CLIENT: 'pub-123', NEXT_PUBLIC_ADS_ENABLED: 'true' }).enabled, false);
  assert.equal(adEligibility(parseAdsConfig({}), { kind: 'rankings', substantive: true }).eligible, false);
});

test('verification is separate from serving: ID set but ads disabled', () => {
  const verifyOnly = parseAdsConfig({ NEXT_PUBLIC_ADSENSE_CLIENT: REAL_LOOKING });
  assert.equal(verifyOnly.client, REAL_LOOKING);
  assert.equal(verifyOnly.enabled, false);
  assert.equal(adEligibility(verifyOnly, { kind: 'rankings', substantive: true }).eligible, false);
  assert.match(adsTxt(verifyOnly), /^google\.com, pub-0000000000000000, DIRECT, f08c47fec0942fa0$/m);
});

test('ad-free page kinds and thin pages are excluded', () => {
  for (const kind of ['utility', 'error', 'draft', 'admin', 'search', 'analysis-index', 'directory']) {
    assert.equal(adEligibility(on, { kind, substantive: true }).eligible, false, kind);
  }
  assert.equal(adEligibility(on, { kind: 'rankings', substantive: false }).eligible, false);
  assert.equal(adEligibility(on, { kind: 'rankings', substantive: true }).eligible, true);
});

test('team pages with unavailable data stay ad-free', () => {
  assert.equal(adEligibility(on, { kind: 'team', substantive: false, teamDataStatus: 'unavailable' }).eligible, false);
  assert.equal(adEligibility(on, { kind: 'team', substantive: true, teamDataStatus: 'complete' }).eligible, true);
});

test('articles need human review before ads', () => {
  assert.equal(adEligibility(on, { kind: 'article', substantive: true, reviewStatus: 'draft', reviewedBy: null }).eligible, false);
  assert.equal(adEligibility(on, { kind: 'article', substantive: true, reviewStatus: 'published', reviewedBy: '' }).eligible, false);
  assert.equal(adEligibility(on, { kind: 'article', substantive: true, reviewStatus: 'published', reviewedBy: 'Jane Editor' }).eligible, true);
});

test('at most two slots per page, and none when ineligible', () => {
  const eligible = { eligible: true, reason: 'eligible' };
  assert.deepEqual(slotsFor(on, eligible, ['rankings-top', 'rankings-bottom', 'team-mid']), ['rankings-top', 'rankings-bottom']);
  assert.deepEqual(slotsFor(on, { eligible: false, reason: 'x' }, ['rankings-top']), []);
});

test('ads.txt is plain seller lines plus configured extras', () => {
  const text = adsTxt({ ...on, adsTxtExtra: 'example.com, 123, RESELLER\n\n' });
  assert.ok(text.endsWith('\n'));
  assert.ok(!text.includes('<'));
  assert.match(text, /^example\.com, 123, RESELLER$/m);
  assert.match(adsTxt(parseAdsConfig({})), /No advertising system is authorized yet/);
});

test('consent defaults deny storage in the EEA, UK and Switzerland before any tag', () => {
  const script = consentDefaultsScript();
  for (const signal of ['ad_storage', 'ad_user_data', 'ad_personalization', 'analytics_storage']) {
    assert.match(script, new RegExp(`${signal}:'denied'`));
  }
  for (const region of ['DE', 'FR', 'GB', 'CH', 'NO', 'IS', 'LI']) assert.ok(script.includes(`"${region}"`), region);
  assert.ok(!script.includes('"US"'));
});
