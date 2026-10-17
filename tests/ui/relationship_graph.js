'use strict';
const {chromium}=require('../visual/node_modules/playwright');
const {spawnSync}=require('child_process');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH,args:['--no-sandbox','--disable-dev-shm-usage']});
 try{
  const page=await browser.newPage({viewport:{width:1672,height:941}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto(process.argv[2]);await page.waitForFunction(()=>document.documentElement.dataset.ready==='true');
  async function open(){await page.click('nav button[data-page="Entity Network"]');await page.click('#open-live-relationship-graph');await page.waitForSelector('[data-live-node]');}
  await open();
  const initial=await page.evaluate(async()=>fetch('/api/investigation-graph').then(r=>r.json()));
  const root=initial.nodes.find(n=>n.kind==='investigation'&&n.label.includes('Synthetic CEQA'));
  if(!root)throw Error('Retained investigation missing from live snapshot');
  const ids=await page.locator('[data-live-node]').evaluateAll(nodes=>nodes.map(n=>n.dataset.liveNode).sort());
  if(new Set(ids).size!==ids.length)throw Error('Duplicate graph nodes');
  if(JSON.stringify(ids)!==JSON.stringify(initial.nodes.map(n=>n.id).sort()))throw Error('Graph canvas does not reflect authoritative snapshot');
  await page.locator('[data-graph-canvas]').evaluate(node=>node.dataset.canvasIdentity='same-canvas');
  await page.click('[data-graph-full]');
  if(!(await page.locator('[data-live-graph]').getAttribute('class')).includes('graph-expanded'))throw Error('Full-screen graph did not expand');
  if(await page.locator('[data-graph-canvas]').getAttribute('data-canvas-identity')!=='same-canvas')throw Error('Expanded graph created an independent canvas/state');
  await page.locator('[data-live-node="'+root.id+'"]').focus();await page.keyboard.press('Enter');
  await page.click('[data-graph-dossier]');await page.waitForSelector('#export-investigation');
  const dossier=await page.locator('#action-content').textContent();
  if(!dossier.includes(root.id)||!dossier.includes('commercial authority: No'))throw Error('Graph dossier differs from canonical native investigation');
  await page.click('#action-close');
  await page.locator('[data-graph-evidence]').first().click();
  await page.waitForFunction(()=>document.querySelector('[data-graph-artifact]').textContent.includes('content_hash'));
  await page.keyboard.press('Escape');
  if((await page.locator('[data-live-graph]').getAttribute('class')).includes('graph-expanded'))throw Error('Escape did not restore embedded graph');
  const cursor=Number(await page.locator('[data-live-graph]').getAttribute('data-graph-cursor'));
  await page.click('[data-graph-pause]');
  function worker(revision){
   const result=spawnSync('python',['tests/ui/seed_investigations.py',process.argv[3]||'/tmp/cs-ui-state',revision],{encoding:'utf8',env:{...process.env,PYTHONPATH:'src'}});
   if(result.status!==0)throw Error('Independent worker failed: '+result.stderr);
  }
  worker('phase6-background-revision');
  const current=await page.evaluate(async()=>fetch('/api/investigation-graph').then(r=>r.json()));
  if(current.cursor<=cursor)throw Error('Pausing graph stopped background investigation');
  if(Number(await page.locator('[data-live-graph]').getAttribute('data-graph-cursor'))!==cursor)throw Error('Paused display silently advanced its snapshot');
  await page.click('[data-graph-pause]');
  await page.waitForFunction(previous=>Number(document.querySelector('[data-live-graph]').dataset.graphCursor)>previous,cursor);
  await page.waitForSelector('[data-graph-event]');
  const afterIds=await page.locator('[data-live-node]').evaluateAll(nodes=>nodes.map(n=>n.dataset.liveNode));
  if(new Set(afterIds).size!==afterIds.length)throw Error('Event replay duplicated nodes');
  await page.route('**/api/investigation-graph/events?*',route=>route.fulfill({status:503,body:'controlled graph connection failure'}));
  await page.waitForFunction(()=>document.querySelector('[data-graph-connection]').textContent.includes('Disconnected'),{},{timeout:10000});
  await page.unroute('**/api/investigation-graph/events?*');
  await page.click('[data-graph-refresh]');
  await page.waitForFunction(()=>document.querySelector('[data-graph-connection]').textContent.startsWith('Connected'));
  await page.click('[data-graph-back]');
  worker('phase6-while-closed');
  await page.click('#open-live-relationship-graph');await page.waitForSelector('[data-live-node]');
  const reopened=await page.locator('[data-live-node]').evaluateAll(nodes=>nodes.map(n=>n.getAttribute('aria-label')).join(' '));
  if(!reopened.includes('phase6-while-closed'))throw Error('Reopened graph failed to reconstruct closed-worker changes');
  if(errors.length)throw Error(errors.join('; '));
  console.log('Live graph: shared embedded/full-screen state, canonical evidence, worker continuity, committed events, disconnection recovery and reopen reconstruction PASS');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
