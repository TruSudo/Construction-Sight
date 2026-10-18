'use strict';
const {chromium} = require('../visual/node_modules/playwright');
const {spawnSync} = require('node:child_process');
const {createHash} = require('node:crypto');
const {readFileSync} = require('node:fs');
const {resolve} = require('node:path');

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
        !initial.includes('Original source attribution aliases: 1 retained mappings · applied: yes') ||
        !initial.includes('Synthetic retained portal') ||
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
    // Complete a separate mixed-source page through the unchanged worker in a
    // fresh process. The earlier single-source review remains independently tested.
    await page.click('nav button[data-page="Sources & Collection"]');
    await page.waitForSelector('#retained-source-filters');
    await page.locator('#retained-source-filters input[name="q"]').fill('scoped migration');
    await page.locator('#retained-source-filters button[type="submit"]').click();
    await page.waitForFunction(() =>
      document.querySelector('#retained-source-queue')?.textContent
        .includes('2 retained source observations match'));
    await page.locator('#retained-source-scope-review').click();
    await page.waitForSelector('#source-scope-queue');
    const scopedPlan = await page.locator('#action-content').textContent();
    if (!scopedPlan.includes('missing: 2') ||
        !scopedPlan.includes('phase8:browser:batch:ceqa') ||
        !scopedPlan.includes('phase8:browser:batch:permit') ||
        !scopedPlan.includes('Exact page digest')) {
      throw Error('Scoped mixed-source review does not bind the exact filtered page');
    }
    let scopePosts = 0;
    page.on('request', request => {
      if (request.method() === 'POST' &&
          new URL(request.url()).pathname === '/api/source-reconciliation-scope-queue') {
        scopePosts += 1;
      }
    });
    await page.locator('#source-scope-queue').click();
    // The reason/confirmation guard is synchronous; the review must stay open.
    if (scopePosts || !await page.locator('#source-scope-queue').isVisible()) {
      throw Error('Unconfirmed source page was submitted');
    }
    const reviewReason = 'Reviewed the exact mixed-source page for retained worker replay only.';
    await page.locator('#source-scope-reason').fill(reviewReason);
    await page.locator('#source-scope-confirm').check();
    const queueResponse = page.waitForResponse(response =>
      new URL(response.url()).pathname === '/api/source-reconciliation-scope-queue' &&
      response.request().method() === 'POST');
    await page.locator('#source-scope-queue').click();
    const batchReceipt = await (await queueResponse).json();
    await page.waitForSelector('[data-scoped-replay-audit]');
    if (scopePosts !== 1 || batchReceipt.queued_count !== 2 ||
        await page.locator('[data-scoped-replay-audit]').count() !== 2 ||
        !batchReceipt.batch_approval_audit_event_id) {
      throw Error('Exact source page did not produce one atomic, auditable approval');
    }
    await page.locator('[data-scoped-replay-audit]').first().click();
    await page.waitForFunction(() =>
      document.querySelector('#action-content')?.textContent
        .includes('original-replay-audit/v1'));
    const pendingAudit = await page.locator('#action-content').textContent();
    if (!pendingAudit.includes(reviewReason) || !pendingAudit.includes('"job_status": "queued"')) {
      throw Error('Scoped approval lost the operator reason or pending worker state');
    }
    await page.click('#action-close');
    const nativeDirectory = process.argv[3];
    if (!nativeDirectory) throw Error('Scoped browser test requires the isolated native data folder');
    const originalDatabase = resolve(nativeDirectory, '../operator-source.sqlite3');
    const originalDigest = () => createHash('sha256')
      .update(readFileSync(originalDatabase)).digest('hex');
    const beforeWorker = originalDigest();
    function runWorker() {
      const worker = spawnSync('python', ['-m', 'constructionsight.investigation_runtime',
        '--data-dir', nativeDirectory, 'run', '--max-jobs', '100'], {
        env: {...process.env, PYTHONPATH: 'src'}, encoding: 'utf8'
      });
      if (worker.status !== 0) throw Error('Retained worker failed: ' + worker.stderr);
      const result = JSON.parse(worker.stdout);
      if (result.failed_jobs) throw Error('Retained worker reported failed jobs');
      return result;
    }
    runWorker();
    if (runWorker().processed_jobs !== 0 || originalDigest() !== beforeWorker) {
      throw Error('Worker restart duplicated work or changed original source data');
    }
    for (const job of batchReceipt.jobs) {
      const completed = await page.request.get(new URL('/api/source-reconciliation-audit?' +
        new URLSearchParams({job: job.job_id}), process.argv[2]).href);
      const completedAudit = await completed.json();
      if (completedAudit.job_status !== 'completed' ||
          completedAudit.commercial_authority_granted !== false) {
        throw Error('Scoped source did not complete with preserved authority safeguards');
      }
    }
    await page.locator('#retained-source-scope-review').click();
    await page.waitForSelector('#source-scope-export');
    const completedPlan = await page.locator('#action-content').textContent();
    if (!completedPlan.includes('missing: 0') ||
        !completedPlan.includes('already retained: 2') ||
        await page.locator('#source-scope-queue').count()) {
      throw Error('Source-page rescan did not converge after independent worker processing');
    }
    await page.click('#action-close');
    await page.click('nav button[data-page="Project Intelligence"]');
    await page.waitForSelector('[data-investigation-search]');
    await page.locator('[data-investigation-search]').fill('scoped migration');
    await page.waitForFunction(() =>
      document.querySelectorAll('[data-shared-investigations] [data-investigation-id]').length === 2);
    const migratedIds = await page.locator('[data-shared-investigations] [data-investigation-id]')
      .evaluateAll(nodes => nodes.map(node => node.dataset.investigationId).sort());
    if (migratedIds[0] === migratedIds[1]) throw Error('Scoped replay merged distinct source identities');
    await page.locator('[data-shared-investigations] [data-investigation-id]').first().click();
    await page.waitForSelector('#export-investigation');
    const migratedDossier = await page.locator('#action-content').textContent();
    if (!migratedDossier.includes('phase8:browser:batch:') ||
        !migratedDossier.includes('commercial authority: No')) {
      throw Error('Migrated source is disconnected from the shared, unverified dossier');
    }
    await page.click('#action-close');
    await page.click('nav button[data-page="Evidence Chains"]');
    await page.waitForFunction(() =>
      document.querySelectorAll('[data-shared-investigations] [data-investigation-id]').length === 2);
    const evidenceIds = await page.locator('[data-shared-investigations] [data-investigation-id]')
      .evaluateAll(nodes => nodes.map(node => node.dataset.investigationId).sort());
    if (JSON.stringify(migratedIds) !== JSON.stringify(evidenceIds)) {
      throw Error('Scoped source replay disagrees across shared investigation views');
    }
    // An existing original record changes independently of the native engine.
    // This mutation belongs only to the isolated source fixture, not the worker.
    const watchedSource = {kind: 'ceqa', record_id: 'phase8:browser:batch:ceqa'};
    const watchCreated = await page.request.post(new URL(
      '/api/source-watchlist-action', process.argv[2]).href, {
      data: {action: 'add', ...watchedSource}, headers: {Origin: process.argv[2]}
    });
    if (!watchCreated.ok()) throw Error('Source notification watch setup failed');
    const priorNotices = await (await page.request.get(new URL(
      '/api/notifications', process.argv[2]).href)).json();
    await page.request.post(new URL('/api/notifications/read', process.argv[2]).href, {
      data: {ids: priorNotices.map(n => n.id)}, headers: {Origin: process.argv[2]}
    });
    await page.evaluate(() => refreshNotificationIndicator());
    await page.waitForFunction(() => document.querySelector('#unread-dot').hidden);
    const revise = spawnSync('python', ['-c', `
import sys
from datetime import timedelta
from sqlalchemy.orm import Session
from constructionsight.storage.database import create_database_engine
from constructionsight.storage.domain_store import CeqaStore
engine = create_database_engine('sqlite:///' + sys.argv[1])
with Session(engine) as session, session.begin():
    record = CeqaStore(session).get('phase8:browser:batch:ceqa')
    assert record is not None
    CeqaStore(session).upsert(record.model_copy(update={
        'title': 'Revised scoped migration source',
        'provenance': [item.model_copy(update={
            'captured_at': item.captured_at + timedelta(days=1)
        }) for item in record.provenance]
    }))
engine.dispose()
`, originalDatabase], {env: {...process.env, PYTHONPATH: 'src'}, encoding: 'utf8'});
    if (revise.status !== 0) throw Error('Isolated original source revision failed: ' + revise.stderr);
    const beforeRevisionWorker = originalDigest();
    // The normal background UI timer must discover the change without reload.
    await page.waitForFunction(() => !document.querySelector('#unread-dot').hidden,
      {timeout: 15000});
    await page.click('#notifications');
    await page.waitForSelector('[data-source-notice]');
    await page.locator('[data-source-notice]').filter({hasText: 'Revised scoped migration source'})
      .click();
    await page.waitForSelector('#source-notice-dossier');
    const sourceNotice = await page.locator('#action-content').textContent();
    if (!sourceNotice.includes('phase8:browser:batch:ceqa') ||
        !sourceNotice.includes('current_observation_disagrees_requires_review') ||
        originalDigest() !== beforeRevisionWorker) {
      throw Error('Source notice lost exact evidence/revision boundary or mutated originals');
    }
    await page.click('#source-notice-dossier');
    await page.waitForSelector('#export-investigation');
    if (!(await page.locator('#action-title').textContent()).includes(
      'Synthetic scoped migration source')) {
      throw Error('Source notice incorrectly approved the original revision');
    }
    await page.click('#action-close');
    await page.click('nav button[data-page="Sources & Collection"]');
    await page.waitForSelector('#retained-source-filters');
    await page.locator('#retained-source-filters input[name="q"]')
      .fill('Revised scoped migration source');
    await page.locator('#retained-source-filters button[type="submit"]').click();
    await page.waitForFunction(() =>
      document.querySelector('#retained-source-queue')?.textContent
        .includes('1 retained source observations match'));
    const revisedRow = page.locator('#retained-source-queue tr')
      .filter({hasText: 'Revised scoped migration source'});
    const revisionResponse = page.waitForResponse(response =>
      new URL(response.url()).pathname === '/api/source-reconciliation');
    await revisedRow.locator('[data-source-reconcile]').click();
    const revisionPreview = await (await revisionResponse).json();
    await page.waitForSelector('#source-reconcile-queue');
    if (!revisionPreview.revision_replay_eligible || revisionPreview.replay_eligible ||
        !(await page.locator('#source-reconcile-queue').textContent()).includes('reviewed source revision')) {
      throw Error('Changed original source did not require an explicit revision handoff');
    }
    const revisionIdentity = revisionPreview.canonical_investigation_id;
    await page.locator('#source-reconcile-open-current').click();
    await page.waitForSelector('#export-investigation');
    if (!(await page.locator('#action-title').textContent()).includes('Synthetic scoped migration source')) {
      throw Error('Original update changed the native dossier before reviewed worker processing');
    }
    await page.click('#action-close');
    await revisedRow.locator('[data-source-reconcile]').click();
    await page.waitForSelector('#source-reconcile-queue');
    await page.locator('#source-reconcile-reason')
      .fill('Reviewed the exact original revision against current retained native evidence.');
    await page.locator('#source-reconcile-confirm').check();
    let releaseRevision, markRevisionQueued;
    const deliverRevision = new Promise(resolve => { releaseRevision = resolve; });
    const originalRevisionQueued = new Promise(resolve => { markRevisionQueued = resolve; });
    await page.route('**/api/source-reconciliation-queue', async route => {
      const response = await route.fetch();
      markRevisionQueued();
      await deliverRevision;
      await route.fulfill({response});
    });
    const revisionQueued = page.waitForResponse(response =>
      new URL(response.url()).pathname === '/api/source-reconciliation-queue' &&
      response.request().method() === 'POST');
    await page.locator('#source-reconcile-queue').click();
    await originalRevisionQueued;
    await page.locator('#source-reconcile-open-current').click();
    await page.waitForSelector('#export-investigation');
    releaseRevision();
    const revisionReceipt = await (await revisionQueued).json();
    await page.unroute('**/api/source-reconciliation-queue');
    if (revisionReceipt.reconciliation_action !== 'retain_revision' ||
        revisionReceipt.previous_native_evidence_id !== revisionPreview.native_evidence_id) {
      throw Error('Original revision approval lost its exact previous evidence binding');
    }
    if (!(await page.locator('#action-title').textContent()).includes('Synthetic scoped migration source') ||
        !(await page.locator('#action-content').textContent()).includes(revisionIdentity)) {
      throw Error('A delayed queue receipt replaced the newly opened current dossier');
    }
    runWorker();
    await page.waitForFunction(() =>
      document.querySelector('#action-title')?.textContent
        .includes('Revised scoped migration source'), {}, {timeout: 25000});
    const revisedDossier = await page.locator('#action-content').textContent();
    if (!revisedDossier.includes(revisionPreview.native_evidence_id) ||
        !revisedDossier.includes(revisionPreview.expected_evidence_id) ||
        !revisedDossier.includes('commercial authority: No')) {
      throw Error('Live original-source revision lost previous evidence or promoted authority');
    }
    const revisionAudit = await (await page.request.get(new URL(
      '/api/source-reconciliation-audit?' + new URLSearchParams({job: revisionReceipt.job_id}),
      process.argv[2]).href)).json();
    if (revisionAudit.job_status !== 'completed' ||
        revisionAudit.approval.previous_evidence_id !== revisionPreview.native_evidence_id) {
      throw Error('Original revision worker lost its immutable prior-evidence approval');
    }
    await page.click('#action-close');
    await page.click('nav button[data-page="Evidence Chains"]');
    await page.waitForFunction(() =>
      document.querySelector('[data-shared-investigations]')?.textContent
        .includes('Revised scoped migration source'));
    const revisedIds = await page.locator('[data-shared-investigations] [data-investigation-id]')
      .evaluateAll(nodes => nodes.map(node => node.dataset.investigationId).sort());
    if (JSON.stringify(revisedIds) !== JSON.stringify(migratedIds) ||
        originalDigest() !== beforeRevisionWorker || runWorker().processed_jobs !== 0) {
      throw Error('Original revision duplicated investigations, changed source data, or repeated work');
    }
    await page.click('#notifications');
    await page.waitForSelector('[data-source-notice]');
    await page.click('#mark-read');
    await page.waitForFunction(() =>
      [...document.querySelectorAll('[data-source-notice]')].every(n =>
        n.closest('.notice').classList.contains('read')));
    await page.reload();
    await page.waitForFunction(() => document.documentElement.dataset.ready === 'true');
    await page.click('#notifications');
    await page.waitForSelector('[data-source-notice]');
    if (!(await page.locator('[data-source-notice]').first()
      .evaluate(n => n.closest('.notice').classList.contains('read')))) {
      throw Error('Source notification read receipt did not survive browser restart');
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
