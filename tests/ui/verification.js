'use strict';
const {chromium}=require('../visual/node_modules/playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH,args:['--no-sandbox','--disable-dev-shm-usage']});
 try{
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(process.argv[2]);await page.waitForFunction(()=>document.documentElement.dataset.ready==='true');
  await page.click('nav button[data-page="Lead Console"]');await page.click('#verification-queue');await page.waitForSelector('#site-review-form');
  const first=await page.locator('#action-title').textContent();
  await page.locator('#verify-next').focus();await page.keyboard.press('j');
  if(await page.locator('#action-title').textContent()===first)throw Error('J did not advance');
  await page.locator('#verify-previous').focus();await page.keyboard.press('k');
  if(await page.locator('#action-title').textContent()!==first)throw Error('K did not return');
  await page.fill('#site-review-form [name=source]','https://county.example.test/demo-site-evidence');
  await page.fill('#site-review-form [name=note]','Demo operator reviewed this independent physical site address.');
  await page.check('#site-review-checked');await page.click('#site-review-form button[type=submit]');
  await page.waitForFunction(()=>data.rows.some(r=>r.site_verification?.note==='Demo operator reviewed this independent physical site address.'));
  await page.reload();await page.waitForFunction(()=>document.documentElement.dataset.ready==='true');
  const review=await page.evaluate(()=>data.rows.find(r=>r.site_verification?.note==='Demo operator reviewed this independent physical site address.')?.site_verification);
  if(!review?.verified||!review.site_fingerprint)throw Error('Review did not persist with site fingerprint');
  if(errors.length)throw Error(errors.join('\n'));
  console.log('Verification queue: J/K, explicit evidence review, persistence and zero browser errors passed');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
