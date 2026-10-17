'use strict';
const {chromium}=require('../visual/node_modules/playwright');
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
  const {spawnSync}=require('child_process');
  const update=spawnSync('python',['tests/ui/seed_investigations.py',process.argv[3]||'/tmp/cs-ui-state','update'],{encoding:'utf8',env:{...process.env,PYTHONPATH:'src'}});
  if(update.status!==0)throw Error('Independent retained worker failed: '+update.stderr);
  await page.waitForFunction(()=>document.querySelector('#action-title').textContent.includes('revised retained evidence'),{},{timeout:20000});
  if(!(await page.locator('section[data-shared-investigations]').textContent()).includes('revised retained evidence'))throw Error('Worker revision did not reach shared inventory');
  await page.click('#action-close');
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
  await page.click('#action-close');
  if(errors.length)throw Error(errors.join('; '));
  console.log('Native shared investigation inventory, dossier, provenance and cross-view IDs: PASS');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
