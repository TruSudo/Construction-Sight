'use strict';
const {chromium}=require('../visual/node_modules/playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH,args:['--no-sandbox','--disable-dev-shm-usage']});
 try{
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(process.argv[2]);await page.waitForFunction(()=>document.documentElement.dataset.ready==='true');
  await page.click('nav button[data-page="Bid Studio"]');await page.click('#scope-templates');
  await page.click('[data-scope-edit="CCTV"]');await page.waitForSelector('#scope-form[data-version="1"]');await page.fill('#scope-form [name="body"]','Demo reusable CCTV reviewed scope');await page.click('#scope-form button[type="submit"]');
  await page.waitForFunction(()=>Array.from(document.querySelectorAll('#action-content tr')).some(r=>r.textContent.includes('CCTV')&&r.textContent.includes('2')));
  await page.click('[data-scope-history="CCTV"]');if(await page.locator('#action-content tbody tr').count()!==2)throw Error('Scope versions not retained');await page.locator('#action-dialog').evaluate(d=>d.close());
  await page.click('#price-book');for(const[k,v]of Object.entries({description:'Demo catalog camera',unit:'each',unit_price:'1.25',basis:'Demo operator quote'}))await page.fill('#price-form [name="'+k+'"]',v);await page.click('#price-form button[type="submit"]');
  await page.waitForSelector('[data-price-edit]');await page.click('[data-price-edit]');await page.waitForSelector('#price-form[data-version="1"]');await page.fill('#price-form [name="unit_price"]','2.50');await page.click('#price-form button[type="submit"]');
  await page.waitForFunction(()=>document.querySelector('#action-content').textContent.includes('$2.50'));await page.click('[data-price-history]');
  if(await page.locator('#action-content tbody tr').count()!==2)throw Error('Price versions not retained');await page.locator('#action-dialog').evaluate(d=>d.close());
  await page.click('#new-bid');await page.selectOption('#bid-form [name="scope_template"]','CCTV');
  if(await page.inputValue('#bid-form [name="scope"]')!=='Demo reusable CCTV reviewed scope')throw Error('Edited template unavailable to estimate');
  const price=await page.locator('#bid-lines [name="price"] option').nth(1).getAttribute('value');await page.selectOption('#bid-lines [name="price"]',price);
  if(await page.inputValue('#bid-lines [name="unit_price"]')!=='2.50')throw Error('Latest price unavailable to estimate');
  if(errors.length)throw Error(errors.join('; '));console.log('Scope and price edits, immutable versions, reusable estimate values: PASS');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
