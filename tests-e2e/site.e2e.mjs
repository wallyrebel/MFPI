// Browser acceptance tests for rankings workflows, ad placement/eligibility and
// consent plumbing. Google's scripts are stubbed: no live ad or CMP is loaded,
// and nothing is ever clicked on an ad.
//
//   BASE=http://localhost:4321 MODE=ads node tests-e2e/site.e2e.mjs   # build made with test ad env
//   BASE=http://localhost:4321 MODE=off node tests-e2e/site.e2e.mjs   # default production build
import { createRequire } from 'node:module';
import assert from 'node:assert/strict';

const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const BASE = process.env.BASE || 'http://localhost:4321';
const MODE = process.env.MODE || 'off';
const results = [];

async function check(name, fn) {
  try { await fn(); results.push(['PASS', name]); } catch (error) { results.push(['FAIL', name, error.message.split('\n')[0]]); }
}

const STUB_FILLED = `window.adsbygoogle=window.adsbygoogle||[];(function(){function fill(){document.querySelectorAll('ins.adsbygoogle:not([data-ad-status])').forEach(function(i){i.setAttribute('data-ad-status','filled');i.innerHTML='<div style="width:300px;height:250px;background:#ddd;margin:auto">test creative</div>';});}var p=window.adsbygoogle.push.bind(window.adsbygoogle);window.adsbygoogle.push=function(x){p(x);fill();};fill();})();`;
const STUB_UNFILLED = `window.adsbygoogle=window.adsbygoogle||[];(function(){function mark(){document.querySelectorAll('ins.adsbygoogle:not([data-ad-status])').forEach(function(i){i.setAttribute('data-ad-status','unfilled');});}var p=window.adsbygoogle.push.bind(window.adsbygoogle);window.adsbygoogle.push=function(x){p(x);mark();};mark();})();`;
const STUB_CMP = `window.googlefc=window.googlefc||{};window.googlefc.callbackQueue=window.googlefc.callbackQueue||[];window.googlefc.showRevocationMessage=function(){window.__revocationShown=true};var q=window.googlefc.callbackQueue;window.googlefc.callbackQueue={push:function(f){f()}};q.forEach(function(f){f()});`;

async function page(browser, path, { ad = 'filled', viewport = { width: 1366, height: 900 } } = {}) {
  const context = await browser.newContext({ viewport });
  const tab = await context.newPage();
  const requests = [];
  const errors = [];
  tab.on('pageerror', (error) => errors.push(error.message));
  await tab.route(/googletagmanager\.com|google-analytics\.com/, (route) => route.fulfill({ body: '', contentType: 'text/javascript' }));
  await tab.route(/pagead2\.googlesyndication\.com/, (route) => {
    requests.push(route.request().url());
    if (ad === 'blocked') return route.abort();
    return route.fulfill({ body: ad === 'unfilled' ? STUB_UNFILLED : STUB_FILLED, contentType: 'text/javascript' });
  });
  await tab.route(/fundingchoicesmessages\.google\.com/, (route) => { requests.push(route.request().url()); return route.fulfill({ body: STUB_CMP, contentType: 'text/javascript' }); });
  const response = await tab.goto(BASE + path, { waitUntil: 'networkidle' });
  return { tab, context, requests, errors, status: response.status() };
}

async function rankingsWork(tab) {
  const rows = tab.locator('.ranking-entry');
  assert.ok(await rows.count() > 200, 'statewide table rendered');
  await tab.getByRole('button', { name: '7A', exact: true }).click();
  assert.equal(await rows.count(), 25, '7A filter');
  await tab.getByRole('button', { name: 'Overall', exact: true }).click();
  await tab.locator('.sort-control select').selectOption('team');
  const first = await rows.first().locator('.team-cell a').textContent();
  assert.match(first, /^Aberdeen/, 'team-name sort');
  await tab.locator('.sort-control select').selectOption('rank');
  await rows.first().locator('summary').click();
  assert.ok(await rows.first().locator('.team-details').isVisible(), 'row expands');
}

const browser = await chromium.launch();

