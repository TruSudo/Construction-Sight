'use strict';
const {chromium}=require('../visual/node_modules/playwright');
const assert=require('node:assert/strict');
const png=Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO5+bdkAAAAASUVORK5CYII=','base64');
(async()=>{
 const base=process.argv[2];
 if(!base)throw Error('Provide local Command Center URL');
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH,args:['--no-sandbox','--disable-dev-shm-usage']});
 try{
  const page=await browser.newPage({viewport:{width:1672,height:941}});
  const errors=[],urls=[];
  page.on('pageerror',err=>errors.push(err.message));
  await page.route('https://basemap.nationalmap.gov/**',async route=>{
   urls.push(route.request().url());
   if(route.request().url().includes('/USGSTopo/'))await route.abort();
   else await route.fulfill({status:200,contentType:'image/png',body:png});
  });
  await page.goto(base);await page.waitForFunction(()=>document.documentElement.dataset.ready==='true');
  await page.click('#layers');
  await page.selectOption('#basemap-choice','usgs-imagery-topo');
  await page.waitForFunction(()=>document.querySelectorAll('#tiles img.usgs-tile').length>0);
  await page.waitForFunction(()=>Array.from(document.querySelectorAll('#tiles img.usgs-tile')).some(img=>img.complete&&img.naturalWidth>0));
  assert.ok(urls.some(u=>/\/USGSImageryTopo\/MapServer\/tile\/\d+\/\d+\/\d+$/.test(u)), 'Expected official imagery/topography ArcGIS tile URL');
  let report=await page.evaluate(()=>{
   const img=document.querySelector('#tiles img.usgs-tile');
   const [,z,y,x]=img.src.match(/\/tile\/(\d+)\/(\d+)\/(\d+)$/).map(Number);
   const map=document.getElementById('map'),size=256*2**(zoom-z),[cx,cy]=world(...center);
   const marker=document.querySelector('#points g[data-key]');
   const row=marker&&filtered.find(r=>r.source_key===marker.dataset.key);
   const circle=marker?.querySelector('circle'),projected=row&&world(+row.SITE_LATITUDE,+row.SITE_LONGITUDE);
   return {tileLevel:z,tileLeft:Number.parseFloat(img.style.left),expectedLeft:x*size-cx+map.clientWidth/2,tileTop:Number.parseFloat(img.style.top),expectedTop:y*size-cy+map.clientHeight/2,tileWidth:Number.parseFloat(img.style.width),expectedWidth:size,markerX:circle?+circle.getAttribute('cx'):null,expectedMarkerX:projected?projected[0]-cx+map.clientWidth/2:null,scale:document.getElementById('map-scale').textContent,coverage:document.getElementById('map-coverage').textContent};
  });
  assert.ok(Math.abs(report.tileLeft-report.expectedLeft)<0.01&&Math.abs(report.tileTop-report.expectedTop)<0.01,'Tiles misaligned with Mercator map origin');
  assert.ok(Math.abs(report.tileWidth-report.expectedWidth)<0.01,'Fractional zoom tile size wrong');
  if(report.markerX!==null)assert.ok(Math.abs(report.markerX-report.expectedMarkerX)<0.01,'Lead marker projected at wrong coordinate');
  assert.ok(report.scale&&report.coverage.includes('geolocated'),'Missing functional map scale or coverage count');
  const pan=await page.evaluate(()=>{
   const initial=Array.from(tileElements.values()),generation=mapGeneration,origin=world(...center);
   const start=performance.now();
   for(let i=0;i<40;i++){center=inverse(origin[0]+i*.3,origin[1]+i*.2);drawMap();}
   return {duration:performance.now()-start,unchangedSource:generation===mapGeneration,
    reused:Array.from(tileElements.values()).filter(node=>initial.includes(node)).length,
    tiles:tileElements.size,nodes:document.querySelector('#tiles').childElementCount,
    accurateMarkers:Array.from(document.querySelectorAll('#points g[data-key]')).every(el=>{
     const row=filtered.find(r=>r.source_key===el.dataset.key);
     const [px,py]=world(+row.SITE_LATITUDE,+row.SITE_LONGITUDE),[cx,cy]=world(...center);
     const circle=el.querySelector('circle');
     return Math.abs(+circle.getAttribute('cx')-(px-cx+$('map').clientWidth/2))<.02
      &&Math.abs(+circle.getAttribute('cy')-(py-cy+$('map').clientHeight/2))<.02;
    })};
  });
  assert.ok(pan.unchangedSource&&pan.reused>0,'Continuous panning replaced all cached tiles');
  assert.equal(pan.tiles,pan.nodes,'Tile cache and DOM diverged during panning');
  assert.ok(pan.accurateMarkers,'Construction markers drifted from projected sites after repeated pans');
  assert.ok(pan.duration<1200,'Synchronous panning took more than 1.2 seconds for 40 frames');

  await page.evaluate(()=>{zoom=10.125;drawMap();});
  report=await page.evaluate(()=>{const img=document.querySelector('#tiles img.usgs-tile'),z=Number(img.src.match(/\/tile\/(\d+)\//)[1]);return {width:+img.style.width.slice(0,-2),zoom,tileLevel:z};});
  assert.ok(Math.abs(report.width-256*2**(report.zoom-report.tileLevel))<0.01,'Fractional zoom misaligned after redraw');
  await page.evaluate(()=>{zoom=18;drawMap();});
  await page.waitForFunction(()=>document.querySelectorAll('#tiles img.usgs-tile').length>0);
  assert.ok(await page.evaluate(()=>Array.from(document.querySelectorAll('#tiles img.usgs-tile')).every(img=>img.src.includes('/tile/16/'))),'USGS cache overzoom should use level 16');
  await page.selectOption('#basemap-choice','usgs-topo');
  await page.waitForFunction(()=>basemapFailed===true);
  assert.ok((await page.locator('#attribution').textContent()).includes('offline fallback'),'Missing explicit outage notice');
  assert.equal(await page.locator('#tiles img.usgs-tile').count(),0,'Failed network tiles remain displayed');
  await page.selectOption('#basemap-choice','offline');
  assert.equal(await page.evaluate(()=>basemapFailed),false,'Offline selection must clear prior failure');
  assert.equal(await page.evaluate(()=>basemapMode),'offline');
  await page.reload();await page.waitForFunction(()=>document.documentElement.dataset.ready==='true');
  assert.equal(await page.evaluate(()=>basemapMode),'offline','Selected basemap mode did not persist');
  await page.click('#layers');await page.selectOption('#basemap-choice','usgs-imagery');
  await page.waitForFunction(()=>Array.from(document.querySelectorAll('#tiles img.usgs-tile')).some(img=>img.complete&&img.naturalWidth>0));
  await page.locator('#action-close').click();
  await page.click('nav button[data-page="Site Map"]');
  await page.waitForSelector('#full-map #map');
  assert.ok(await page.locator('#full-map #points g[data-key]').count()>0,'Site Map lost real lead markers');
  await page.click('#zoom-in');
  assert.ok(await page.locator('#full-map #tiles img.usgs-tile').count()>0,'Full map zoom lost USGS tile layer');
  assert.deepEqual(errors,[],'Browser JavaScript errors');
  console.log('USGS provider switching, fixed hosts, mocked tiles, fractional alignment, marker projection, overzoom, offline outage recovery, and full map: PASS');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
