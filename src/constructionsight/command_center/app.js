'use strict';
const $=id=>document.getElementById(id), esc=s=>String(s==null||['NA','N/A','UNKNOWN','NULL','NONE'].includes(String(s).toUpperCase())?'—':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const nav=[['grid','Command Center'],['chart','Project Intelligence'],['pin','Site Map'],['network','Entity Network'],['file','Evidence Chains'],['','COMMERCIAL'],['target','Lead Console'],['send','Outreach'],['database','Bid Studio'],['dollar','Royalty Ledger'],['','INTELLIGENCE'],['star','Watchlist'],['source_layers','Sources & Collection']];
let activeInvestigationMapRows=[];
let data,filtered=[],selected=null,readinessFilter='',zoom=8,center=[34.05,-117.25],online=false,activePage='Command Center',watches=[],mapLayers={ready:true,review:true,not_ready:true,county:false,heat:false},includeExcluded=false,analyticFilter=null;
let basemapMode=safeMapMode(localStorage.getItem('cs:basemap')),basemapFailed=false,mapGeneration=0,tileSource=null;
const tileElements=new Map();
function setBasemap(mode){basemapMode=safeMapMode(mode);basemapFailed=false;localStorage.setItem('cs:basemap',basemapMode);drawMap();}
const colors={ready:'#38ba52',review:'#ffb000',not_ready:'#f13e44'},bandOf=r=>({ready:'high',review:'review',not_ready:'low'}[r.readiness]);
$('nav').innerHTML=nav.map(([symbol,name])=>symbol?`<button data-page="${name}" class="${name==='Command Center'?'active':''}"><em>${icon(symbol)}</em>${name}</button>`:`<small>${name}</small>`).join('');
$('nav').onclick=e=>{const b=e.target.closest('button');if(b)openWorkspace(b.dataset.page);};
$('back').onclick=()=>openWorkspace('Command Center');
function scope(r){const region=$('county').value;return !region||(region.startsWith('city:')?r.SITE_CITY===region.slice(5):r.SITE_COUNTY===region);}
function baseRows(){return data.rows.filter(r=>scope(r)&&(!r.hidden||$('show-hidden')?.checked)&&(data.mockup_parity||includeExcluded||r.project_type!=='infrastructure'));}
function point(r){const lat=Number(r.SITE_LATITUDE),lon=Number(r.SITE_LONGITUDE);return r.SITE_LATITUDE!=null&&r.SITE_LONGITUDE!=null&&Number.isFinite(lat)&&Number.isFinite(lon)&&lat>=-85&&lat<=85&&lon>=-180&&lon<=180;}
function world(lat,lon){const n=256*2**zoom,s=Math.sin(lat*Math.PI/180);return [(lon+180)/360*n,(.5-Math.log((1+s)/(1-s))/(4*Math.PI))*n];}
function inverse(x,y){const n=256*2**zoom;return [Math.atan(Math.sinh(Math.PI*(1-2*y/n)))*180/Math.PI,x/n*360-180];}
function fitBounds(){const investigationPoints=activePage==='Site Map'?activeInvestigationMapRows.flatMap(r=>(r.points||[]).map(p=>({SITE_LATITUDE:p.latitude,SITE_LONGITUDE:p.longitude}))):[];const rows=[...filtered,...investigationPoints].filter(point);if(!rows.length)return;center=[(Math.min(...rows.map(r=>+r.SITE_LATITUDE))+Math.max(...rows.map(r=>+r.SITE_LATITUDE)))/2,(Math.min(...rows.map(r=>+r.SITE_LONGITUDE))+Math.max(...rows.map(r=>+r.SITE_LONGITUDE)))/2];zoom=12;while(zoom>3){const [cx,cy]=world(...center);if(rows.every(r=>{const [x,y]=world(+r.SITE_LATITUDE,+r.SITE_LONGITUDE);return Math.abs(x-cx)<$('map').clientWidth/2-24&&Math.abs(y-cy)<$('map').clientHeight/2-24;}))break;zoom--;}drawMap();saveMapView();}
let viewTimer;function saveMapView(){if(data?.read_only)return;clearTimeout(viewTimer);viewTimer=setTimeout(()=>api('/api/settings',{map_view:{center,zoom}}).catch(showError),250);}
function drawMap(){if(!data)return;
 const map=$('map'),w=map.clientWidth,h=map.clientHeight,[cx,cy]=world(...center),left=cx-w/2,top=cy-h/2;
 const provider=USGS_BASEMAPS[basemapMode],configured=online&&data.map_settings.url_template;
 const remoteRequested=basemapMode!=='offline'&&(Boolean(provider)||(basemapMode==='auto'&&Boolean(configured)));
 const remote=remoteRequested&&!basemapFailed,localMap=!remote&&Boolean(data.local_map);
 const template=remote&&!provider?data.map_settings.url_template:localMap?'/api/offline-map/{z}/{x}/{y}.png':null;
 const source=remote?(provider?'usgs:'+provider.service:'configured:'+template):localMap?'local:'+template:'grid';
 // Preserve existing requests and decoded images while panning within the same tiles.
 // A source change retires prior nodes and invalidates only their error callbacks.
 if(source!==tileSource){tileSource=source;mapGeneration++;tileElements.clear();$('tiles').replaceChildren();}
 const generation=mapGeneration,wanted=new Set();
 if(remote||localMap)for(const tile of mapTileGrid(center,zoom,w,h,remote&&provider?16:18)){
  const key=tile.z+'/'+tile.x+'/'+tile.y;wanted.add(key);
  let img=tileElements.get(key);
  if(!img){
   img=new Image();img.alt='';img.className=localMap?'local-tile':provider&&remote?'usgs-tile':'';
   const image=img;
   image.onerror=()=>{if(generation!==mapGeneration||!image.isConnected)return;
    if(remote&&!basemapFailed){basemapFailed=true;drawMap();}else image.hidden=true;};
   image.src=remote&&provider?usgsTileUrl(basemapMode,tile.z,tile.x,tile.y):template.replace('{z}',tile.z).replace('{x}',tile.x).replace('{y}',tile.y);
   tileElements.set(key,image);$('tiles').append(image);
  }
  img.style.left=tile.left+'px';img.style.top=tile.top+'px';
  img.style.width=tile.size+'px';img.style.height=tile.size+'px';
 }
 for(const [key,img] of tileElements)if(!wanted.has(key)){img.remove();tileElements.delete(key);}
 if(typeof renderBasemap==='function')renderBasemap(center,zoom,mapLayers);
 const attribution=remote&&provider?'<a href="https://www.usgs.gov/programs/national-geospatial-program/national-map" target="_blank" rel="noopener">USGS The National Map</a> · '+esc(provider.attribution):remote?esc(data.map_settings.attribution):localMap?'<a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">© OpenStreetMap contributors · ODbL</a> · local regional map (outside coverage: grid)':'Offline coordinate grid · WGS84 source points';
 $('attribution').innerHTML=(basemapFailed&&remoteRequested?'USGS / provider unavailable · offline fallback · ':'')+attribution;
 const scale=mapScaleBar(center[0],zoom),scaleNode=$('map-scale');scaleNode.hidden=Boolean(data.mockup_parity);scaleNode.style.width=scale.pixels+'px';scaleNode.textContent=scale.label;
 renderHighwayShields(localMap?data.local_map.shields:[],left,top,w,h);
 $('map-overlay').hidden=true;if(selected&&point(selected)){const [mx,my]=world(+selected.SITE_LATITUDE,+selected.SITE_LONGITUDE),px=mx-left,py=my-top;if(px>=0&&px<w&&py>=0&&py<h){$('map-overlay').hidden=false;$('map-overlay').style.left=Math.min(px+10,w-195)+'px';$('map-overlay').style.top=Math.max(py-59,8)+'px';$('map-overlay').innerHTML=`<button id="popup-open"><b>${esc(selected.SITE_NAME)}</b><small>${esc(selected.project_type[0].toUpperCase()+selected.project_type.slice(1))} · ${selected.size_sf==null?'—':(selected.size_sf/1000).toFixed(0)+'K SF'}</small>${icon('chevron')}</button>`;}}
 document.querySelector('.legend').innerHTML=['ready','review','not_ready'].map(k=>`<div class="legend-line"><span class="dot ${bandOf({readiness:k})}"></span>${{ready:'Ready for Outreach',review:'In Review',not_ready:'Not Ready'}[k]} (${filtered.filter(r=>r.readiness===k).length})</div>`).join('');
 $('points').setAttribute('viewBox',`0 0 ${w} ${h}`);let mapped=0;
 $('points').innerHTML=filtered.filter(r=>point(r)&&mapLayers[r.readiness]).map(r=>{const [x,y]=world(+r.SITE_LATITUDE,+r.SITE_LONGITUDE),px=x-left,py=y-top;if(px<0||px>w||py<0||py>h)return '';mapped++;const chosen=r===selected,c=chosen?'#ffb000':colors[r.readiness];return `<g data-key="${esc(r.source_key)}" tabindex="0" role="button" aria-label="Select ${esc(r.SITE_NAME)}"><circle cx="${px}" cy="${py}" r="${chosen?16:11}" fill="${c}22" stroke="${c}88" stroke-width="1.5"/><circle cx="${px}" cy="${py}" r="${chosen?10:7.5}" fill="${c}" stroke="#232a23" stroke-width="2"/></g>`;}).join('');
 $('map-coverage').hidden=Boolean(data.mockup_parity);$('map-coverage').textContent=`${mapped} visible · ${filtered.filter(point).length} geolocated · ${filtered.length-filtered.filter(point).length} without coordinates`;
 // Investigation points are source claims, not verified sites or commercial leads.
 // Render only within the full Site Map workspace, preserving approved mockup parity.
 if(activePage==='Site Map'&&!data.mockup_parity){
  let claimedVisible=0,claimedMapped=0;
  for(const record of activeInvestigationMapRows){
   for(const location of record.points||[]){
    const lat=location.latitude,lon=location.longitude;
    if(typeof lat!=='number'||typeof lon!=='number'||!Number.isFinite(lat)||!Number.isFinite(lon)||Math.abs(lat)>85||Math.abs(lon)>180)continue;
    claimedMapped++;
    const [x,y]=world(lat,lon),px=x-left,py=y-top;
    if(px<0||px>w||py<0||py>h)continue;
    claimedVisible++;
    const id=esc(record.investigation_id);
    const label=esc(record.title||record.investigation_id);
    $('points').insertAdjacentHTML('beforeend',
     '<g data-investigation-id="'+id+'" role="button" tabindex="0" aria-label="Source-claimed investigation: '+label+'">'+
     '<title>Source-claimed point · identity and construction unverified</title>'+
     '<path d="M'+px+' '+(py-12)+'L'+(px+12)+' '+py+'L'+px+' '+(py+12)+'L'+(px-12)+' '+py+'Z" fill="#ffb00033" stroke="#ffb000" stroke-width="2"/>'+
     '<circle cx="'+px+'" cy="'+py+'" r="3" fill="#fff2b7"/></g>');
   }
  }
  const unmapped=activeInvestigationMapRows.filter(r=>!(r.points||[]).some(p=>typeof p.latitude==='number'&&typeof p.longitude==='number'&&Number.isFinite(p.latitude)&&Number.isFinite(p.longitude)&&Math.abs(p.latitude)<=85&&Math.abs(p.longitude)<=180)).length;
  $('map-coverage').textContent+=' · '+claimedVisible+' visible source-claimed investigation points ('+claimedMapped+' on page) · '+unmapped+' investigations unmapped on page';
 }
 $('attribution').insertAdjacentHTML('afterbegin',`${mapped} visible points · `);if(mapLayers.heat){$('points').insertAdjacentHTML('afterbegin',filtered.filter(point).map(r=>{const[x,y]=world(+r.SITE_LATITUDE,+r.SITE_LONGITUDE);return `<circle cx="${x-left}" cy="${y-top}" r="28" fill="#ffb00015" style="pointer-events:none"/>`;}).join(''));}
}
$('points').onclick=e=>{const investigation=e.target.closest('[data-investigation-id]');if(investigation){perform(()=>openInvestigationDossier(investigation.dataset.investigationId));return;}const r=filtered.find(x=>x.source_key===e.target.closest('[data-key]')?.dataset.key);if(r)choose(r);};$('points').onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();e.target.dispatchEvent(new MouseEvent('click',{bubbles:true}));}};
$('zoom-in').onclick=()=>{zoom=Math.min(18,zoom+1);drawMap();saveMapView();};$('zoom-out').onclick=()=>{zoom=Math.max(3,zoom-1);drawMap();saveMapView();};
let drag; $('map').onpointerdown=e=>{if(e.target.closest('button,[data-key],[data-investigation-id],a'))return;drag={x:e.clientX,y:e.clientY,origin:world(...center)};$('map').setPointerCapture(e.pointerId);};$('map').onpointermove=e=>{if(!drag)return;const scale=Number(document.documentElement.style.getPropertyValue('--shell-scale'));center=inverse(drag.origin[0]-(e.clientX-drag.x)/scale,drag.origin[1]-(e.clientY-drag.y)/scale);drawMap();};$('map').onpointerup=()=>{if(drag){drag=null;saveMapView();}};
function dossier(r){if(!r){$('dossier').innerHTML='<p class="stub-small">No matching leads.</p>';return;}
 const fields=[['Project ID','project_id',r.project_id||r.WDID||r.APP_ID],['Stage','stage',r.stage],['Permit Type','permit_type',r.permit_type],['Size','size_sf',r.size_sf==null?'—':Number(r.size_sf).toLocaleString()+' SF'],['Est. Value','value',r.value==null?'—':'$'+Number(r.value).toLocaleString()],['Owner','OWNER_NAME',r.OWNER_NAME],['Architect','architect',r.architect],['General Contractor','contractor',r.contractor],['Permit Date','permit_date',r.permit_date]];
 $('dossier-status').innerHTML=`<span class="status-dot"></span>${{ready:'READY FOR OUTREACH',review:'IN REVIEW',not_ready:'NOT READY'}[r.readiness]}`;$('dossier-status').style.color=colors[r.readiness];
 $('dossier').innerHTML=`<div class="project-visual">${data.mockup_parity?'<img src="/parity-photo.png" alt="Demo project image">':r.photo?`<img src="/api/photo/${encodeURIComponent(r.source_key)}" alt="User-uploaded site photograph">`:'PROJECT IMAGE —'}</div><div class="dossier-content"><h2>${esc(r.SITE_NAME)}</h2><div class="location">${icon('pin')} ${esc(r.SITE_CITY)}, CA <span class="type-pill">${esc(r.project_type).toUpperCase()}</span></div><dl>${fields.map(([label,key,value])=>`<dt>${label}</dt><dd title="${esc(data.demo?'Demo fixture':r.field_sources?.[key]?.source||(value==null?'Unknown':'SMARTS source claim'))}">${esc(value)}</dd>`).join('')}</dl><div class="lead-actions"><button class="amber-button" id="add-outreach" ${r.do_not_contact||r.feedback?.status==='Not a fit'?'disabled':''}>${icon('send')} ${r.outreach_queued?'Added to Outreach':'Add to Outreach'}</button><button id="edit-lead">View Full Dossier ${icon('arrow')}</button></div></div>`;
}
function choose(r){selected=r;dossier(r);drawTable();drawMap();}
function drawTable(){const chunk=filtered.slice(0,5);$('leads').innerHTML=chunk.map(r=>`<tr data-key="${esc(r.source_key)}" tabindex="0" class="${r===selected?'selected':''}"><td><span class="dot ${bandOf(r)}"></span>${esc(r.SITE_NAME)}</td><td>${esc(r.SITE_CITY)}, CA</td><td>${esc(r.project_type[0].toUpperCase()+r.project_type.slice(1))}</td><td><span class="status-pill ${(r.table_stage||r.stage)==='Permit Issued'?'ready':(r.table_stage||r.stage)==='On Hold'?'hold':''}" title="${esc(r.field_sources?.stage?.source||'Source-claimed stage')}">${esc(r.table_stage||r.stage)}</span></td><td>${r.value==null?'—':'$'+(r.value/1000000).toFixed(1)+'M'}</td><td>${esc(r.added_label||(r.first_seen?new Date(r.first_seen).toLocaleDateString('en-US',{month:'short',day:'numeric'}):'—'))}</td></tr>`).join('')||'<tr><td colspan="6">No matching source records.</td></tr>';$('contact-summary').hidden=data.mockup_parity;$('contact-summary').textContent=`Contact found ${filtered.filter(r=>r.sourced_contacts?.length).length} · No contact ${filtered.filter(r=>!r.sourced_contacts?.length).length}`;$('count').textContent=data.mockup_parity?`${filtered.length.toLocaleString()} leads`:`${filtered.length.toLocaleString()} leads · ${filtered.filter(r=>r.sourced_contacts?.length).length} Contact found · ${filtered.filter(r=>!r.sourced_contacts?.length).length} No contact`;}
$('leads').onclick=e=>{const r=filtered.find(r=>r.source_key===e.target.closest('tr')?.dataset.key);if(r)choose(r);};$('leads').onkeydown=e=>{if(e.key==='Enter')e.target.dispatchEvent(new MouseEvent('click',{bubbles:true}));};
function apply(){if(!data)return;const type=$('type').value,band=$('band').value,status=$('status-filter').value,fresh=$('freshness').value,q=$('console-search')?.value.toLowerCase()||'';filtered=baseRows().filter(r=>(!analyticFilter||analyticMatch(r))&&(!readinessFilter||(readinessFilter==='new'?r.new_week:r.readiness===readinessFilter))&&(!type||r.project_type===type)&&(!band||r.fit_band===band)&&(!status||r.feedback?.status===status)&&(!fresh||(fresh==='today'?r.new_today:r.is_new))&&(!q||JSON.stringify(r).toLowerCase().includes(q)));filtered.sort((a,b)=>data.mockup_parity?(a.display_order-b.display_order):String(b.first_seen||'').localeCompare(String(a.first_seen||'')));renderKpis();if(!filtered.some(r=>r.source_key===selected?.source_key))selected=filtered[0]||null;else selected=filtered.find(r=>r.source_key===selected.source_key);drawTable();dossier(selected);drawMap();if(activePage==='Lead Console')renderConsole();}
for(const id of ['county','type','band','freshness','status-filter'])$(id).onchange=()=>{localStorage.setItem('cs:'+id,$(id).value);apply();refreshChrome();if(activePage!=='Command Center'&&activePage!=='Lead Console')openWorkspace(activePage);};
function fitShell(){const scale=Math.min(innerWidth/1672,innerHeight/941),shell=$('app-shell');shell.style.transform=`scale(${scale})`;shell.style.left=((innerWidth-1672*scale)/2)+'px';shell.style.top=((innerHeight-941*scale)/2)+'px';document.documentElement.style.setProperty('--shell-scale',scale);drawMap();}fitShell();window.addEventListener('resize',fitShell);
function renderKpis(){const rows=baseRows(),n=rows.length,counts={total:n,ready:rows.filter(r=>r.readiness==='ready').length,review:rows.filter(r=>r.readiness==='review').length,not_ready:rows.filter(r=>r.readiness==='not_ready').length,new:rows.filter(r=>r.new_week).length};$('kpis').innerHTML=[['file','Total Opportunities','total'],['dot','Ready for Outreach','ready','high'],['dot','In Review','review','review'],['dot','Not Ready','not_ready','low'],['calendar','New This Week','new']].map(([glyph,label,key,band])=>{const delta=data.mockup_parity?(key==='total'?12:key==='new'?27:null):data.deltas?.[$('county').value||'all']?.[key];const secondary=band?`${n?Math.floor(counts[key]/n*100)+'%':'—'} of total`:`<span class="delta">${delta==null?'—':icon('up')+' '+(delta>=0?'+':'')+delta+'%'}</span><br>vs. ${key==='new'?'last week':'last 30 days'}`;return `<button class="kpi" data-kpi="${key}" title="${esc(data.readiness_rule)}"><span class="symbol">${glyph==='dot'?'<span class="dot '+band+'"></span>':icon(glyph)}</span><div><label>${label}</label><strong>${counts[key].toLocaleString()}</strong><span class="secondary">${secondary}</span></div>${band?icon('chevron').replace('class="icon"','class="icon chevron"'):''}</button>`;}).join('');}
$('kpis').onclick=e=>{const b=e.target.closest('[data-kpi]');if(b){readinessFilter=b.dataset.kpi==='total'?'':b.dataset.kpi;apply();}};
$('dossier').onclick=e=>{if(e.target.closest('#edit-lead')&&selected)openDossier(selected.source_key,'facts',true);if(e.target.closest('#add-outreach')&&selected)perform(async()=>{await api('/api/outreach/'+encodeURIComponent(selected.source_key),{});await reload();});};
$('map-overlay').onclick=e=>{if(e.target.closest('button')&&selected)openDossier(selected.source_key,'facts',true);};$('dossier-menu').onclick=()=>{if(selected)openMenu(selected);};$('view-leads').onclick=()=>openWorkspace('Lead Console');$('view-watches').onclick=()=>openWorkspace('Watchlist');$('layers').onclick=()=>openLayers();
$('notifications').onclick=()=>openNotifications();$('workspace-menu').onclick=()=>openSettings();$('search').oninput=()=>showSearch();$('search').onclick=()=>showSearch();document.addEventListener('keydown',e=>{if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){e.preventDefault();$('search').focus();showSearch();}});
document.querySelectorAll('[data-icon]').forEach(el=>el.innerHTML=icon(el.dataset.icon));
async function reload(){data=await api('/api/leads');$('demo-label').hidden=!data.demo;$('warning').hidden=!data.warning;$('warning').textContent=data.warning||'';if(data.mockup_parity){zoom=10.12;center=[34.04885,-117.25125];$('operator-name').textContent='Jordan Smith';$('operator-role').textContent='Operations';$('avatar').textContent='JS';$('unread-dot').hidden=false;}else{const profile=data.settings?.profile;for(const[id,key]of [['operator-name','name'],['operator-role','role']])$(id).textContent=profile?.[key]||'—';$('avatar').textContent=profile?.name?.split(/\s+/).map(w=>w[0]).slice(0,2).join('').toUpperCase()||'—';}apply();await refreshChrome();}
async function boot(){await document.fonts.ready;data=await api('/api/leads');const regions=[...new Set(data.rows.map(r=>r.SITE_COUNTY).filter(Boolean))].sort(),cities=[...new Set(data.rows.map(r=>r.SITE_CITY).filter(v=>v&&!['NA','N/A'].includes(v)))].sort();$('county').innerHTML=`<option value="">${data.mockup_parity?'Riverside, CA':'All regions'}</option>`+regions.map(r=>`<option value="${esc(r)}">${esc(r)}</option>`).join('')+cities.map(r=>`<option value="city:${esc(r)}">${esc(r)}, CA</option>`).join('');$('status-filter').innerHTML='<option value="">All statuses</option>'+data.statuses.map(s=>`<option>${esc(s)}</option>`).join('');for(const id of ['freshness','status-filter','county','type','band'])$(id).value=localStorage.getItem('cs:'+id)||'';if(!localStorage.getItem('cs:county'))$('county').value=data.settings?.profile.default_region||'';if(data.settings?.map_view){center=data.settings.map_view.center;zoom=data.settings.map_view.zoom;}online=Boolean(data.map_settings.url_template);await reload();drawMap();document.documentElement.dataset.ready='true';}
window.addEventListener('DOMContentLoaded',()=>boot().catch(showError));
