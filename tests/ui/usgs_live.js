'use strict';
// Real USGS HTTP + browser-image probe. No interception or synthetic tile responses.
// Network failures are recorded as FAIL rather than converting into a passing mock.
const fs=require('node:fs'),path=require('node:path');
const {chromium}=require('../visual/node_modules/playwright');
const origin=process.argv[2],output=process.argv[3];
if(!origin||!output)throw Error('Usage: node tests/ui/usgs_live.js URL OUTPUT.json');
fs.mkdirSync(path.dirname(output),{recursive:true});
const report={checked_at:new Date().toISOString(),context:'retained six genuine SMARTS records, browser fetching real USGS tiles',providers:[],errors:[],passed:false};
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH,args:['--no-sandbox','--disable-dev-shm-usage']});
 try{
  const page=await browser.newPage({viewport:{width:1672,height:941},deviceScaleFactor:1,ignoreHTTPSErrors:false});
  const responses=[];
  page.on('pageerror',e=>report.errors.push('Browser: '+e.message));
  page.on('response',res=>{if(res.url().startsWith('https://basemap.nationalmap.gov/'))responses.push({url:res.url(),status:res.status(),at:new Date().toISOString()});});
  page.on('requestfailed',req=>{if(req.url().startsWith('https://basemap.nationalmap.gov/'))report.errors.push('USGS request failed: '+req.failure()?.errorText+' · '+req.url());});
  await page.goto(origin,{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>document.documentElement.dataset.ready==='true',{timeout:25000});
  const context=await page.evaluate(()=>({genuine:data.rows.filter(r=>r.source_key?.startsWith('smarts:')).length,geolocated:filtered.filter(point).length}));
  report.source=context;
  if(context.genuine<1||context.geolocated<1)throw Error('Expected retained genuine SMARTS rows with geolocated sites');
  await page.evaluate(()=>{center=[34.10373,-117.3493];zoom=12;drawMap();});
  for(const [mode,service] of [['usgs-imagery','USGSImageryOnly'],['usgs-imagery-topo','USGSImageryTopo'],['usgs-topo','USGSTopo']]){
   const entry={mode,service,started_at:new Date().toISOString(),loaded_tiles:0,requested_tiles:0,http_statuses:[],passed:false};
   report.providers.push(entry);
   try{
    const start=Date.now(),offset=responses.length;
    await page.click('#layers');
    await page.selectOption('#basemap-choice',mode);
    await page.locator('#action-close').click();
    await page.waitForFunction(()=>basemapFailed||Array.from(document.querySelectorAll('#tiles img.usgs-tile')).some(i=>i.complete&&i.naturalWidth===256),null,{timeout:22000});
    const first=await page.evaluate(()=>{
     const imgs=Array.from(document.querySelectorAll('#tiles img.usgs-tile'));
     const markers=Array.from(document.querySelectorAll('#points g[data-key]'));
     const [cx,cy]=world(...center),map=$('map');
     const aligned=markers.every(g=>{const r=filtered.find(x=>x.source_key===g.dataset.key),p=world(+r.SITE_LATITUDE,+r.SITE_LONGITUDE),c=g.querySelector('circle');
      return Math.abs(+c.getAttribute('cx')-(p[0]-cx+map.clientWidth/2))<.02&&Math.abs(+c.getAttribute('cy')-(p[1]-cy+map.clientHeight/2))<.02;});
     return {failed:basemapFailed,total:imgs.length,loaded:imgs.filter(i=>i.complete&&i.naturalWidth===256).length,geocoded:filtered.filter(point).length,visibleMarkers:markers.length,aligned,
      attribution:$('attribution').textContent,scale:$('map-scale').textContent};
    });
    Object.assign(entry,{first_load_ms:Date.now()-start,first,loaded_tiles:first.loaded,requested_tiles:responses.slice(offset).filter(r=>r.url.includes('/'+service+'/')).length,http_statuses:responses.slice(offset).filter(r=>r.url.includes('/'+service+'/')).map(r=>r.status)});
    if(first.failed||first.loaded===0||first.visibleMarkers===0||!first.aligned||!first.attribution.includes('USGS'))throw Error('Live imagery, markers, projection, or attribution unavailable');
    // Real navigation: pan 75 px, then zoom; compare coordinates and imagery.
    await page.evaluate(()=>{const p=world(...center);center=inverse(p[0]+75,p[1]+35);drawMap();});
    await page.waitForFunction(()=>Array.from(document.querySelectorAll('#tiles img.usgs-tile')).some(i=>i.complete&&i.naturalWidth===256)||basemapFailed,null,{timeout:15000});
    await page.click('#zoom-in');
    await page.waitForFunction(()=>Array.from(document.querySelectorAll('#tiles img.usgs-tile')).some(i=>i.complete&&i.naturalWidth===256)||basemapFailed,null,{timeout:15000});
    const after=await page.evaluate(()=>{
     const imgs=Array.from(document.querySelectorAll('#tiles img.usgs-tile'));
     const [cx,cy]=world(...center),markers=Array.from(document.querySelectorAll('#points g[data-key]'));
     return {failed:basemapFailed,loaded:imgs.filter(i=>i.complete&&i.naturalWidth===256).length,zoom,
      aligned:markers.every(g=>{const r=filtered.find(x=>x.source_key===g.dataset.key),p=world(+r.SITE_LATITUDE,+r.SITE_LONGITUDE),c=g.querySelector('circle');
       return Math.abs(+c.getAttribute('cx')-(p[0]-cx+$('map').clientWidth/2))<.02&&Math.abs(+c.getAttribute('cy')-(p[1]-cy+$('map').clientHeight/2))<.02;})};
    });
    entry.after_pan_zoom=after;
    if(after.failed||after.loaded===0||!after.aligned)throw Error('Real tile rendering or marker alignment failed after pan/zoom');
    const image=path.join(path.dirname(output),'usgs-'+service+'.png');
    await page.locator('#map').screenshot({path:image,timeout:10000});
    entry.screenshot=path.basename(image);
    entry.passed=true;
    await page.evaluate(()=>{center=[34.10373,-117.3493];zoom=12;drawMap();});
   }catch(e){entry.error=e.message;report.errors.push(service+': '+e.message);}
  }
  report.passed=report.providers.length===3&&report.providers.every(p=>p.passed)&&!report.errors.length;
 }catch(e){report.errors.push('Setup: '+e.message);}
 finally{await browser.close();}
})().catch(e=>report.errors.push('Unexpected: '+e.message)).finally(()=>{
 fs.writeFileSync(output,JSON.stringify(report,null,2)+'\n');
 console.log(JSON.stringify({passed:report.passed,source:report.source,providers:report.providers.map(p=>({service:p.service,passed:p.passed,loaded_tiles:p.loaded_tiles,first_load_ms:p.first_load_ms,error:p.error})),errors:report.errors},null,2));
 if(!report.passed)process.exitCode=1;
});
