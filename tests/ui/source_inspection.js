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
    const sourceRow = page.locator('.retained-source-inspection tr')
      .filter({hasText: 'Synthetic retained source observation'}).first();
    await sourceRow.locator('[data-source-preview]').click();
    await page.waitForSelector('#action-dialog[open]');
    const evidence = await page.locator('#action-content').textContent();
    if (!evidence.includes('phase8:browser:source') ||
        !evidence.includes('normalized_source_sha256')) {
      throw Error('Exact retained evidence is not inspectable');
    }
    await page.click('#action-close');
    await sourceRow.locator('[data-source-lineage]').click();
    await page.waitForFunction(() =>
      document.querySelector('#action-content')?.textContent
        .includes('"schema_version": "constructionsight.original-workflow-candidate-lineage/v1"'));
    const lineage = await page.locator('#action-content').textContent();
    if (!lineage.includes('"matching_workflow_total": 1') ||
        !lineage.includes('"review_package_status": "ready"') ||
        !lineage.includes('"identity_association_verified": false') ||
        !lineage.includes('"commercial_authority_granted": false') ||
        !lineage.includes('"history_integrity_validated": true') ||
        !lineage.includes('"revision_count": 2') ||
        !lineage.includes('"gross_value_minor": 123456') ||
        !lineage.includes('"share_rate_ppm": 100000') ||
        !lineage.includes('"calculated_share_minor": 12346') ||
        !lineage.includes('"payment_received_verified": false')) {
      throw Error('Original workflow, outcome revision and royalty cautions lost lineage');
    }
    await page.click('#action-close');
    await sourceRow.locator('[data-source-reconcile]').click();
    await page.waitForSelector('#source-reconcile-queue');
    const reconciliation = await page.locator('#action-content').textContent();
    if (!reconciliation.includes('not_in_native_store') ||
        !reconciliation.includes('"replay_eligible": true') ||
        !reconciliation.includes('phase8:browser:source')) {
      throw Error('Original exact source did not present an unverified native reconciliation');
    }
    await page.locator('#source-reconcile-reason')
      .fill('Reviewed exact retained source and confirm native worker queue only.');
    await page.locator('#source-reconcile-confirm').check();
    await page.locator('#source-reconcile-queue').click();
    await page.waitForSelector('#source-reconcile-audit');
    const queued = await page.locator('#action-content').textContent();
    if (!queued.includes('"outreach_authorized": false') ||
        !queued.includes('"bid_authorized": false')) {
      throw Error('Native source replay queue lacks preserved no-commercial-effects guards');
    }
    await page.locator('#source-reconcile-audit').click();
    await page.waitForFunction(() =>
      document.querySelector('#action-content')?.textContent
        .includes('"schema_version": "constructionsight.original-replay-audit/v1"'));
    const audit = await page.locator('#action-content').textContent();
    if (!audit.includes('original-replay-audit/v1') ||
        !audit.includes('Reviewed exact retained source and confirm native worker') ||
        !audit.includes('"commercial_authority_granted": false')) {
      throw Error('Exact reviewed replay reason was not retained in auditable worker state');
    }
    await page.click('#action-close');
    await sourceRow.locator('[data-source-reconcile]').click();
    await page.waitForSelector('#source-reconcile-queue');
    await page.click('#action-close');
    await sourceRow.locator('[data-parcel-review]').click();
    await page.waitForSelector('#action-dialog[open]');
    const parcel = await page.locator('#action-content').textContent();
    if (!parcel.includes('phase8:browser:source') ||
        !parcel.includes('source_apn')) {
      throw Error('Source-specific parcel candidates were not retained');
    }
    await page.click('#action-close');
    await sourceRow.locator('[data-source-watch]').click();
    await page.waitForSelector('#retained-source-watchlist [data-source-unwatch]');
    const activeSourceWatch = await page.locator('#retained-source-watchlist').textContent();
    if (!activeSourceWatch.includes('Synthetic retained source observation') ||
        !activeSourceWatch.includes('1 active source watches') ||
        !activeSourceWatch.includes('remote source polling: disabled')) {
      throw Error('Original source-specific watch was not persisted in native workspace');
    }
    await page.locator('#retained-source-watchlist [data-source-unwatch]').first().click();
    await page.waitForFunction(() =>
      document.querySelector('#retained-source-watchlist')?.textContent
        .includes('0 active source watches'));
    await page.waitForSelector('#retained-capture-inbox [data-capture-candidate]');
    const captureText = await page.locator('#retained-capture-inbox').textContent();
    if (!captureText.includes('2026012345') ||
        !captureText.includes('2026030377') ||
        !captureText.includes('Original CEQA capture & ingestion')) {
      throw Error('Native exact capture and ingestion artifacts not retained');
    }
    await page.locator('#retained-capture-inbox [data-capture-candidate]').first().click();
    await page.waitForSelector('#action-dialog[open]');
    const captureDetail = await page.locator('#action-content').textContent();
    if (!captureDetail.includes('candidate_only') ||
        !captureDetail.includes('2026012345')) {
      throw Error('Original capture candidate evidence is not inspectable');
    }
    await page.click('#action-close');
    await page.waitForSelector('#original-export-generate');
    await page.locator('#original-export-confirm').check();
    await page.locator('#original-export-generate').click();
    await page.waitForSelector('#original-export-download');
    const exportReport = await page.locator('#original-export-result').textContent();
    if (!exportReport.includes('Verified original operator ZIP is ready') ||
        !exportReport.includes('No commercial action was authorized')) {
      throw Error('Original verified CEQAnet package/archive export is unavailable');
    }
    const downloadEvent = page.waitForEvent('download');
    await page.locator('#original-export-download').click();
    const operatorArchive = await downloadEvent;
    if (operatorArchive.suggestedFilename() !== 'ceqanet-operator-export.zip') {
      throw Error('Original CEQAnet ZIP download filename differs from validated export');
    }
    await page.waitForSelector('#source-smarts-change-results [data-smarts-parcel]');
    const originalSmarts = await page.locator('#retained-smarts-history').textContent();
    if (!originalSmarts.includes('smarts:facility:Riverside:wdid:8 33C101') ||
        !originalSmarts.includes('candidate changes') ||
        originalSmarts.includes('secret@example.test')) {
      throw Error('Private SMARTS changes or source privacy missing in native panel');
    }
    await page.locator('#source-smarts-change-results [data-smarts-parcel]').first().click();
    await page.waitForSelector('#action-dialog[open]');
    const smartsParcel = await page.locator('#action-content').textContent();
    if (!smartsParcel.includes('parcel:browser:smarts') ||
        !smartsParcel.includes('parcel_identity_verified') ||
        !smartsParcel.includes('false') || smartsParcel.includes('secret@example.test')) {
      throw Error('Verified current SMARTS snapshot exact parcel candidate unavailable');
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
    await page.waitForSelector('#original-outreach-form');
    const originalBidHistory = page.locator('.retained-source-inspection').first();
    const firstWorkflow = await originalBidHistory.locator('[data-original-record]').first()
      .locator('xpath=ancestor::tr').textContent();
    await originalBidHistory.locator('[data-original-next]').click();
    await page.waitForFunction(() =>
      document.querySelector('.retained-source-inspection')?.textContent.includes('page offset 25'));
    if (await originalBidHistory.locator('[data-original-record]').count() !== 3 ||
        await originalBidHistory.locator('[data-original-next]').isEnabled()) {
      throw Error('Original workflow pagination did not expose all retained records');
    }
    await originalBidHistory.locator('[data-original-record]').first().click();
    await page.waitForSelector('#action-dialog[open]');
    if (!(await page.locator('#action-content').textContent())
      .includes('synthetic:historical-page:23')) {
      throw Error('Original workflow second page did not open exact retained record');
    }
    await page.click('#action-close');
    await originalBidHistory.locator('[data-original-previous]').click();
    await page.waitForFunction(() =>
      document.querySelector('.retained-source-inspection')?.textContent.includes('page offset 0'));
    if (!(await originalBidHistory.locator('[data-original-record]').first()
      .locator('xpath=ancestor::tr').textContent()).includes(firstWorkflow.trim()) ||
        !(await page.locator('#original-outreach-form').count())) {
      throw Error('Original workflow first-page and preview binding did not recover');
    }
    if (!(await page.locator('[name="original-workflow"]').inputValue())
      .startsWith('lead-workflow:')) {
      throw Error('Retained commercial preview did not bind a persisted workflow');
    }
    const outreachFields = {
      destination: 'estimator@example-contractor.test',
      business_role: 'estimating department',
      source_name: 'Synthetic reviewed business website',
      source_reference: 'https://example-contractor.test/contact',
      contact_review_basis: 'Reviewed exact business source for synthetic fixture.',
      subject: 'Internal construction site security introduction',
      body: 'Draft text for human review; not sent.'
    };
    for (const [name, value] of Object.entries(outreachFields)) {
      await page.locator('#original-outreach-form [name="' + name + '"]').fill(value);
    }
    await page.locator('#original-outreach-form button[type="submit"]').click();
    await page.waitForSelector('#action-dialog[open]');
    const outreachPreview = await page.locator('#action-content').textContent();
    if (!outreachPreview.includes('"external_send_authorized": false') ||
        !outreachPreview.includes('"outreach_sent": false')) {
      throw Error('Original governed no-send outreach preview was not upheld');
    }
    await page.click('#action-close');
    const requestFields = {
      requester_business_name: 'Synthetic Contractor LLC',
      requester_business_role: 'estimating department',
      request_source_name: 'Retained synthetic business email',
      request_source_reference: 'message:fixture:request',
      request_review_basis: 'Reviewed explicit written bid request.',
      request_observed_at: '2026-10-08T10:00:00+00:00',
      request_text: 'Please quote construction site night security.',
      scope_summary: 'Night guard services for the reviewed site.'
    };
    for (const [name, value] of Object.entries(requestFields)) {
      await page.locator('#original-request-form [name="' + name + '"]').fill(value);
    }
    await page.locator('#original-request-form button[type="submit"]').click();
    await page.waitForSelector('#action-dialog[open]');
    const requestPreview = await page.locator('#action-content').textContent();
    if (!requestPreview.includes('"pricing_authorized": false') ||
        !requestPreview.includes('"bid_submitted": false')) {
      throw Error('Original guarded bid-request evidence unavailable');
    }
    await page.click('#action-close');
    await page.locator('#original-pricing-form [name="line_key"]').fill('night-guard');
    await page.locator('#original-pricing-form [name="description"]').fill('Night guard');
    await page.locator('#original-pricing-form [name="pricing_basis"]').fill('Manual');
    await page.locator('#original-pricing-form [name="amount"]').fill('125.50');
    await page.locator('#original-pricing-form [name="validity_note"]').fill('Internal approval needed.');
    await page.locator('#original-pricing-form button[type="submit"]').click();
    await page.waitForSelector('#action-dialog[open]');
    const pricingPreview = await page.locator('#action-content').textContent();
    if (!pricingPreview.includes('"subtotal_minor": 12550') ||
        !pricingPreview.includes('"bid_submission_authorized": false')) {
      throw Error('Original manually reviewed exact-money pricing is absent');
    }
    await page.click('#action-close');
    await page.locator('#original-proposal-form [name="proposal_title"]')
      .fill('Internal synthetic security proposal');
    await page.locator('#original-proposal-form [name="cover_note"]')
      .fill('For internal review only.');
    await page.locator('#original-proposal-form button[type="submit"]').click();
    await page.waitForSelector('#action-dialog[open]');
    const proposalPreview = await page.locator('#action-content').textContent();
    if (!proposalPreview.includes('"bid_submission_authorized": false') ||
        !proposalPreview.includes('"commercial_terms_authorized": false')) {
      throw Error('Original internal proposal draft was incorrectly authorized');
    }
    await page.click('#action-close');
    await page.click('nav button[data-page="Royalty Ledger"]');
    await page.waitForFunction(() => {
      const panel = document.querySelector('.retained-source-inspection');
      return panel && !panel.querySelector('[role="status"]');
    }, {timeout: 20000});
    const resultText = await page.locator('.retained-source-inspection').textContent();
    if (!resultText.includes('Legacy records are displayed separately')) {
      throw Error('Native result comparison is absent: ' + resultText.slice(0, 500));
    }
    await page.waitForSelector('.retained-source-inspection [data-original-attribution]');
    const originalResultHistory = page.locator('.retained-source-inspection').first();
    await originalResultHistory.locator('[data-original-next]').click();
    await page.waitForFunction(() =>
      document.querySelector('.retained-source-inspection')?.textContent.includes('page offset 25'));
    if (await originalResultHistory.locator('[data-original-record]').count() !== 3 ||
        await originalResultHistory.locator('[data-original-next]').isEnabled()) {
      throw Error('Original corrected result ledger pagination is incomplete');
    }
    await originalResultHistory.locator('[data-original-record]').first().click();
    await page.waitForSelector('#action-dialog[open]');
    if (!(await page.locator('#action-content').textContent())
      .includes('lead-review:phase8:pagination:23')) {
      throw Error('Original result second page did not open retained history');
    }
    await page.click('#action-close');
    await originalResultHistory.locator('[data-original-previous]').click();
    await page.waitForFunction(() =>
      document.querySelector('.retained-source-inspection')?.textContent.includes('page offset 0'));
    await page.locator('.retained-source-inspection [data-original-attribution]')
      .first().click();
    await page.waitForSelector('#original-workflow-attribution-form');
    await page.locator('#original-workflow-attribution-form [name="record_id"]')
      .fill('phase8:browser:dossier');
    await page.locator('#original-workflow-attribution-form button[type="submit"]')
      .click();
    await page.waitForFunction(() =>
      document.querySelector('#original-workflow-attribution-result')?.textContent
        .includes('Exact attribution rejected'));
    if ((await page.locator('#original-workflow-attribution-result').textContent())
      .includes('canonical_investigation_id')) {
      throw Error('Unrelated original workflow was granted a native investigation');
    }
    await page.locator('#original-workflow-attribution-form [name="record_id"]')
      .fill('phase8:browser:source');
    await page.locator('#original-workflow-attribution-form button[type="submit"]')
      .click();
    await page.waitForFunction(() =>
      document.querySelector('#original-workflow-attribution-result')?.textContent
        .includes('original-workflow-source-attribution/v1'));
    const exactUnretained = await page.locator('#original-workflow-attribution-result')
      .textContent();
    if (!exactUnretained.includes('"source_identity_match": true') ||
        !exactUnretained.includes('"current_native_observation_matches_original": false') ||
        !exactUnretained.includes('"payment_received_verified": false') ||
        await page.locator('#original-attribution-open-native').count()) {
      throw Error('Unretained source was incorrectly linked to a native investigation');
    }
    await page.click('#action-close');
    await page.locator('.retained-source-inspection [data-original-attribution]')
      .nth(1).click();
    await page.waitForSelector('#original-workflow-attribution-form');
    await page.locator('#original-workflow-attribution-form [name="record_id"]')
      .fill('phase8:browser:dossier');
    await page.locator('#original-workflow-attribution-form button[type="submit"]')
      .click();
    await page.waitForSelector('#original-attribution-open-native');
    const matchedHistory = await page.locator('#original-workflow-attribution-result')
      .textContent();
    if (!matchedHistory.includes('"current_native_observation_matches_original": true') ||
        !matchedHistory.includes('"history_integrity_validated": true') ||
        !matchedHistory.includes('"event_count": 2') ||
        !matchedHistory.includes('Synthetic history: original operator moved') ||
        !matchedHistory.includes('"gross_value_minor": 250000') ||
        !matchedHistory.includes('"calculated_share_minor": 20000') ||
        !matchedHistory.includes('"royalty_entitlement_verified": false') ||
        !matchedHistory.includes('"bid_authorized": false')) {
      throw Error('Exact workflow-to-native source attribution omitted integrity safeguards');
    }
    await page.locator('#original-attribution-open-native').click();
    await page.waitForFunction(() =>
      document.querySelector('#action-content')?.textContent
        .includes('Exact original commercial lineage'));
    if (!(await page.locator('#action-content').textContent())
      .includes('phase8:browser:dossier')) {
      throw Error('Exact original Royalty Ledger workflow did not open canonical dossier');
    }
    await page.click('#action-close');
    await page.click('nav button[data-page="Project Intelligence"]');
    await page.waitForSelector('[data-shared-investigations] button[data-investigation-id]');
    await page.locator('[data-shared-investigations] button[data-investigation-id]')
      .first().click();
    await page.waitForSelector('#action-dialog[open] [data-dossier-original-source]');
    const nativeDossier = await page.locator('#action-content').textContent();
    if (!nativeDossier.includes('phase8:browser:dossier') ||
        !nativeDossier.includes('Exact original commercial lineage')) {
      throw Error('Canonical investigation dossier omits exact preserved original source');
    }
    await page.locator('[data-dossier-original-source]').first().click();
    await page.waitForFunction(() =>
      document.querySelector('#native-original-lineage-detail')?.textContent
        .includes('original-workflow-candidate-lineage/v1'));
    const commercialContext = await page.locator('#native-original-lineage-detail')
      .textContent();
    if (!commercialContext.includes('"matching_workflow_total": 1') ||
        !commercialContext.includes('"history_integrity_validated": true') ||
        !commercialContext.includes('"event_count": 2') ||
        !commercialContext.includes('Synthetic history: original operator moved') ||
        !commercialContext.includes('"gross_value_minor": 250000') ||
        !commercialContext.includes('"share_rate_ppm": 80000') ||
        !commercialContext.includes('"calculated_share_minor": 20000') ||
        !commercialContext.includes('"payment_received_verified": false') ||
        !commercialContext.includes('"share_entitlement_verified": false')) {
      throw Error('Native dossier incorrectly promotes or omits preserved financial lineage');
    }
    await page.locator('#export-native-source-lineage').click();
    await page.click('#action-close');
    if (errors.length) throw Error(errors.join('; '));
    console.log('Phase 8 native retained-source and historical-commercial read parity: PASS');
  } finally {
    await browser.close();
  }
})().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
