'use strict';
const {chromium}=require('../visual/node_modules/playwright');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH,args:['--no-sandbox','--disable-dev-shm-usage']});
 try{
  const page=await browser.newPage(),errors=[],external=[];page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(!r.url().startsWith(process.argv[2])&&!r.url().startsWith('data:'))external.push(r.url());});
  await page.goto(process.argv[2]);await page.waitForFunction(()=>document.documentElement.dataset.ready==='true');
  await page.waitForFunction(()=>Array.from(document.querySelectorAll('#tiles img.local-tile')).some(img=>img.complete&&img.naturalWidth===256));
  if(!await page.locator('#attribution a[href="https://www.openstreetmap.org/copyright"]').count())throw Error('OSM attribution missing');
  await page.waitForSelector('#highway-shields image');
  const shield=await page.locator('#highway-shields image').first().getAttribute('href');if(!(await page.request.get(process.argv[2]+shield)).ok())throw Error('Local SVG shield missing');
  await page.click('nav button[data-page="Site Map"]');await page.waitForSelector('#full-map #map');
  await page.click('#zoom-in');await page.waitForFunction(()=>Array.from(document.querySelectorAll('#tiles img.local-tile')).some(img=>img.complete&&img.naturalWidth===256));
  if(process.argv[3]){const fs=require('fs'),crypto=require('crypto');await page.click('#workspace-menu');await page.setInputFiles('#map-archive',process.argv[3]);await page.fill('[name="map-sha"]','bad');await page.click('#install-map');await page.waitForFunction(()=>document.querySelector('#map-install-report').textContent.includes('mismatch'));await page.fill('[name="map-sha"]',crypto.createHash('sha256').update(fs.readFileSync(process.argv[3])).digest('hex'));await page.click('#install-map');await page.waitForFunction(()=>document.querySelector('#map-install-report').textContent.includes('installed'));}
  if(errors.length||external.length)throw Error([...errors,...external].join('; '));
  console.log('Offline PMTiles images, OSM attribution, local SVG shields and zoom: PASS');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
