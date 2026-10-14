'use strict';
const {chromium}=require('../visual/node_modules/playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH,args:['--no-sandbox','--disable-dev-shm-usage']});
 try{
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(process.argv[2]);await page.waitForFunction(()=>document.documentElement.dataset.ready==='true');
  await page.click('nav button[data-page="Project Intelligence"]');await page.waitForSelector('#review-weights');
  await page.click('[data-cohort]');await page.waitForSelector('#action-dialog[open] [data-open]');await page.locator('#action-dialog').evaluate(d=>d.close());
  await page.click('#review-weights');const prior=Number(await page.inputValue('#weights-review-form input[name="industrial"]'));
  await page.fill('#weights-review-form input[name="industrial"]',String(prior===100?99:prior+1));
  await page.fill('#weights-review-form input[name="reason"]','Browser-reviewed calibration cohort');await page.check('#weights-review-form input[name="reviewed"]');
  await page.click('#apply-reviewed-weights');await page.waitForFunction(()=>document.querySelector('#section-content').textContent.includes('Browser-reviewed calibration cohort'));
  await page.reload();await page.waitForFunction(()=>document.documentElement.dataset.ready==='true');await page.click('nav button[data-page="Project Intelligence"]');
  await page.waitForFunction(()=>document.querySelector('#section-content').textContent.includes('Browser-reviewed calibration cohort'));
  if(errors.length)throw Error(errors.join('; '));console.log('Calibration drill-down, reviewed weights apply and persistent changelog: PASS');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