if (MODE === 'ads') {
  await check('rankings: two labelled slots, outside rows and controls; rankings still work', async () => {
    const { tab, errors, context } = await page(browser, '/');
    const slots = tab.locator('.ad-slot');
    assert.equal(await slots.count(), 2);
    for (const label of await slots.locator('.ad-label').allTextContents()) assert.equal(label, 'Advertisement');
    assert.equal(await tab.locator('.ranking-entry .ad-slot, .class-tabs .ad-slot, .rankings-title-row .ad-slot, nav .ad-slot').count(), 0);
    const top = await slots.first().boundingBox();
    const controls = await tab.locator('.rankings-title-row').boundingBox();
    assert.ok(controls.y - (top.y + top.height) > 150, 'top slot well separated from filters and sort');
    await rankingsWork(tab);
    assert.deepEqual(errors, []);
    await context.close();
  });
  await check('unfilled slots collapse instead of leaving empty space', async () => {
    const { tab, context } = await page(browser, '/', { ad: 'unfilled' });
    for (const box of await tab.locator('.ad-slot').evaluateAll((els) => els.map((el) => el.getBoundingClientRect().height))) assert.equal(box, 0);
    await context.close();
  });
  await check('blocked ad script: page and rankings still work, no errors, slots collapse', async () => {
    const { tab, errors, context } = await page(browser, '/', { ad: 'blocked' });
    await rankingsWork(tab);
    await tab.waitForTimeout(5500);
    for (const box of await tab.locator('.ad-slot').evaluateAll((els) => els.map((el) => el.getBoundingClientRect().height))) assert.equal(box, 0);
    assert.deepEqual(errors, []);
    await context.close();
  });
  await check('consent defaults (denied in EEA/UK/CH) precede analytics config', async () => {
    const { tab, context } = await page(browser, '/');
    const layer = await tab.evaluate(() => window.dataLayer.map((entry) => Array.from(entry)));
    const consent = layer.findIndex((entry) => entry[0] === 'consent' && entry[1] === 'default');
    const config = layer.findIndex((entry) => entry[0] === 'config');
    assert.ok(consent >= 0 && consent < config, 'consent default before config');
    assert.equal(layer[consent][2].ad_storage, 'denied');
    assert.ok(layer[consent][2].region.includes('GB'));
    await context.close();
  });
  await check('privacy choices link reopens the CMP (consent withdrawal)', async () => {
    const { tab, context } = await page(browser, '/privacy');
    await tab.getByRole('button', { name: 'Privacy and cookie settings' }).click();
    assert.equal(await tab.evaluate(() => window.__revocationShown), true);
    await context.close();
  });
  for (const path of ['/privacy', '/contact', '/about', '/advertise', '/corrections', '/analysis', '/teams', '/team/cleveland-central', '/does-not-exist']) {
    await check(`no ad code on ${path} (CMP still present)`, async () => {
      const { tab, requests, context } = await page(browser, path);
      assert.equal(requests.filter((url) => url.includes('googlesyndication')).length, 0);
      assert.equal(await tab.locator('.ad-slot, ins.adsbygoogle').count(), 0);
      assert.ok(requests.some((url) => url.includes('fundingchoicesmessages')), 'CMP loaded');
      await context.close();
    });
  }
  await check('team page with results: at most two slots, after complete sections', async () => {
    const { tab, context } = await page(browser, '/team/tupelo');
    assert.equal(await tab.locator('.ad-slot').count(), 2);
    assert.equal(await tab.locator('.mf-team-hero .ad-slot, .run-card .ad-slot, .table-scroll .ad-slot, .component-grid .ad-slot').count(), 0);
    await context.close();
  });
  await check('verification meta tag and ads.txt use the configured ID', async () => {
    const { tab, context } = await page(browser, '/about');
    assert.equal(await tab.locator('meta[name="google-adsense-account"]').getAttribute('content'), 'ca-pub-0000000000000000');
    const text = await (await tab.request.get(BASE + '/ads.txt')).text();
    assert.match(text, /^google\.com, pub-0000000000000000, DIRECT, f08c47fec0942fa0$/m);
    await context.close();
  });
} else {
  for (const path of ['/', '/team/tupelo', '/team/cleveland-central', '/privacy', '/analysis', '/archive/2026/week-04']) {
    await check(`ads disabled: no ad or CMP code on ${path}`, async () => {
      const { tab, requests, status, errors, context } = await page(browser, path);
      assert.equal(status, 200);
      assert.equal(requests.length, 0);
      assert.equal(await tab.locator('.ad-slot, meta[name="google-adsense-account"]').count(), 0);
      assert.deepEqual(errors, []);
      await context.close();
    });
  }
  await check('rankings workflows with ads disabled', async () => {
    const { tab, context } = await page(browser, '/');
    await rankingsWork(tab);
    await context.close();
  });
  await check('ads.txt is plain text, not the HTML fallback', async () => {
    const { tab, context } = await page(browser, '/about');
    const response = await tab.request.get(BASE + '/ads.txt');
    assert.match(response.headers()['content-type'], /^text\/plain/);
    assert.ok(!(await response.text()).includes('<html'));
    await context.close();
  });
  await check('404 page has navigation and a 404 status', async () => {
    const { tab, status, context } = await page(browser, '/no-such-page');
    assert.equal(status, 404);
    assert.ok(await tab.locator('header nav').isVisible());
    await context.close();
  });
  for (const path of ['/', '/team/tupelo', '/team/cleveland-central', '/methodology', '/archive/2026/week-04', '/corrections']) {
    await check(`mobile ${path}: no horizontal page scroll, nav reachable`, async () => {
      const { tab, context } = await page(browser, path, { viewport: { width: 390, height: 844 } });
      assert.equal(await tab.evaluate(() => document.documentElement.scrollWidth > window.innerWidth), false);
      assert.ok(await tab.locator('header .mf-nav a[href="/teams"]').isVisible(), 'nav visible on mobile');
      await context.close();
    });
  }
  await check('keyboard: class tabs and sort are reachable and labelled', async () => {
    const { tab, context } = await page(browser, '/');
    assert.equal(await tab.locator('.class-tabs button[aria-pressed="true"]').count(), 1);
    assert.ok(await tab.getByLabel('Sort').isVisible());
    await tab.getByRole('button', { name: '1A', exact: true }).focus();
    await tab.keyboard.press('Enter');
    assert.equal(await tab.locator('.ranking-entry').count(), 34);
    await context.close();
  });
}

await browser.close();
for (const [status, name, detail] of results) console.log(`${status}  ${name}${detail ? `  — ${detail}` : ''}`);
const failed = results.filter(([status]) => status === 'FAIL').length;
console.log(`\n${results.length - failed} passed, ${failed} failed (${MODE})`);
process.exit(failed ? 1 : 0);
