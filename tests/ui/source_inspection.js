'use strict';
const {chromium} = require('../visual/node_modules/playwright');

(async () => {
  const browser = await chromium.launch({
    headless: true, executablePath: process.env.CHROMIUM_PATH,
    args: ['--no-sandbox', '--disable-dev-shm-usage']
  });
  try {
    const page = await browser.newPage(), errors = [];
    page.on('pageerror', e => errors.push(e.message));
    await page.goto(process.argv[2]);
    await page.waitForFunction(() => document.documentElement.dataset.ready === 'true');
    await page.click('nav button[data-page="Sources & Collection"]');
    await page.waitForSelector('.retained-source-inspection [data-source-preview]', {
      timeout: 20000
    });
    const area = page.locator('.retained-source-inspection');
    const initial = await area.textContent();
    if (!initial.includes('Local source revisions') ||
        !initial.includes('Source-specific watchlist') ||
        !initial.includes('Synthetic retained source observation')) {
      throw Error('Native source registry/revision/queue parity did not render');
    }
    await page.locator('[data-source-preview]').first().click();
    await page.waitForSelector('#action-dialog[open]');
    const evidence = await page.locator('#action-content').textContent();
    if (!evidence.includes('phase8:browser:source') ||
        !evidence.includes('normalized_source_sha256')) {
      throw Error('Exact retained evidence is not inspectable');
    }
    await page.click('#action-close');
    await page.locator('[data-parcel-review]').first().click();
    await page.waitForSelector('#action-dialog[open]');
    const parcel = await page.locator('#action-content').textContent();
    if (!parcel.includes('phase8:browser:source') ||
        !parcel.includes('source_apn')) {
      throw Error('Source-specific parcel candidates were not retained');
    }
    await page.click('#action-close');
    await page.locator('[data-history-mode="entities"]').click();
    await page.waitForSelector('[data-historical-entity]');
    const entityText = await page.locator('#retained-history-results').textContent();
    if (!entityText.includes('phase8:browser:entity') ||
        !entityText.includes('Synthetic Contractor')) {
      throw Error('Retained entity-key index not inspectable');
    }
    await page.locator('[data-historical-entity]').first().click();
    await page.waitForSelector('#action-dialog[open]');
    const neighborhood = await page.locator('#action-content').textContent();
    if (!neighborhood.includes('phase8:browser:source')) {
      throw Error('Exact source-key co-occurrence did not retain source evidence');
    }
    await page.click('#action-close');
    await page.locator('[data-history-mode="timeline"]').click();
    await page.waitForFunction(() => document.querySelector('#retained-history-results')?.textContent.includes('ceqa_posted'));
    const chronology = await page.locator('#retained-history-results').textContent();
    if (!chronology.includes('2026-10-13') || !chronology.includes('ceqa_received')) {
      throw Error('Recorded original CEQA timeline missing');
    }
    await page.locator('[data-history-mode="footprint"]').click();
    await page.waitForFunction(() => document.querySelector('#retained-history-results')?.textContent.includes('33.95'));
    const footprint = await page.locator('#retained-history-results').textContent();
    if (!footprint.includes('-117.36') ||
        !(await page.locator('#retained-history-export').isVisible())) {
      throw Error('Original geocoded evidence not inspectable/exportable');
    }
    await page.click('nav button[data-page="Bid Studio"]');
    await page.waitForSelector('.retained-source-inspection');
    if (!(await page.locator('.retained-source-inspection').textContent())
      .includes('Preserved workflow / outcome records')) {
      throw Error('Native workflow comparison is absent');
    }
    await page.click('nav button[data-page="Royalty Ledger"]');
    await page.waitForFunction(() => {
      const panel = document.querySelector('.retained-source-inspection');
      return panel && !panel.querySelector('[role="status"]');
    }, {timeout: 20000});
    const resultText = await page.locator('.retained-source-inspection').textContent();
    if (!resultText.includes('Legacy records are displayed separately')) {
      throw Error('Native result comparison is absent: ' + resultText.slice(0, 500));
    }
    if (errors.length) throw Error(errors.join('; '));
    console.log('Phase 8 native retained-source and historical-commercial read parity: PASS');
  } finally {
    await browser.close();
  }
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
