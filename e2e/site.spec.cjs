const { test, expect } = require('@playwright/test');
const fs = require('node:fs');
const path = require('node:path');

const season = JSON.parse(
  fs.readFileSync(path.join(__dirname, '../public/assets/config/season.json'), 'utf8')
);
const start = new Date(season.start);
const end = new Date(season.end);
const csvHeader = fs.readFileSync(
  path.join(__dirname, '../public/assets/csv/results.csv'), 'utf8'
).split(/\r?\n/, 1)[0].split(',');

// These synthetic figures exist only in browser interception. Nothing is
// written to results.csv, Google Sheets, Gmail, or production services.
function syntheticCsv(overrides = {}) {
  const numbers = Object.fromEntries(csvHeader.map(k => [k, '0']));
  for (const key of csvHeader.filter(key => key.endsWith('_donor_names'))) {
    numbers[key] = '';
  }
  return csvHeader.join(',') + '\n' +
    csvHeader.map(key => numbers[key] = overrides[key] ?? numbers[key])
      .map(value => JSON.stringify(value)).join(',') + '\n';
}

async function mockCsv(page, overrides = {}) {
  const requests = [];
  await page.route(/\/assets\/csv\/results\.csv(?:\?|$)/, async route => {
    requests.push(route.request().url());
    await route.fulfill({
      status: 200,
      contentType: 'text/csv; charset=utf-8',
      body: syntheticCsv(overrides),
    });
  });
  return requests;
}

async function openReady(page) {
  await page.goto('/', { waitUntil: 'load' });
  // Checks that the actual browser ran jQuery, PapaParse and main.js, rather
  // than passing solely because the original HTML skeleton is present.
  await expect(page.locator('#season-dates')).toContainText('from ');
}

test('prelaunch page renders without requesting previous results', async ({ page }) => {
  await page.clock.setFixedTime(new Date(start.getTime() - 60_000));
  const requests = await mockCsv(page);
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));

  await openReady(page);
  await expect(page.locator('#countdown-text')).toHaveText('The Cup Starts In');
  await expect(page.locator('#hooTotal')).toHaveText('0');
  await expect(page.locator('#hokieTotal')).toHaveText('0');
  await expect(page.locator('.enable-during-contest').first()).toHaveCSS('pointer-events', 'none');
  await page.waitForTimeout(250);
  expect(requests).toHaveLength(0);
  expect(errors).toEqual([]);
});

test('active phase displays synthetic scores, winners and donor text', async ({ page }) => {
  await page.clock.setFixedTime(new Date(start.getTime() + 60_000));
  const requests = await mockCsv(page, {
    uva_total_amount: '1234.5',
    vt_total_amount: '1000',
    uva_most_individual_donors: '2',
    vt_most_individual_donors: '5',
    uva_donor_names: 'Synthetic Hoo',
    vt_donor_names: 'Synthetic Hokie',
  });

  await openReady(page);
  await expect(page.locator('#countdown-text')).toHaveText('The Cup Ends In');
  await expect(page.locator('#uva_total_amount')).toHaveText('1,234.50');
  await expect(page.locator('#vt_total_amount')).toHaveText('1,000.00');
  // The current HTML gives total raised 3 points and donors 2 points.
  // These expected points come from the fixture, not a financial transaction.
  await expect(page.locator('#hooTotal')).toHaveText('3');
  await expect(page.locator('#hokieTotal')).toHaveText('2');
  await expect(page.locator('#uva_donor_names')).toContainText('Synthetic Hoo');
  await expect(page.locator('#vt_donor_names')).toContainText('Synthetic Hokie');
  await expect(page.locator('.enable-during-contest').first()).not.toHaveCSS('pointer-events', 'none');
  expect(requests.length).toBeGreaterThanOrEqual(1);
});

test('existing tab switches from prelaunch to live at kickoff', async ({ page }) => {
  await page.clock.install({ time: new Date(start.getTime() - 1_500) });
  const requests = await mockCsv(page, { uva_total_amount: '1' });
  await openReady(page);
  expect(requests).toHaveLength(0);

  await page.clock.runFor(2_000);
  await expect(page.locator('#countdown-text')).toHaveText('The Cup Ends In');
  await expect(page.locator('#hooTotal')).toHaveText('3');
  expect(requests.length).toBeGreaterThanOrEqual(1);
});

test('ended phase loads final synthetic scores once and announces the winner', async ({ page }) => {
  await page.clock.install({ time: new Date(end.getTime() + 1_000) });
  const requests = await mockCsv(page, { uva_total_amount: '1' });
  await openReady(page);
  await expect(page.locator('#hooTotal')).toHaveText('3');
  await page.clock.runFor(6_000);
  await expect(page.locator('#countdown')).toContainText('Hoos win');
  expect(requests).toHaveLength(1);
  await expect(page.locator('.enable-during-contest').first()).toHaveCSS('pointer-events', 'none');
});

test('responsive layout shows countdown above team scores on phones', async ({ page }) => {
  await page.clock.setFixedTime(new Date(start.getTime() - 60_000));
  await openReady(page);
  const cards = page.locator('#overall-results > div > div > div');
  await expect(cards).toHaveCount(3);
  const left = await cards.nth(0).boundingBox();
  const center = await cards.nth(1).boundingBox();
  const right = await cards.nth(2).boundingBox();
  expect(left && center && right).toBeTruthy();

  if (page.viewportSize().width < 768) {
    expect(center.y).toBeLessThan(left.y);
    expect(left.y).toBeLessThan(right.y);
  } else {
    expect(left.x).toBeLessThan(center.x);
    expect(center.x).toBeLessThan(right.x);
  }
  const overflow = await page.evaluate(() => ({
    scroll: document.documentElement.scrollWidth,
    view: document.documentElement.clientWidth,
  }));
  expect(overflow.scroll).toBeLessThanOrEqual(overflow.view + 2);
});

test('local images load and public donation buttons remain external', async ({ page }) => {
  await page.clock.setFixedTime(new Date(start.getTime() - 60_000));
  await openReady(page);
  const images = page.locator('img[src^="assets/"]');
  expect(await images.count()).toBeGreaterThan(0);
  const failed = await images.evaluateAll(imgs =>
    imgs.filter(img => !img.complete || img.naturalWidth === 0)
      .map(img => img.getAttribute('src')));
  expect(failed).toEqual([]);

  const donationLinks = page.getByRole('link', { name: /donate to the (hoos|hokies)/i });
  await expect(donationLinks).toHaveCount(2);
  for (const href of await donationLinks.evaluateAll(links => links.map(link => link.href))) {
    expect(new URL(href).hostname).toBe('secure.lglforms.com');
  }
  // Never click a donation link, submit a form, or navigate off localhost.
  await expect(page).toHaveURL(/^http:\/\/127\.0\.0\.1:8765\//);
});
