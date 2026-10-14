'use strict';
const {chromium}=require('../visual/node_modules/playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH,args:['--no-sandbox','--disable-dev-shm-usage']});
 try{
  const page=await browser.newPage({viewport:{width:1536,height:864}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto(process.argv[2]);await page.waitForFunction(()=>document.documentElement.dataset.ready==='true');
  let release,started;const delayed=new Promise(resolve=>release=resolve),seen=new Promise(resolve=>started=resolve);let first=true;
  await page.route('**/api/bids',async route=>{if(first){first=false;started();await delayed;}await route.continue();});
  await page.click('nav button[data-page="Bid Studio"]');await seen;
  await page.click('nav button[data-page="Royalty Ledger"]');await page.waitForSelector('#new-royalty');
  release();await page.waitForTimeout(600);
  if(await page.locator('#section-content #new-bid').count())throw Error('Stale Bid Studio response overwrote Royalty Ledger');
  if(!await page.locator('#section-content #new-royalty').count())throw Error('Royalty Ledger disappeared');
  if(errors.length)throw Error(errors.join('; '));
  console.log('Delayed workspace response cannot overwrite the current tab: PASS');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
