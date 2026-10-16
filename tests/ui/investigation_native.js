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
  if(errors.length)throw Error(errors.join('; '));
  console.log('Native shared investigation inventory, dossier, provenance and cross-view IDs: PASS');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
