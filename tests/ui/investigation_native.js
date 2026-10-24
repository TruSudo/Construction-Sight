'use strict';
const {chromium}=require('../visual/node_modules/playwright');
const {spawnSync}=require('node:child_process');
const {createHash}=require('node:crypto');
const {readFileSync}=require('node:fs');
const {resolve}=require('node:path');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH,args:['--no-sandbox','--disable-dev-shm-usage']});
 try{
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(process.argv[2]);
  await page.waitForFunction(()=>document.documentElement.dataset.ready==='true');
  await page.click('nav button[data-page="Evidence Chains"]');
  await page.waitForSelector('section[data-shared-investigations] [data-investigation-id]');
  const ids=await page.locator('section[data-shared-investigations] [data-investigation-id]').evaluateAll(nodes=>nodes.map(n=>n.dataset.investigationId).sort());
  if(ids.length!==2||ids[0]===ids[1])throw Error('Distinct source investigations were merged or absent');
  if(!(await page.locator('section[data-shared-investigations]').textContent()).includes('unmapped'))throw Error('Unmapped investigative records silently acquired map points');
  await page.locator('section[data-shared-investigations] [data-investigation-id]').first().click();
  await page.waitForSelector('#export-investigation');
  const body=await page.locator('#action-content').textContent();
  if(!body.includes('identity independently verified: No')||!body.includes('commercial authority: No'))throw Error('Unverified candidate was promoted in dossier');
  if(!body.includes('Evidence chronology'))throw Error('Retained chronology not shown');
  await page.click('#action-close');
  await page.click('nav button[data-page="Project Intelligence"]');
  await page.waitForSelector('section[data-shared-investigations] [data-investigation-id]');
  const analyticsIds=await page.locator('section[data-shared-investigations] [data-investigation-id]').evaluateAll(nodes=>nodes.map(n=>n.dataset.investigationId).sort());
  if(JSON.stringify(ids)!==JSON.stringify(analyticsIds))throw Error('Workspace views disagree about canonical identities');
  for(const view of ['Lead Console','Entity Network','Site Map']){
   await page.click('nav button[data-page="'+view+'"]');
   await page.waitForSelector('section[data-shared-investigations] [data-investigation-id]');
   const viewIds=await page.locator('section[data-shared-investigations] [data-investigation-id]').evaluateAll(nodes=>nodes.map(n=>n.dataset.investigationId).sort());
   if(JSON.stringify(ids)!==JSON.stringify(viewIds))throw Error(view+' disagrees about canonical identities');
  }
  await page.selectOption('[data-investigation-source]','ceqa');
  await page.waitForFunction(()=>document.querySelectorAll('section[data-shared-investigations] [data-investigation-id]').length===1);
  await page.selectOption('[data-investigation-location]','unmapped');
  await page.waitForFunction(()=>document.querySelectorAll('section[data-shared-investigations] [data-investigation-id]').length===0);
  await page.click('[data-investigation-reset]');
  await page.waitForFunction(()=>document.querySelectorAll('section[data-shared-investigations] [data-investigation-id]').length===2);
  await page.click('#map-fit');
  await page.waitForSelector('#points [data-investigation-id]');
  const markers=page.locator('#points [data-investigation-id]');
  if(await markers.count()!==1)throw Error('Unmapped record acquired a point or mapped record disappeared');
  const markerId=await markers.first().getAttribute('data-investigation-id');
  const coverage=await page.locator('#map-coverage').textContent();
  if(!coverage.includes('1 visible source-claimed investigation points (1 on page)')||!coverage.includes('1 investigations unmapped on page'))throw Error('Investigation coverage was lost: '+coverage);
  await markers.first().focus();
  await page.keyboard.press('Enter');
  await page.waitForSelector('#export-investigation');
  if(!(await page.locator('#action-content').textContent()).includes(markerId))throw Error('Map marker opens a different investigation');
  await page.click('#action-close');
  await page.click('nav button[data-page="Entity Network"]');
  await page.locator('section[data-shared-investigations] tr').filter({hasText:'Synthetic CEQA'}).locator('[data-investigation-network-id]').click();
  await page.waitForFunction(()=>[...document.querySelectorAll('[data-shared-node]')].some(n=>(n.getAttribute('aria-label')||'').includes('Synthetic Evidence Development')));
  await page.getByRole('button',{name:'Source-claimed developer: Synthetic Evidence Development',exact:true}).click();
  if(!(await page.locator('[data-shared-node-detail]').textContent()).includes('Synthetic Evidence Development'))throw Error('Full retained party identity is not inspectable');
  await page.waitForSelector('[data-shared-entity-graph] [data-shared-node]');
  const nodeLabels=await page.locator('[data-shared-node]').evaluateAll(nodes=>nodes.map(n=>n.getAttribute('aria-label')).join(' '));
  if(!nodeLabels.includes('Synthetic Evidence Development'))throw Error('Persisted source party missing from Entity Network');
  if(!(await page.locator('[data-investigation-network]').textContent()).includes('source_claimed_developer'))throw Error('Persisted party relationship evidence missing');
  await page.fill('#search','Synthetic Evidence Development');
  await page.waitForSelector('#search-results [data-search-index]');
  await page.waitForFunction(()=>[...document.querySelectorAll('#search-results [data-search-index]')].some(n=>n.textContent.includes('Synthetic CEQA')));
  await page.locator('#search-results [data-search-index]').filter({hasText:'Synthetic CEQA'}).click();
  await page.waitForSelector('#export-investigation');
  if(!(await page.locator('#action-content').textContent()).includes('Retained evidence artifacts'))throw Error('Source evidence inspection missing');
  // The existing lead engine must accept only explicitly reviewed, nonactionable
  // canonical source evidence, then suppress repeat handoffs across reloads.
  await page.click('#preview-canonical-lead');
  await page.waitForFunction(()=>document.querySelector('#canonical-lead-review-result')?.textContent.includes('Original review:'),{},{timeout:20000});
  if(!(await page.locator('#canonical-lead-review-result').textContent()).includes('Human review required'))
   throw Error('Original lead preview promoted unverified source evidence');
  await page.fill('#canonical-lead-review-reason','Retain this source claim for independent human review.');
  await page.check('#canonical-lead-review-confirm');
  await page.click('#retain-canonical-lead');
  await page.waitForFunction(()=>document.querySelector('#canonical-lead-review-result')?.textContent.includes('Retained under existing lead workflow'),{},{timeout:20000});
  if(!(await page.locator('#canonical-lead-review-result').textContent()).includes('No contact or bid authorized'))
   throw Error('Canonical lead handoff bypassed commercial authority');
  await page.click('#preview-canonical-lead');
  await page.waitForFunction(()=>document.querySelector('#canonical-lead-review-result')?.textContent.includes('Already retained for review'),{},{timeout:20000});
  // A retained workflow must appear in the real Lead Console with a link back
  // to the same canonical investigation, not a separate SMARTS lead identity.
  await page.click('#action-close');
  await page.click('nav button[data-page="Lead Console"]');
  await page.waitForSelector('[data-canonical-lead-dossier]',{timeout:20000});
  const consoleText=await page.locator('[data-canonical-lead-workflows]').textContent();
  if(!(await page.locator('[data-canonical-watch-state]').first().textContent()).includes('Not watched'))
   throw Error('Original retained lead unexpectedly borrowed a watch from another source');
  if(!consoleText.includes('current source observation')||
     !consoleText.includes('1–1 of 1 retained canonical lead records'))
   throw Error('Native lead console lost persisted workflow provenance: '+consoleText);
  // Exercise original one-shot authority and durable review history from the
  // existing native Lead Console, without ever authorizing ready/outreach/bids.
  await page.locator('[data-canonical-review-transition]').first().click();
  await page.waitForSelector('#canonical-review-transition-form');
  await page.locator('#canonical-review-transition-form [name="reason"]')
   .fill('Retained source is under independent operator review.');
  await page.locator('#canonical-review-transition-form [name="confirm"]').check();
  await page.locator('#canonical-review-transition-form button[type="submit"]').click();
  await page.waitForFunction(()=>!document.getElementById('action-dialog').open,{},{timeout:20000});
  await page.waitForFunction(()=>document.querySelector('[data-canonical-lead-workflows]')?.textContent.includes('2 events'),{},{timeout:20000});
  const reviewedConsole=await page.locator('[data-canonical-lead-workflows]').textContent();
  if(!reviewedConsole.includes('2 events')||!reviewedConsole.includes('current source observation'))
   throw Error('Original review state transition did not persist safely in native console');
  await page.locator('[data-canonical-lead-workflows] details').first().locator('summary').click();
  const workflowDownload=page.waitForEvent('download');
  await page.locator('[data-canonical-workflow-export]').first().click();
  const workflowExport=await workflowDownload;
  if(workflowExport.suggestedFilename()!=='canonical-lead-workflow-history.json')
   throw Error('Complete original workflow history export is unavailable');
  const workflowReport=JSON.parse(readFileSync(await workflowExport.path(),'utf8'));
  if(!workflowReport.history_integrity_validated||!workflowReport.history_complete||
     workflowReport.event_count!==2||workflowReport.transitions.length!==2||
     workflowReport.current_status!==workflowReport.transitions[1].current_status||
     workflowReport.outreach_authorized||workflowReport.bid_authorized)
   throw Error('Native lead export omitted original events or granted unauthorized commerce');
  const leadPage=await (await page.request.get(
   new URL('/api/investigation-lead-workflows',process.argv[2]).href)).json();
  if(leadPage.rows.length!==1)throw Error('Canonical result fixture requires one exact retained lead');
  const retainedLead=leadPage.rows[0],workflowId=retainedLead.workflow_id;
  const emptyHistory=page.locator('[data-canonical-result-history]').first();
  if(!await emptyHistory.count()||
     !(await emptyHistory.locator('summary').textContent()).includes('No retained outcome'))
   throw Error('Absent original result history was represented as an outcome');
  const resultSeed=spawnSync('python',['tests/ui/seed_canonical_results.py',
   process.argv[3]||'/tmp/cs-ui-state',workflowId],
   {encoding:'utf8',env:{...process.env,PYTHONPATH:'src'}});
  if(resultSeed.status!==0)throw Error('Original immutable result fixture failed: '+resultSeed.stderr);
  const seeded=JSON.parse(resultSeed.stdout);
  const database=resolve(process.argv[3]||'/tmp/cs-ui-state','investigations.sqlite3');
  const databaseDigest=()=>createHash('sha256').update(readFileSync(database)).digest('hex');
  const seededDatabaseDigest=databaseDigest();
  await page.reload();
  await page.waitForFunction(()=>document.documentElement.dataset.ready==='true');
  await page.click('nav button[data-page="Lead Console"]');
  await page.waitForSelector('[data-canonical-result-history]');
  const resultRow=page.locator('[data-canonical-lead-workflows] tr').filter({hasText:workflowId});
  const resultHistory=resultRow.locator('[data-canonical-result-history]');
  const summary=await resultHistory.locator('summary').textContent();
  if(!summary.includes('lost')||!summary.includes('3'))
   throw Error('Superseded calculated share was resurrected as the current outcome: '+summary);
  await resultHistory.locator('summary').click();
  const historyText=await resultHistory.textContent();
  const currentRevisionText=await resultHistory.locator('li').last().textContent();
  if(!historyText.includes('Never sum superseded shares')||
     !historyText.includes('grants no commercial authority')||
     !historyText.includes('Superseded revision 1 · unknown')||
     !currentRevisionText.includes('Current revision 3 · lost')||
     !currentRevisionText.includes('Calculated share: not recorded')||
     currentRevisionText.includes('12346'))
   throw Error('Native result details lost current-only or non-authority cautions');
  for(const expected of ['123456','100000','12346',
   retainedLead.canonical_investigation_id,retainedLead.original_source_evidence_id,
   ...seeded.history.flatMap(r=>[r.ledger_id,r.content_digest]),
   'Synthetic correction removes the current calculated share']){
   if(!historyText.includes(expected))
    throw Error('Native original result history lost exact money, revision or source provenance: '+expected);
  }
  const historyPayload=await (await page.request.get(
   new URL('/api/investigation-lead-workflows',process.argv[2]).href)).json();
  const exactRow=historyPayload.rows.find(r=>r.workflow_id===workflowId);
  const outcome=exactRow.historical_result;
  if(historyPayload.read_only!==true||outcome.revision_count!==3||
     outcome.current_revision.status!=='lost'||
     outcome.current_revision.gross_value_minor!==null||
     outcome.current_revision.calculated_share_minor!==null||
     outcome.money_unit_encoding!=='decimal_integer_string'||
     outcome.revision_history[1].gross_value_minor!=='123456'||
     outcome.revision_history[1].share_rate_ppm!==100000||
     outcome.revision_history[1].calculated_share_minor!=='12346'||
     outcome.revision_history.map(r=>r.revision).join(',')!=='1,2,3'||
     outcome.revision_history[2].supersedes_ledger_id!==seeded.history[1].ledger_id||
     !outcome.latest_revision_only_is_current||!outcome.past_revisions_must_not_be_summed)
   throw Error('Native result payload lost original immutable correction or exact-money semantics');
  for(const flag of ['award_verified','contract_verified',
   'share_entitlement_verified','payment_received_verified']){
   if(outcome[flag]!==false)throw Error('Historical outcome inferred commercial authority: '+flag);
  }
  for(const flag of ['commercial_authority_granted','outreach_authorized','bid_authorized']){
   if(exactRow[flag]!==false)throw Error('Result inspection enabled a commercial action: '+flag);
  }
  const exportEvent=page.waitForEvent('download');
  await resultHistory.locator('[data-canonical-result-export]').click();
  const exported=await exportEvent;
  if(exported.suggestedFilename()!=='canonical-lead-result-history.json')
   throw Error('Canonical result export did not use the exact history artifact');
  const exportedRow=JSON.parse(readFileSync(await exported.path(),'utf8'));
  if(JSON.stringify(exportedRow)!==JSON.stringify(exactRow))
   throw Error('Canonical result export lost exact workflow/source/correction lineage');
  if(databaseDigest()!==seededDatabaseDigest)
   throw Error('Read-only Lead Console result inspection or export altered retained state');
  await page.locator('[data-canonical-lead-dossier]').first().click();
  await page.waitForSelector('#export-investigation');
  if(!(await page.locator('#action-content').textContent()).includes('Canonical investigation ID:'))
   throw Error('Original retained lead did not reopen the shared investigation dossier');
  // The native canonical watcher must bind the current committed dossier, not
  // the unrelated commercial lead watchlist or a browser-only state object.
  await page.locator('[data-investigation-watch-action="watch"]').click();
  await page.waitForFunction(()=>document.querySelector('#native-investigation-watch')?.textContent.includes('Watching committed evidence'));
  const update=spawnSync('python',['tests/ui/seed_investigations.py',process.argv[3]||'/tmp/cs-ui-state','update'],{encoding:'utf8',env:{...process.env,PYTHONPATH:'src'}});
  if(update.status!==0)throw Error('Independent retained worker failed: '+update.stderr);
  await page.waitForFunction(()=>document.querySelector('#action-title').textContent.includes('revised retained evidence'),{},{timeout:20000});
  if(!(await page.locator('section[data-shared-investigations]').textContent()).includes('revised retained evidence'))throw Error('Worker revision did not reach shared inventory');
  await page.waitForSelector('[data-investigation-watch-action="acknowledge"]');
  await page.click('#action-close');
  await page.reload();
  await page.waitForFunction(()=>document.documentElement.dataset.ready==='true');
  await page.click('nav button[data-page="Lead Console"]');
  await page.waitForSelector('[data-canonical-result-history]');
  const staleResultRow=page.locator('[data-canonical-lead-workflows] tr').filter({hasText:workflowId});
  if(!(await staleResultRow.textContent()).includes('source revision requires review')||
     await staleResultRow.locator('[data-canonical-review-transition]').count())
   throw Error('Historical outcomes bypassed the changed-source review boundary');
  if(!(await staleResultRow.locator('[data-canonical-watch-state]').textContent())
      .includes('Watched · committed evidence changed'))
   throw Error('Original lead projection failed to share the dossier and Watchlist watch state');
  await staleResultRow.locator('[data-canonical-result-history] summary').click();
  const staleHistory=await staleResultRow.locator('[data-canonical-result-history]').textContent();
  if(!staleHistory.includes(seeded.history[2].content_digest)||
     !staleHistory.includes(retainedLead.original_source_evidence_id))
   throw Error('Source revision or reload replaced the immutable original result history');
  const stalePayload=await (await page.request.get(
   new URL('/api/investigation-lead-workflows',process.argv[2]).href)).json();
  const stale=stalePayload.rows.find(r=>r.workflow_id===workflowId);
  if(stale.canonical_investigation_id!==retainedLead.canonical_investigation_id||
     stale.current_source_evidence_id===stale.original_source_evidence_id||
     JSON.stringify(stale.historical_result)!==JSON.stringify(outcome))
   throw Error('Changed-source lead history lost exact investigation or original result lineage');
  await page.click('nav button[data-page="Watchlist"]');
  await page.waitForSelector('[data-investigation-watch-open]');
  if(!(await page.locator('[data-investigation-watch-open]').first().locator('xpath=../..').textContent()).includes('changed'))
   throw Error('Committed investigation change not visible in existing Watchlist');
  await page.click('#notifications');
  await page.waitForSelector('[data-investigation-notice]');
  await page.locator('[data-investigation-notice]').first().click();
  await page.waitForSelector('[data-investigation-watch-action="acknowledge"]');
  await page.locator('[data-investigation-watch-action="acknowledge"]').click();
  await page.waitForFunction(()=>!document.querySelector('[data-investigation-watch-action="acknowledge"]'));
  await page.click('#action-close');
  await page.click('nav button[data-page="Entity Network"]');
  await page.waitForSelector('section[data-shared-investigations] [data-investigation-id]');
  await page.route('**/api/investigations?revision=1',route=>route.fulfill({status:503,body:'offline refresh fixture'}));
  await page.waitForFunction(()=>document.querySelector('[data-investigation-status]').textContent.includes('Live refresh disconnected'),{},{timeout:15000});
  await page.unroute('**/api/investigations?revision=1');
  await page.click('[data-investigation-refresh]');
  await page.waitForFunction(()=>document.querySelector('[data-investigation-status]').textContent.includes('committed revision'));
  await page.click('nav button[data-page="Site Map"]');
  await page.waitForSelector('section[data-shared-investigations] [data-investigation-id]');
  const afterRevisionIds=await page.locator('section[data-shared-investigations] [data-investigation-id]').evaluateAll(nodes=>nodes.map(n=>n.dataset.investigationId).sort());
  if(JSON.stringify(ids)!==JSON.stringify(afterRevisionIds))throw Error('Source revision duplicated investigations');
  await page.click('nav button[data-page="Command Center"]');
  await page.waitForSelector('#points [data-investigation-id]',{timeout:20000});
  const overviewIds=await page.locator('#points [data-investigation-id]').evaluateAll(nodes=>nodes.map(n=>n.dataset.investigationId));
  if(overviewIds.length!==1||overviewIds[0]!==markerId)
   throw Error('Approved native overview map disagrees with persisted Site Map investigation identity: '+overviewIds);
  const overviewMarkerLabel=await page.locator('#points [data-investigation-id]').first().getAttribute('aria-label');
  if(!overviewMarkerLabel.includes('Source-claimed investigation'))
   throw Error('Overview silently promoted an unverified source claim into a commercial lead');
  const overviewCoverage=await page.locator('#map-coverage').textContent();
  if(!overviewCoverage.includes('1 visible source-claimed investigation points')||!overviewCoverage.includes('mapped investigation scan complete'))
   throw Error('Overview did not disclose source-claimed investigation coverage: '+overviewCoverage);
  await page.locator('#points [data-investigation-id]').first().click();
  await page.waitForSelector('#export-investigation');
  if(!(await page.locator('#action-content').textContent()).includes(markerId))
   throw Error('Overview investigation marker did not navigate into the shared canonical dossier');
  // A new worker commit must update the overview without navigating away or
  // requiring the operator to restart the dashboard.
  const overviewRevision=await page.evaluate(()=>overviewInvestigationMap.cursor);
  const later=spawnSync('python',['tests/ui/seed_investigations.py',process.argv[3]||'/tmp/cs-ui-state','dashboard-refresh'],{encoding:'utf8',env:{...process.env,PYTHONPATH:'src'}});
  if(later.status!==0)throw Error('Background map revision fixture failed: '+later.stderr);
  await page.waitForFunction(previous=>overviewInvestigationMap.cursor!==previous&&
   overviewInvestigationMap.rows.some(r=>(r.title||'').includes('dashboard-refresh')),
   overviewRevision,{timeout:25000});
  if(await page.locator('#points [data-investigation-id]').count()!==1)
   throw Error('Background source revision duplicated or removed the canonical overview marker');
  await page.waitForFunction(()=>document.querySelector('#action-title').textContent.includes('dashboard-refresh'),{},{timeout:20000});
  await page.click('#action-close');
  // Parcel/GIS original operator source evidence must be reachable inside the
  // single approved native interface, independent of an original operator DB.
  const parcelResponse = await page.request.get(new URL('/api/parcel-source-readiness',
    process.argv[2]).href);
  if (!parcelResponse.ok())
    throw Error('Original parcel source API unavailable: '+parcelResponse.status()+
      ' '+(await parcelResponse.text()).slice(0,350));
  await page.click('nav button[data-page="Sources & Collection"]');
  await page.waitForSelector('[data-parcel-source-readiness]',{timeout:20000});
  const parcelProblem = await page.locator(
    '[data-parcel-source-readiness] [role="alert"]').allTextContents();
  if (parcelProblem.length)
    throw Error('Original parcel readiness could not render: '+parcelProblem.join(' | '));
  await page.waitForSelector('[data-parcel-source-readiness] [data-parcel-source-inspect]',
    {timeout:20000});
  await page.waitForFunction(() => {
    const box=document.querySelector('[data-retained-parcel-proofs]');
    return Boolean(box && !box.textContent.includes('Checking explicitly configured'));
  }, {}, {timeout:15000});
  if (!(await page.locator('[data-retained-parcel-proofs]').textContent())
       .match(/original source database|original persisted bundles|verification unavailable/i))
    throw Error('Original ArcGIS proof inventory not connected to Sources & Collection');
  const parcelRows = page.locator('[data-parcel-source-inspect]');
  if (await parcelRows.count()!==4) throw Error('Original four-provider parcel source registry was lost');
  const parcelText = await page.locator('[data-parcel-source-readiness]').textContent();
  if (!parcelText.includes('San Bernardino') || !parcelText.includes('Riverside') ||
      !parcelText.includes('licensed') || !parcelText.includes('not live data'))
    throw Error('Native parcel source status omitted county, license or assurance limits');
  await parcelRows.first().click();
  await page.waitForSelector('#action-content pre');
  const parcelEvidence = await page.locator('#action-content').textContent();
  if (!parcelEvidence.includes('Original expected-field schema preview') ||
      !parcelEvidence.includes('Retained official evidence') ||
      !parcelEvidence.includes('not execution'))
    throw Error('Original parcel schema/verification/acquisition reports disconnected');
  await page.click('#action-close');
  await page.locator('[data-parcel-sample-preview]').first().click();
  await page.waitForSelector('#parcel-row-json');
  await page.fill('#parcel-row-json',JSON.stringify([{ParcelNumber:'123-456-789'}]));
  await page.click('#parcel-run-row-preview');
  await page.waitForSelector('#parcel-row-export');
  const parcelRowText = await page.locator('#action-content').textContent();
  if (!parcelRowText.includes('manual_unverified_sample') ||
      !parcelRowText.includes('normalized_apn') ||
      !parcelRowText.includes('rows_retained'))
    throw Error('Original parcel row preview missing from native source workflow');
  await page.click('#action-close');
  if(errors.length)throw Error(errors.join('; '));
  console.log('Native shared investigation inventory, exact immutable outcome history, dossier and cross-view IDs: PASS');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
