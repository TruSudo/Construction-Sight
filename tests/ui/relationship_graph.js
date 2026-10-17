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
  // Display filters must not change durable graph state or imply verification.
  const sourceFamily=initial.edges.map(e=>e.source_family).find(Boolean);
  if(!sourceFamily)throw Error('No retained source family available for graph filtering');
  await page.selectOption('[data-graph-source]',sourceFamily);
  const visibleIds=await page.locator('[data-live-edge]').evaluateAll(edges=>edges.map(e=>e.dataset.liveEdge));
  if(visibleIds.some(id=>initial.edges.find(e=>e.id===id)?.source_family!==sourceFamily))
   throw Error('Source family filter admitted an unrelated relationship');
  await page.fill('[data-graph-since]','2099-01-01');
  if(await page.locator('[data-live-node]').count())throw Error('Future retained-date filter did not exclude historical nodes');
  await page.fill('[data-graph-since]','');
  await page.selectOption('[data-graph-source]','');
  await page.check('[data-graph-collapse-evidence]');
  if(await page.locator('[data-live-node]').evaluateAll(nodes=>nodes.some(n=>n.getAttribute('aria-label')?.startsWith('evidence:'))))
   throw Error('Collapse-evidence display control left evidence nodes visible');
  await page.uncheck('[data-graph-collapse-evidence]');
  await page.fill('[data-graph-view-name]','Saved browser graph test');
  await page.selectOption('[data-graph-depth]','2');
  await page.click('[data-graph-load]');
  await page.waitForFunction(()=>document.querySelector('[data-graph-connection]').textContent.includes('committed revision'));
  await page.fill('[data-graph-confidence]','50');
  await page.click('[data-graph-save]');
  const local=await page.evaluate(()=>JSON.parse(localStorage.getItem('constructionsight.graph-layouts.v1')||'[]'));
  if(local.length!==1||local[0].name!=='Saved browser graph test'||local[0].depth!==2||!local[0].points.length)
   throw Error('Named view did not persist browser-only coordinates and filters');
  await page.click('[data-graph-clear-filters]');
  await page.fill('[data-graph-confidence]','0');
  await page.click('[data-graph-restore]');
  await page.waitForFunction(()=>document.querySelector('[data-graph-confidence]').value==='50');
  if(await page.locator('[data-graph-depth]').inputValue()!=='2')
   throw Error('Restored local graph layout lost neighborhood depth');
  await page.click('[data-graph-clear-filters]');
  await page.selectOption('[data-graph-depth]','1');
  await page.click('[data-graph-load]');
  await page.waitForSelector('[data-live-node="'+root.id+'"]');
  const retainedAgain=await page.evaluate(async()=>fetch('/api/investigation-graph').then(r=>r.json()));
  if(JSON.stringify(retainedAgain.nodes)!==JSON.stringify(initial.nodes))
   throw Error('Saving or filtering a browser layout modified authoritative graph nodes');
  await page.click('[data-graph-group]');
  const afterGrouping=await page.locator('[data-live-node]').evaluateAll(nodes=>nodes.map(n=>n.dataset.liveNode).sort());
  if(JSON.stringify(afterGrouping)!==JSON.stringify(initial.nodes.map(n=>n.id).sort()))
   throw Error('Node grouping invented, removed or duplicated retained nodes');
  await page.click('[data-graph-family-group]');
  const sourceGrouped=await page.locator('[data-live-node]').evaluateAll(nodes=>nodes.map(n=>n.dataset.liveNode).sort());
  if(JSON.stringify(sourceGrouped)!==JSON.stringify(ids))
   throw Error('Source grouping changed retained node identities');
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
  const historyEntries=await page.evaluate(async()=>fetch('/api/investigation-graph/history-index').then(r=>r.json()));
  if(!historyEntries.events?.length)throw Error('Retained revision timeline is empty');
  const first={sequence:initial.cursor,event_id:initial.anchor};
  const earlier=await page.evaluate(async revision=>{
   const query=new URLSearchParams({after:String(revision.sequence),anchor:revision.event_id});
   const response=await fetch('/api/investigation-graph/history?'+query);
   if(!response.ok)throw Error('Historical graph API rejected retained revision: '+response.status);
   return response.json();
  },first);
  if(!earlier.historical||earlier.as_of_sequence!==first.sequence)throw Error('Event-anchored historical projection was not retained');
  if(earlier.nodes.some(n=>n.label.includes('phase6-background-revision')))
   throw Error('Historical graph leaked later worker state into earlier selected revision');
  await page.selectOption('[data-graph-history]','0');
  await page.click('[data-graph-history-open]');
  await page.waitForFunction(()=>document.querySelector('[data-graph-connection]').textContent.includes('Historical retained graph'));
  if((await page.locator('[data-live-node]').evaluateAll(nodes=>nodes.map(n=>n.getAttribute('aria-label')).join(' '))).includes('phase6-background-revision'))
   throw Error('Historical canvas displayed current instead of retained earlier label');
  await page.click('[data-graph-history-compare]');
  await page.waitForFunction(()=>document.querySelector('[data-graph-history-diff]').textContent.includes('Compared with'));
  if(!(await page.locator('[data-graph-history-diff]').textContent()).includes('revised'))
   throw Error('Historical compare did not report changed retained records');
  await page.click('[data-graph-history-live]');
  await page.waitForFunction(()=>document.querySelector('[data-graph-connection]').textContent.startsWith('Connected'));
  await page.waitForSelector('[data-live-node="'+root.id+'"]');

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
  const dossierLocation=await page.evaluate(async id=>{
   const dossier=await fetch('/api/investigations/'+encodeURIComponent(id)).then(r=>r.json());
   return dossier.source_claimed_points?.find(p=>typeof p.latitude==='number'&&typeof p.longitude==='number');
  },root.id);
  if(!dossierLocation)throw Error('Source-claimed coordinate missing from map navigation fixture');
  await page.locator('[data-live-node="'+root.id+'"]').focus();await page.keyboard.press('Enter');
  await page.click('[data-graph-map]');
  await page.waitForSelector('[data-investigation-id="'+root.id+'"]');
  if(await page.locator('#stub-title').textContent()!=='Site Map')
   throw Error('Graph coordinate navigation did not enter the existing Site Map');
  const pointCentered=await page.evaluate(p=>Math.abs(center[0]-p.latitude)<.0001&&
   Math.abs(center[1]-p.longitude)<.0001,dossierLocation);
  if(!pointCentered)throw Error('Map was not centered on exact retained source-claimed coordinates');
  await page.waitForSelector('[data-investigation-live-graph-id="'+root.id+'"]');
  await page.click('[data-investigation-live-graph-id="'+root.id+'"]');
  await page.waitForSelector('[data-live-graph]');
  await page.waitForFunction(id=>document.querySelector('[data-graph-root]')?.value===id,root.id);
  await page.waitForSelector('[data-live-node="'+root.id+'"]');
  if((await page.locator('#stub-title').textContent())!=='Entity Network')
   throw Error('Map-to-graph navigation did not restore Entity Network');
  if(errors.length)throw Error(errors.join('; '));
  console.log('Live graph: shared embedded/full-screen state, canonical evidence, worker continuity, committed events, disconnection recovery and reopen reconstruction PASS');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
