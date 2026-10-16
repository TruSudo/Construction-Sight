'use strict';
const {chromium}=require('../visual/node_modules/playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH,args:['--no-sandbox','--disable-dev-shm-usage']});
 try{
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(process.argv[2]);await page.waitForFunction(()=>document.documentElement.dataset.ready==='true');
  if(!await page.locator('#warning').isVisible())throw Error('Scheduled failure is not visible globally');
  await page.click('nav button[data-page="Sources & Collection"]');await page.waitForSelector('#daily-schedule');
  if(await page.locator('#next-run').textContent()!=='—')throw Error('Uninstalled timer invented a next run');
  if(!(await page.locator('#schedule-warning').textContent()).includes('Demo scheduled capture failure'))throw Error('Scheduled failure warning absent');
  await page.click('#daily-schedule');await page.fill('#schedule-form [name="hour"]','7');await page.fill('#schedule-form [name="minute"]','30');await page.click('#schedule-form button[type="submit"]');
  await page.waitForFunction(()=>document.querySelector('#schedule-timer').textContent.includes('07:30:00 America/Los_Angeles'));
  if(!(await page.locator('#schedule-worker-service').textContent()).includes('--poll-inbox'))throw Error('Retained-input worker was hidden from the unit review');
  if(!(await page.locator('#schedule-worker-timer').textContent()).includes('OnUnitInactiveSec=30s'))throw Error('Independent investigation timer missing from review');
  if(!(await page.locator('#action-content').textContent()).includes('systemctl --user daemon-reload'))throw Error('Exact Zorin setup missing');
  await page.click('#schedule-install');await page.waitForFunction(()=>document.querySelector('#schedule-result').textContent.includes('Review and acknowledge'));
  await page.check('#schedule-reviewed');await page.click('#schedule-install');await page.waitForFunction(()=>document.querySelector('#next-run')?.textContent.includes('07:30'));
  await page.click('#daily-schedule');await page.click('#schedule-disable');await page.waitForFunction(()=>document.querySelector('#action-content').textContent.includes('Next run reported by systemd: —'));
  if(errors.length)throw Error(errors.join('; '));console.log('Daily schedule preview/review/install/next-run/disable and visible failure: PASS (isolated Demo manager)');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
