'use strict';
async function api(path,payload){const r=await fetch(path,payload===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});if(!r.ok){const text=await r.text();throw Error(text.match(/<p>Message: ([\s\S]*?)<\/p>/)?.[1]||`Request failed (${r.status})`);}return r.json();}
function showError(e){$('warning').hidden=false;$('warning').textContent=e.message||String(e);}
function perform(task){return Promise.resolve().then(task).catch(showError);}
const blank=v=>v==null?'':String(v),keyPath=(family,key)=>'/api/'+family+'/'+encodeURIComponent(key),moneyText=n=>n==null?'—':'$'+(n/100).toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2});
function download(name,value){const a=document.createElement('a');a.download=name;a.href=URL.createObjectURL(new Blob([typeof value==='string'?value:JSON.stringify(value,null,2)],{type:name.endsWith('.csv')?'text/csv':'application/json'}));a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);}
function field(name,label,value='',type='text',required=false){return `<label>${esc(label)}${type==='textarea'?`<textarea name="${name}" ${required?'required':''}>${esc(blank(value))}</textarea>`:`<input name="${name}" type="${type}" value="${esc(blank(value))}" ${required?'required':''}>`}</label>`;}
function options(name,values,value='',label=name){return `<label>${esc(label)}<select name="${name}">${values.map(v=>{const [val,text]=Array.isArray(v)?v:[v,v];return `<option value="${esc(val)}" ${val===value?'selected':''}>${esc(text)}</option>`;}).join('')}</select></label>`;}
function table(headers,rows){return `<table class="workspace-table"><thead><tr>${headers.map(h=>`<th>${esc(h)}</th>`).join('')}</tr></thead><tbody>${rows.map(r=>`<tr>${r.map(cell=>`<td>${cell}</td>`).join('')}</tr>`).join('')}</tbody></table>`;}
let modalTicket=0;
function modal(title,content){currentInvestigationIdentity=null;modalTicket++;$('action-title').textContent=title;$('action-content').innerHTML=content;if(!$('action-dialog').open)$('action-dialog').showModal();return modalTicket;}
$('action-close').onclick=()=>{modalTicket++;$('action-dialog').close();};
$('action-dialog').addEventListener('cancel',()=>modalTicket++);
function bindForm(id,submit){const form=$(id);if(!form)return;form.onsubmit=e=>{e.preventDefault();const button=form.querySelector('button[type=submit]');if(button)button.disabled=true;perform(()=>submit(Object.fromEntries(new FormData(form)))).finally(()=>{if(button?.isConnected)button.disabled=false;});};if(data?.read_only){form.querySelectorAll('input,textarea,select,button[type=submit]').forEach(e=>e.disabled=true);form.insertAdjacentHTML('beforeend','<p>Demo · isolated read-only fixture</p>');}}
document.addEventListener('click',e=>{const b=e.target.closest('[data-open]');if(b)openDossier(b.dataset.open);});
async function refreshChrome(){watches=data.mockup_parity?data.parity_watches:await api('/api/watchlist');watches=watches.filter(w=>scope(w.row));$('watchlist-summary').innerHTML=watches.slice(0,4).map(w=>`<button class="watch-row" data-open="${esc(w.source_key)}"><span class="dot ${w.color||(w.changed?'review':w.due?'low':'high')}"></span><b>${esc(w.row.SITE_NAME)}</b><span title="${esc(w.remind_on)}">${esc(w.note||w.source_state)}</span><time>${esc(w.age||age(w.updated_at))}</time></button>`).join('')||'<p>No saved reminders.</p>';if(!data.read_only)await refreshNotificationIndicator();}
let notificationRefresh = null;
async function refreshNotificationIndicator(){
 if(data.read_only||notificationRefresh)return notificationRefresh;
 const snapshot=data;
 notificationRefresh=(async()=>{
  try{
   const notices=await api('/api/notifications');
   if(data!==snapshot)return;
   $('unread-dot').hidden=!notices.some(n=>!n.read&&noticeScope(n));
   $('notifications').title='Notifications';
  }catch(error){
   if(data===snapshot)$('notifications').title='Notifications: refresh unavailable';
  }finally{notificationRefresh=null;}
 })();
 return notificationRefresh;
}
function age(at){const seconds=Math.max(0,(Date.now()-Date.parse(at))/1000);if(!Number.isFinite(seconds))return '—';return seconds<3600?Math.floor(seconds/60)+'m ago':seconds<86400?Math.floor(seconds/3600)+'h ago':Math.floor(seconds/86400)+'d ago';}
function noticeScope(n){const region=$('county').value;return !region||!n.county||(region.startsWith('city:')?n.city===region.slice(5):n.county===region);}
async function openNotifications(){
 const openingTicket=modalTicket;
 const items=data.read_only?[]:(await api('/api/notifications')).filter(noticeScope);
 if(openingTicket!==modalTicket)return;
 modal('Notifications',`<button id="mark-read" ${data.read_only?'disabled':''}>Mark all as read</button>`+items.map((n,i)=>`<p class="notice ${n.read?'read':''}">${n.investigation_id?`<button data-investigation-notice="${i}">${esc(n.message)}</button>`:n.record_kind?`<button data-source-notice="${i}">${esc(n.message)}</button>`:n.source_key?`<button data-open="${esc(n.source_key)}">${esc(n.message)}</button>`:esc(n.message)} <small>${n.read?'Read':'Unread'}</small></p>`).join('')+(!items.length?'<p>No new leads, due reminders, failed runs or unreviewed source changes.</p>':''));
 const ticket=modalTicket;
 document.querySelectorAll('[data-investigation-notice]').forEach(button=>{
  button.onclick=()=>perform(()=>openInvestigationDossier(
   items[Number(button.dataset.investigationNotice)].investigation_id));
 });
 document.querySelectorAll('[data-source-notice]').forEach(button=>{
  button.onclick=()=>perform(()=>openRetainedSourceNotice(items[Number(button.dataset.sourceNotice)]));
 });
 $('mark-read').onclick=()=>perform(async()=>{
  await api('/api/notifications/read',{ids:items.map(n=>n.id)});
  await refreshChrome();
  if(ticket===modalTicket&&$('action-dialog').open)await openNotifications();
 });
}
async function openSettings(){const s=data.settings;if(!s){modal('User settings','<p>Demo · settings are isolated from your real data.</p>');return;}modal('User settings',`<form id="settings-form" class="form-grid">${field('name','Name',s.profile.name)}${field('role','Role',s.profile.role)}${field('company','Company',s.profile.company)}${options('default_region',[['','All'],...Array.from($('county').options).slice(1).map(o=>[o.value,o.textContent])],s.profile.default_region,'Default region')}<h3>Scoring weights</h3>${Object.entries(s.weights).map(([k,v])=>field('weight:'+k,k,v,'number')).join('')}<h3>Map provider</h3>${field('map_url','Authorized HTTPS tile URL with {z}, {x}, {y}',s.map.url_template)}${field('map_attribution','Provider attribution',s.map.attribution)}<p>Data folder: <code>${esc(s.data_folder)}</code></p><p><a href="/api/backup.zip" download="ConstructionSight-backup.zip">Download backup</a> · <a href="/api/export.csv" download="leads.csv">Export leads</a></p><button type="submit">Save settings</button></form><h3>Data folder</h3><form id="folder-form" class="form-grid">${field('directory','New empty folder (absolute path)','')}<p>The current folder is preserved. The next launch follows the saved location.</p><button>Relocate and verify</button></form><h3>Local OSM map</h3><p>Geofabrik public extract; ODbL attribution remains visible. Core Inland Empire region, native zoom 6–13; outside coverage uses the grid. Optional authorized tile URL above can include your own provider key.</p><input id="map-archive" type="file" accept=".pmtiles">${field('map-sha','Archive SHA-256 from build report','')}<button id="install-map">Install verified local map</button><p id="map-install-report"></p><h3>Restore backup</h3><input id="restore-file" type="file" accept=".zip,application/zip"><button id="restore-preview">Dry-run restore</button><p id="restore-report">Choose a backup to check hashes, JSON, SQLite and source evidence before restoring.</p><button id="restore-apply" disabled>Apply reviewed restore</button>`);$('install-map').onclick=async()=>{try{const file=$('map-archive').files[0];if(!file)throw Error('Choose the locally built PMTiles archive');const r=await fetch('/api/offline-map-install',{method:'POST',headers:{'Content-Type':'application/octet-stream','X-Archive-SHA256':document.querySelector('[name="map-sha"]').value.trim()},body:file});if(!r.ok)throw Error(await r.text());await reload();$('map-install-report').textContent='Local map installed and hash verified';drawMap();}catch(e){$('map-install-report').textContent=e.message;}};let restoreToken=null;$('restore-file').onchange=()=>{restoreToken=null;$('restore-apply').disabled=true;};$('restore-preview').onclick=async()=>{try{const file=$('restore-file').files[0];if(!file)throw new Error('Choose a backup first');$('restore-preview').disabled=true;const r=await fetch('/api/restore-preview',{method:'POST',headers:{'Content-Type':'application/zip'},body:file});if(!r.ok)throw new Error(await r.text());const report=await r.json();restoreToken=report.archive_sha256;$('restore-report').textContent=`Dry run passed: ${report.files_verified} files; hashes and database integrity checked. Current data unchanged. SHA-256: ${restoreToken}`;$('restore-apply').disabled=false;}catch(e){$('restore-report').textContent=e.message;}finally{$('restore-preview').disabled=false;}};$('restore-apply').onclick=async()=>{try{await api('/api/restore-apply',{token:restoreToken});$('action-dialog').close();await reload();}catch(e){$('restore-report').textContent=e.message;}};bindForm('folder-form',async f=>{await api('/api/data-folder',{directory:f.directory});$('action-dialog').close();await reload();});bindForm('settings-form',async f=>{const weights=Object.fromEntries(Object.keys(s.weights).map(k=>[k,Number(f['weight:'+k])]));await api('/api/settings',{profile:{name:f.name,role:f.role,company:f.company,default_region:f.default_region},weights,map:{url_template:f.map_url||null,attribution:f.map_attribution||null}});$('action-dialog').close();await reload();online=Boolean(data.map_settings.url_template);drawMap();});}
let searchResults=[],searchIndex=0;
function showSearch(){investigationSearchTicket++;const q=$('search').value.trim().toLowerCase(),groups=['Leads','Developers / owners','Cities / identifiers','Contacts','Notes'],items=[];for(const r of baseRows()){if(!q||String(r.SITE_NAME||'').toLowerCase().includes(q))items.push({r,group:groups[0]});else if([r.OWNER_NAME,r.DEVELOPER_NAME].join(' ').toLowerCase().includes(q))items.push({r,group:groups[1]});else if([r.SITE_CITY,r.WDID,r.APP_ID,r.project_id].join(' ').toLowerCase().includes(q))items.push({r,group:groups[2]});else if(JSON.stringify(r.sourced_contacts).toLowerCase().includes(q))items.push({r,group:groups[3]});else if(String(r.feedback?.notes||'').toLowerCase().includes(q))items.push({r,group:groups[4]});}searchResults=items.slice(0,50);searchIndex=0;$('search-results').hidden=false;$('search-results').innerHTML=groups.map(g=>{const matching=searchResults.map((v,i)=>({...v,i})).filter(v=>v.group===g);return matching.length?`<h4>${g}</h4>`+matching.map(({r,i})=>`<button role="option" data-search-index="${i}" aria-selected="${i===0}"><b>${esc(r.SITE_NAME)}</b> <span>${esc(r.SITE_CITY)} · ${esc(r.WDID||r.APP_ID)}</span></button>`).join(''):'';}).join('')||'<p>No matching commercial leads.</p>';$('search').setAttribute('aria-expanded','true');appendInvestigationSearch(q);}
$('search-results').onclick=e=>{const b=e.target.closest('[data-search-index]');if(b){const item=searchResults[Number(b.dataset.searchIndex)];hideSearch();if(item.investigation)perform(()=>openInvestigationDossier(item.investigation));else openDossier(item.r.source_key);}};
function hideSearch(){investigationSearchTicket++;$('search-results').hidden=true;$('search').setAttribute('aria-expanded','false');}
$('search').onkeydown=e=>{if(e.key==='Escape'){hideSearch();return;}if(['ArrowDown','ArrowUp'].includes(e.key)){e.preventDefault();searchIndex=Math.max(0,Math.min(searchResults.length-1,searchIndex+(e.key==='ArrowDown'?1:-1)));document.querySelectorAll('[data-search-index]').forEach(b=>b.setAttribute('aria-selected',Number(b.dataset.searchIndex)===searchIndex));$('search-results').querySelector('[aria-selected=true]')?.scrollIntoView({block:'nearest'});}if(e.key==='Enter'&&searchResults.length){e.preventDefault();hideSearch();const item=searchResults[searchIndex];if(item.investigation)perform(()=>openInvestigationDossier(item.investigation));else openDossier(item.r.source_key);}};
document.addEventListener('click',e=>{if(!e.target.closest('.search,#search-results'))hideSearch();});
const factLabels={SITE_NAME:'Project name',SITE_CITY:'City',SITE_COUNTY:'County',OWNER_NAME:'Owner',DEVELOPER_NAME:'Developer',project_id:'Project ID',project_type:'Type',stage:'Stage',permit_type:'Permit type',size_sf:'Square feet',value:'Project value (USD)',architect:'Architect',contractor:'General contractor',permit_date:'Permit date',SITE_LATITUDE:'Latitude',SITE_LONGITUDE:'Longitude'};
async function openDossier(key,tab='facts',asPage=false){currentInvestigationIdentity=null;const request=++modalTicket;let lead;try{lead=await api(keyPath('lead',key));}catch(e){showError(e);return;}if(request!==modalTicket)return;selected=data.rows.find(r=>r.source_key===key)||lead;choose(selected);const tabs=['facts','contacts','notes','activity','evidence','outreach','bids','royalty'];const content=`<div class="tool-tabs">${tabs.map(t=>`<button data-dossier-tab="${t}" class="${t===tab?'active':''}">${t[0].toUpperCase()+t.slice(1)}</button>`).join('')}</div><div id="dossier-tab"></div>`;if(asPage){$('action-dialog').close();await openWorkspace('Project Dossier');$('stub-title').textContent=lead.SITE_NAME||'—';$('section-content').innerHTML=content;}else modal(lead.SITE_NAME||'—',content);document.querySelectorAll('[data-dossier-tab]').forEach(b=>b.onclick=()=>openDossier(key,b.dataset.dossierTab,asPage));const box=$('dossier-tab');
 if(tab==='facts'){box.innerHTML=`<button id="upload-photo">Upload site photograph</button><form id="facts-form" class="form-grid">${Object.entries(factLabels).map(([k,label])=>`<div title="${esc(lead.field_sources?.[k]?.source||'SMARTS source claim')}">${k==='project_type'?options(k,['unknown','industrial','commercial','residential','infrastructure'],lead[k],label):field(k,label,lead[k],k==='permit_date'?'date':'text')}<small>${esc(lead.field_sources?.[k]?.source||(lead[k]==null?'Unknown':'SMARTS source claim'))}${k==='project_type'&&lead.field_sources?.[k]?.confidence!=null?' · confidence '+esc(lead.field_sources[k].confidence)+' · unverified':''}${k==='project_type'&&lead.project_subtype?' · '+esc(lead.project_subtype):''}</small></div>`).join('')}<label class="check"><input name="site_verified" type="checkbox" ${lead.site_verified?'checked':''}>I verified this physical site</label><p>Edited facts are saved with provenance “Entered by user”. Empty values remove a local override.</p><button type="submit">Save facts</button></form>`;$('upload-photo').onclick=()=>photoForm(key);bindForm('facts-form',async f=>{const changed={};for(const k of Object.keys(factLabels))if(f[k]!==blank(lead[k]))changed[k]=f[k];const verified=$('facts-form').elements.site_verified.checked;if(verified!==Boolean(lead.site_verified))changed.site_verified=verified;await api(keyPath('facts',key),changed);await reload();if($('action-dialog').open||(asPage&&activePage==='Project Dossier'))openDossier(key,tab,asPage);});}
 else if(tab==='contacts'){box.innerHTML=`<button id="import-source-contacts" ${data.read_only?'disabled':''}>Import hash-verified SMARTS contacts</button><p>Source-reported regulatory contacts; purchasing authority remains unverified.</p>`+table(['Name / role','Company','Email','Phone','Priority / why','Source'],(lead.sourced_contacts||[]).map(c=>[esc([c.name,c.role].filter(Boolean).join(' · ')),esc(c.company),esc(c.email),esc(c.phone),`${esc(c.reliability_score)} / 100 · ${esc((c.reliability_reasons||[]).join("; "))}`,esc(c.source)]))+`<form id="contact-form" class="form-grid"><h3>Add a sourced contact</h3>${['name','role','company','email','phone','source'].map(k=>field(k,k,'',k==='email'?'email':'text',k==='source')).join('')}<p>A source and at least one actual email or phone number are required.</p><button type="submit">Save contact</button></form>`;$('import-source-contacts').onclick=()=>perform(async()=>{const b=$('import-source-contacts');b.disabled=true;try{await api(keyPath('smarts-contacts',key),{});await reload();if($('action-dialog').open||(asPage&&activePage==='Project Dossier'))openDossier(key,tab,asPage);}finally{if(b.isConnected)b.disabled=false;}});bindForm('contact-form',async f=>{await api(keyPath('contacts',key),f);await reload();if($('action-dialog').open||(asPage&&activePage==='Project Dossier'))openDossier(key,tab,asPage);});}
 else if(tab==='notes'){const f=lead.feedback||{};box.innerHTML=`<form id="notes-form" class="form-grid">${options('status',data.statuses,f.status||'New','Status')}${field('notes','Notes',f.notes,'textarea')}${field('last_contacted','Last contacted',f.last_contacted,'date')}${options('reason_code',[['','—'],...data.reasons],f.reason_code||'','Loss / exclusion reason')}${field('reason_text','Additional reason',f.reason_text,'textarea')}<button type="submit">Save status and notes</button></form>`;bindForm('notes-form',async values=>{await api(keyPath('feedback',key),values);await reload();if($('action-dialog').open||(asPage&&activePage==='Project Dossier'))openDossier(key,tab,asPage);});}
 else if(tab==='activity')box.innerHTML=table(['When','Action','Details'],lead.activity.map(e=>[esc(new Date(e.at).toLocaleString()),esc(e.kind),esc(JSON.stringify(e.data))]));
 else if(tab==='evidence'){const evidence=await api(keyPath('evidence',key));box.innerHTML=`<p>Source: California SMARTS · capture ${esc(data.captured_at)}</p><p>Row SHA-256: <code>${esc(lead.row_sha256)}</code></p><p>Response SHA-256: <code>${esc(lead.response_sha256)}</code></p><button id="verify-evidence">Verify original response hashes</button> <button id="export-evidence">Export evidence</button><p id="verify-result"></p>`+table(['Field','Value','Source'],Object.entries(factLabels).map(([k,label])=>[esc(label),esc(lead[k]),esc(lead.field_sources?.[k]?.source||(lead[k]==null?'Unknown':'SMARTS source claim'))]));$('verify-evidence').onclick=()=>perform(async()=>{const r=await api(keyPath('evidence',key)+'?verify=1');$('verify-result').textContent=r.verified?'Verified original response and source row':r.error||'Original response unavailable';});$('export-evidence').onclick=()=>download('evidence.json',evidence);}
 else if(tab==='outreach'){renderOutreachLead(lead,box);}
 else if(tab==='bids'){box.innerHTML=`<button id="lead-estimate">Create estimate</button>`+table(['Title','Version','Status','Total','Proposal'],lead.bids.map(b=>[esc(b.title),esc(b.version),esc(b.status),moneyText(b.total_minor),`<a href="/api/proposal/${esc(b.id)}" download="proposal.pdf">PDF</a>`]));$('lead-estimate').onclick=()=>{ $('action-dialog').close();openWorkspace('Bid Studio',key);};}
 else box.innerHTML=table(['Partner','Calculated','Invoiced','Collected','Receivable'],lead.royalties.map(r=>[esc(r.partner),moneyText(r.calculated_minor),moneyText(r.invoiced_minor),moneyText(r.received_minor),moneyText(r.receivable_minor)]));
}
function openMenu(lead){const key=lead.source_key;modal('Dossier actions',`<div class="action-list"><button id="menu-status">Set status / add note</button><button id="menu-watch">Watch / remind</button><button id="menu-dnc">${lead.do_not_contact?'Remove Do-Not-Contact':'Mark Do-Not-Contact'}</button><button id="menu-hide">${lead.hidden?'Show lead':'Hide lead'}</button><button id="menu-export">Export dossier</button></div>`);$('menu-status').onclick=()=>openDossier(key,'notes');$('menu-watch').onclick=()=>editWatch(key);$('menu-export').onclick=()=>download('dossier.json',lead);for(const[name,field]of [['dnc','dnc'],['hide','hidden']])$('menu-'+name).onclick=()=>perform(async()=>{await api(keyPath('control',key),{[field]:!lead[field==='dnc'?'do_not_contact':'hidden']});$('action-dialog').close();await reload();});}
function openLayers(){modal('Map layers',`<div class="action-list"><label>Basemap <select id="basemap-choice"><option value="auto" ${basemapMode==='auto'?'selected':''}>Configured provider / offline default</option><option value="offline" ${basemapMode==='offline'?'selected':''}>Offline / coordinate grid</option>${Object.entries(USGS_BASEMAPS).map(([key,source])=>`<option value="${key}" ${basemapMode===key?'selected':''}>${esc(source.label)}</option>`).join('')}</select></label><p>USGS maps use online public imagery; image dates vary by location and do not verify current construction activity.</p>${Object.entries(mapLayers).map(([k,v])=>`<label><input type="checkbox" data-map-layer="${k}" ${v?'checked':''}>${{ready:'Ready for Outreach',review:'In Review',not_ready:'Not Ready',county:'County boundaries',heat:'Lead density',investigations:'Source-claimed investigations (unverified)'}[k]}</label>`).join('')}<button id="fit-bounds">Fit to visible leads</button></div>`);$('basemap-choice').onchange=e=>setBasemap(e.target.value);document.querySelectorAll('[data-map-layer]').forEach(el=>el.onchange=()=>{mapLayers[el.dataset.mapLayer]=el.checked;drawMap();});$('fit-bounds').onclick=()=>{fitBounds();$('action-dialog').close();};}
const filterHome=$('lead-filters').parentNode,mapHome=$('map').parentNode;
async function openInvestigationDossier(identity,refresh=false){
 const ticket=++modalTicket;
 const [dossier,watch]=await Promise.all([
  api('/api/investigations/'+encodeURIComponent(identity)),
  api('/api/investigation-watch?'+new URLSearchParams({investigation_id:identity}))
   .catch(error=>({error:error.message}))
 ]);
 if(ticket!==modalTicket||refresh&&(!$('action-dialog').open||currentInvestigationIdentity!==identity))return;
 currentInvestigationIdentity=identity;investigationDossierRevision=investigationRevision(dossier);
 const scroll=refresh?$('action-content').scrollTop:0;
 const sources=dossier.source_membership||[],chronology=dossier.chronology||[];
 const info=dossier.investigation||{},assessment=dossier.assessment||{};
 const gaps=dossier.evidence_assessment?.information_gaps||[];
 const claims=dossier.evidence_assessment?.source_claim_discrepancies||[];
 const milestones=event=>(event.source_claimed_milestones||[]).map(m=>esc(m.field.replaceAll('_',' '))+': '+esc(m.date)+' (source-claimed)').join('; ')||'—';
 modal('Investigation · '+(info.project_name||identity),
  '<p>Shared retained investigation · identity independently verified: '+(assessment.identity_independently_verified?'Yes':'No')+
  ' · commercial authority: '+(assessment.commercial_authority_granted?'Yes':'No')+
  '. Context association does not establish same-project identity or construction activity.</p>'+
  '<p>Canonical investigation ID: <code>'+esc(identity)+'</code></p>'+
  '<div id="native-investigation-watch" role="status">'+
  (watch.error?'<p role="alert">Investigation watch status unavailable: '+esc(watch.error)+'</p>':
   '<p>Canonical evidence watch · '+(watch.watched?(watch.changed?'Changed; review needed':'Watching committed evidence'):'Not watched')+
   '. Source claims are not commercial authorization.</p>'+
   (watch.watched&&watch.changed?'<button data-investigation-watch-action="acknowledge">Acknowledge reviewed change</button> ':'')+
   (!watch.watched?'<button data-investigation-watch-action="watch">Watch this investigation</button>':
    '<button data-investigation-watch-action="remove">Remove investigation watch</button>'))+
  '</div>'+
  '<h3>Governed lead handoff review</h3>'+
  '<p>Assess current exact source evidence using the original opportunity and lead workflow rules. This is not commercial approval.</p>'+
  '<button id="preview-canonical-lead">Preview original governed lead assessment</button>'+
  '<div id="canonical-lead-review-result" role="status"></div>'+
  '<h3>Source membership and provenance</h3>'+
  table(['Family','Original record','Membership basis','Current evidence ID'],sources.map(m=>[
    esc(m.source_family||'—'),esc(m.source_record_id||'—'),esc(m.membership_basis||'—'),esc(m.current_evidence_id||'—')
  ]))+
  '<h3>Exact original commercial lineage</h3>'+
  '<p>Inspect historical workflow/outcome and calculated-share records only for '+
  'the current exact native source evidence. Original records do not establish '+
  'a verified project, bid authority, contractual royalty or payment.</p>'+
  '<div id="native-original-lineage">'+
  table(['Source','Recorded evidence','Inspect original workflow and outcome'],
   sources.filter(m=>['ceqa','permit'].includes(m.source_family))
    .slice(0,25).map((m,i)=>[
     esc(m.source_family+' · '+m.source_record_id),
     esc(m.current_evidence_id||'Unknown current evidence'),
     '<button data-dossier-original-source="'+i+'">Inspect exact lineage</button>'
    ]))+
  (sources.filter(m=>['ceqa','permit'].includes(m.source_family)).length>25?
   '<p>Bounded to the first 25 CEQA/permit source memberships; others are not examined.</p>':'')+
  '<div id="native-original-lineage-detail" role="status"></div></div>'+
  '<h3>Evidence chronology</h3>'+
  table(['Source','Retention time','Agency-reported milestones','Evidence revision'],chronology.map(e=>[
    esc(e.source_family||'—'),esc(e.retained_at||'—'),milestones(e),esc(e.evidence_id||'—')+(e.is_current_source_revision?' · current':' · historical')
  ]))+
  '<h3>Retained evidence artifacts</h3>'+
  (dossier.evidence||[]).map(e=>'<details><summary>'+esc(e.source_family||e.source_name)+' · '+esc(e.evidence_id)+'</summary><p>SHA-256: <code>'+esc(e.content_hash)+'</code></p><p>Source URL: '+esc(e.source_url||'—')+'</p><p>Limitations: '+esc((e.limitations||[]).join(' · ')||'—')+'</p><pre>'+esc(JSON.stringify(e.raw_observations,null,2))+'</pre></details>').join('')+
  '<h3>Source-claim discrepancies</h3><pre>'+esc(JSON.stringify(claims,null,2))+'</pre>'+
  '<h3>Source association reviews</h3>'+associationReviewActions(dossier)+'<details><summary>Candidate source details</summary><pre>'+esc(JSON.stringify(dossier.candidate_source_links||[],null,2))+'</pre></details>'+
  '<h3>Review questions</h3><p>'+esc(gaps.map(g=>g.code||g.message||'').filter(Boolean).join(' · ')||'No specific gap codes recorded.')+'</p>'+
  '<p>Current source-claim variations: '+esc(String(claims.length))+' · chronology and source previews may be bounded.</p>'+
  '<button id="export-investigation">Export retained dossier JSON</button>');
 currentInvestigationIdentity=identity;
 const displayedTicket=modalTicket;
 $('action-content').scrollTop=scroll;
 $('export-investigation').onclick=()=>download('investigation-dossier.json',dossier);
 $('preview-canonical-lead').onclick=()=>perform(async()=>{
  const button=$('preview-canonical-lead'),host=$('canonical-lead-review-result');
  if(!host||!button)return;
  button.disabled=true;
  host.textContent='Reviewing current source using original workflow rules…';
  try{
   const result=await api('/api/investigation-lead-preview?'+
    new URLSearchParams({investigation_id:identity}));
   if(displayedTicket!==modalTicket||!$('action-dialog').open)return;
   if(result.canonical_investigation_id!==(info.project_cluster_id||identity)||
      result.event_anchor!==dossier.event_anchor||
      !sources.some(s=>s.source_id===result.source_entity_id&&
       s.current_evidence_id===result.current_evidence_id)){
    host.textContent='Retained evidence changed; reopen the dossier before lead assessment.';
    return;
   }
   host.innerHTML='<p>Original review: '+esc(result.lead_review_status)+
    ' · provisional workflow: '+esc(result.provisional_workflow_status)+
    '. Human review required. Not qualified to contact or bid.</p>'+
    '<p>Exact evidence: '+esc(result.current_evidence_id)+'</p>'+
    '<p>Original pipeline limitations: '+
    esc((result.original_product_integration.review_package.limitations||[]).join(' · ')||'—')+
    '</p><p>Persisted duplicate/authority review remains required.</p>'+
    (result.existing_native_handoff?
     '<p>Already retained for review: workflow '+esc(result.existing_native_handoff.workflow_id)+
     ', status '+esc(result.existing_native_handoff.workflow_status)+
     '. No second candidate will be created.</p>':
     !result.can_retain_review_candidate?
     '<p role="alert">Existing retained lead with matching exact source or reviewed site.'+
     ' No duplicate candidate will be created. Review its original history first.</p>'+
     '<pre>'+esc(JSON.stringify(result.existing_source_or_site_matches,null,2))+'</pre>':
     '<label>Reason for keeping this candidate under human review '+
     '<textarea id="canonical-lead-review-reason" maxlength="2000"></textarea></label>'+
     '<label><input type="checkbox" id="canonical-lead-review-confirm"> '+
     'I reviewed the current evidence and only authorize retaining a nonactionable candidate.</label>'+
     '<button id="retain-canonical-lead">Retain candidate for manual review</button>')+
    '<button id="export-canonical-lead-review">Export original pipeline assessment</button>';
   const retain=$('retain-canonical-lead');
   if(retain)retain.onclick=()=>perform(async()=>{
    const reason=$('canonical-lead-review-reason')?.value.trim();
    if(!$('canonical-lead-review-confirm')?.checked||!reason){
     throw Error('Explicit confirmation and review reason are required.');
    }
    retain.disabled=true;
    try{
     const receipt=await api('/api/investigation-lead-handoff',{
      investigation_id:identity,expected_evidence_id:result.current_evidence_id,
      expected_evidence_sha256:result.current_evidence_sha256,
      expected_event_anchor:result.event_anchor,reason,caller_confirmation:true
     });
     if(displayedTicket!==modalTicket||!$('action-dialog').open)return;
     host.innerHTML='<p>Retained under existing lead workflow '+
      esc(receipt.workflow_id)+', status '+esc(receipt.workflow_status)+
      '. Human review still required. No contact or bid authorized.</p>'+
      '<pre>'+esc(JSON.stringify(receipt,null,2))+'</pre>';
    }finally{if(retain.isConnected)retain.disabled=false;}
   });
   $('export-canonical-lead-review').onclick=()=>
    download('canonical-lead-review.json',result);
  }catch(error){if(displayedTicket===modalTicket&&host.isConnected)
   host.textContent='Lead assessment unavailable: '+error.message;}
  finally{if(button.isConnected)button.disabled=false;}
 });
 document.querySelectorAll('[data-investigation-watch-action]').forEach(button=>{
  button.onclick=()=>perform(async()=>{
   button.disabled=true;
   try{
    await api('/api/investigation-watch',{
     action:button.dataset.investigationWatchAction,
     investigation_id:identity,expected_digest:watch.current_digest
    });
    if(displayedTicket===modalTicket&&$('action-dialog').open){
     await openInvestigationDossier(identity,true);
     await refreshNotificationIndicator();
    }
   }finally{if(button.isConnected)button.disabled=false;}
  });
 });
 const originalSources=sources.filter(m=>['ceqa','permit'].includes(m.source_family)).slice(0,25);
 document.querySelectorAll('[data-dossier-original-source]').forEach(button=>{
  button.onclick=()=>perform(async()=>{
   const source=originalSources[Number(button.dataset.dossierOriginalSource)];
   const detail=$('native-original-lineage-detail');
   if(!source||!detail)return;
   detail.textContent='Checking exact current source evidence against preserved operator records…';
   try{
    const params=new URLSearchParams({kind:source.source_family,record_id:source.source_record_id,limit:'20',offset:'0'});
    const result=await api('/api/source-commercial-lineage?'+params);
    if(displayedTicket!==modalTicket||!$('action-dialog').open)return;
    const exact=result.original_source?.kind===source.source_family&&
     result.original_source?.record_id===source.source_record_id&&
     result.source_entity_id===source.source_id&&
     result.native_state==='exact_observation_already_retained'&&
     result.canonical_investigation_id===(info.project_cluster_id||identity);
    if(!exact){
     detail.innerHTML='<p role="alert">Original workflow evidence does not match '+
      'the current exact source membership; no commercial context was attached. '+
      'Reload the investigation and inspect both evidence revisions before proceeding.</p>';
     return;
    }
    if(!source.current_evidence_id){
     detail.innerHTML='<p role="alert">Current native evidence identity is absent. '+
      'No original commercial context can be associated.</p>';return;
    }
    const verification=await api('/api/source-reconciliation?'+
      new URLSearchParams({kind:source.source_family,record_id:source.source_record_id}));
    if(displayedTicket!==modalTicket||!$('action-dialog').open)return;
    if(verification.native_evidence_id!==source.current_evidence_id||
       verification.native_state!=='exact_observation_already_retained'||
       verification.canonical_investigation_id!==(info.project_cluster_id||identity)||
       verification.original_source?.source_sha256!==result.original_source?.source_sha256){
     detail.innerHTML='<p role="alert">Source evidence changed or no longer '+
      'matches the dossier. Historical financial context is withheld.</p>';return;
    }
    detail.innerHTML='<h4>Exact retained original commercial context</h4>'+
      '<p>Verified only as exact source evidence and historical candidate-key lineage, '+
      'not same-project identity, contract, royalty entitlement, payment or permission to bid.</p>'+
      '<p>Matching original workflows: '+esc(result.matching_workflow_total)+
      '. Returned '+esc(result.matching_workflows?.length||0)+
      (result.has_more?' · additional records remain beyond this page.':'')+'</p>'+
      '<pre>'+esc(JSON.stringify(result,null,2))+'</pre>'+
      '<button id="export-native-source-lineage">Export exact lineage JSON</button>';
    $('export-native-source-lineage').onclick=()=>
     download('investigation-original-financial-lineage.json',result);
   }catch(error){
    if(displayedTicket===modalTicket&&$('action-dialog').open)
     detail.innerHTML='<p role="alert">Exact original lineage unavailable: '+
      esc(error.message)+'. No financial linkage was asserted.</p>';
   }
  });
 });
 bindAssociationReviews(identity);
}
function canonicalResultHistory(entry){
 const result=entry.historical_result;
 const current=result.current_revision;
 const units=value=>value===null?'not recorded':esc(value);
 return '<details data-canonical-result-history="'+esc(entry.workflow_id)+'">'+
  '<summary>'+(current?'Historical result · current revision '+esc(current.revision)+
   ': '+esc(current.status)+' · '+esc(result.revision_count)+' revisions':
   'No retained outcome')+'</summary>'+
  '<p>Immutable original result history. Integrity validation does not verify an award,'+
   ' contract, royalty entitlement or payment and grants no commercial authority.'+
   ' Only the latest revision is current. Never sum superseded shares.</p>'+
  '<p>Canonical investigation: <code>'+esc(entry.canonical_investigation_id)+
   '</code><br>Exact workflow: <code>'+esc(entry.workflow_id)+'</code><br>Review package: <code>'+
   esc(entry.original_package_id)+'</code><br>Retained handoff evidence: <code>'+
   esc(entry.original_source_evidence_id)+'</code></p>'+
  (current?'<ol>'+result.revision_history.map(revision=>'<li><strong>'+
   (revision.ledger_id===current.ledger_id?'Current':'Superseded')+' revision '+
   esc(revision.revision)+' · '+esc(revision.status)+'</strong>'+
   '<p>Gross: '+units(revision.gross_value_minor)+' minor units · Rate: '+
   units(revision.share_rate_ppm)+' millionths · Calculated share: '+
   units(revision.calculated_share_minor)+' minor units</p><pre>'+
   esc(JSON.stringify(revision,null,2))+'</pre></li>').join('')+'</ol>':
   '<p>No result ledger is retained for this exact workflow. No outcome is inferred.</p>')+
  '<button data-canonical-result-export="'+esc(entry.workflow_id)+
   '">Export validated result history</button></details>';
}
async function renderCanonicalLeadWorkflows(box){
 const section=document.createElement('section');
 section.className='feature-card';
 section.dataset.canonicalLeadWorkflows='true';
 section.innerHTML='<h3>Retained investigation lead workflows</h3>'+
  '<p role="status">Reading the preserved governed lead records…</p>';
 box.append(section);
 let offset=0;
 async function load(){
  if(!section.isConnected||activePage!=='Lead Console')return;
  section.innerHTML='<h3>Retained investigation lead workflows</h3>'+
   '<p role="status">Reading original workflow history…</p>';
  try{
   const page=await api('/api/investigation-lead-workflows?'+
    new URLSearchParams({limit:'25',offset:String(offset)}));
   if(!section.isConnected||activePage!=='Lead Console')return;
   if(page.available===false){
    section.innerHTML='<h3>Retained investigation lead workflows</h3>'+
     '<p>Shared investigation store not initialized. No retained lead count is asserted.</p>';
    return;
   }
   const rows=page.rows||[];
   section.innerHTML='<h3>Retained investigation lead workflows</h3>'+
    '<p>Original persisted lead candidates from shared investigations. Statuses are'+
    ' historical workflow states, not contact permission or bid readiness. '+
    'Current evidence is compared with the exact evidence retained at handoff.</p>'+
    table(['Investigation','Preserved status','Source continuity','Workflow / result history','Inspect'],
     rows.map(entry=>[
      esc(entry.title||entry.canonical_investigation_id),
      esc(entry.workflow_status)+' · '+esc(entry.workflow_id),
      esc(entry.source_evidence_state.replaceAll('_',' ')),
      '<details><summary>'+esc(entry.transition_count)+' events</summary>'+
       '<pre>'+esc(JSON.stringify(entry.recent_transitions,null,2))+'</pre>'+
       (entry.transitions_truncated?'<p>Earlier events retained in the original workflow store.</p>':'')+
       '</details>'+canonicalResultHistory(entry),
      '<button data-canonical-lead-dossier="'+esc(entry.canonical_investigation_id)+
       '">Open shared dossier</button>'+
       (entry.source_evidence_state==='current_source_observation'&&
        ['hold','monitor','review'].includes(entry.workflow_status)?
        ' <button data-canonical-review-transition="'+esc(entry.workflow_id)+
        '">Update review status</button>':'')
     ]))+
    '<p>Showing '+(rows.length?offset+1:0)+'–'+(offset+rows.length)+
    ' of '+page.total+' retained canonical lead records.</p>'+
    (offset?'<button data-canonical-lead-previous>Previous records</button> ':'')+
    (page.has_more?'<button data-canonical-lead-next>Next records</button>':'')+
    (!page.total?'<p>No retained canonical lead candidates. Review an investigation dossier first.</p>':'');
   section.querySelectorAll('[data-canonical-lead-dossier]').forEach(button=>{
    button.onclick=()=>perform(()=>openInvestigationDossier(button.dataset.canonicalLeadDossier));
   });
   section.querySelectorAll('[data-canonical-result-export]').forEach(button=>{
    button.onclick=()=>{
     const row=rows.find(r=>r.workflow_id===button.dataset.canonicalResultExport);
     if(row)download('canonical-lead-result-history.json',row);
    };
   });
   section.querySelectorAll('[data-canonical-review-transition]').forEach(button=>{
    button.onclick=()=>perform(async()=>{
     const row=rows.find(r=>r.workflow_id===button.dataset.canonicalReviewTransition);
     if(!row)return;
     const options={hold:['monitor','review'],monitor:['hold','review'],
      review:['hold','monitor']}[row.workflow_status]||[];
     if(!options.length)return;
     modal('Review-only original workflow transition',
      '<p>Only hold, monitor and review are available. This does not verify a site,'+
      ' authorize outreach or enable bidding.</p>'+
      '<form id="canonical-review-transition-form">'+
      '<label>Next review status <select name="next_status">'+
      options.map(status=>'<option value="'+esc(status)+'">'+esc(status)+'</option>').join('')+
      '</select></label>'+
      '<label>Operator review reason <textarea name="reason" minlength="10" maxlength="2000" required></textarea></label>'+
      '<label><input name="confirm" type="checkbox" required>'+
      ' I authorize this exact review-only status transition.</label>'+
      '<button type="submit">Record original workflow transition</button></form>');
     $('canonical-review-transition-form').onsubmit=event=>{
      event.preventDefault();
      perform(async()=>{
       const form=$('canonical-review-transition-form');
       const reason=form.elements.namedItem('reason').value.trim();
       if(reason.length<10||!form.elements.namedItem('confirm').checked)
        throw Error('An explicit review reason and confirmation are required.');
       await api('/api/investigation-lead-review-transition',{
        investigation_id:row.canonical_investigation_id,
        workflow_id:row.workflow_id,expected_status:row.workflow_status,
        next_status:form.elements.namedItem('next_status').value,
        expected_evidence_id:row.current_source_evidence_id,
        reason,caller_confirmation:true
       });
       if($('action-dialog').open)$('action-dialog').close();
       await load();
      });
     };
    });
   });
   const back=section.querySelector('[data-canonical-lead-previous]');
   if(back)back.onclick=()=>perform(async()=>{offset-=25;await load();});
   const next=section.querySelector('[data-canonical-lead-next]');
   if(next)next.onclick=()=>perform(async()=>{offset+=25;await load();});
  }catch(error){
   if(section.isConnected&&activePage==='Lead Console')
    section.innerHTML='<h3>Retained investigation lead workflows</h3>'+
     '<p role="alert">Original workflow records unavailable: '+esc(error.message)+'</p>';
  }
 }
 await load();
}
async function openWorkspace(name,key){activePage=name;activeInvestigationMapRows=[];hideSearch();if($('map').parentNode!==mapHome)mapHome.append($('map'));if($('lead-filters').parentNode!==filterHome)filterHome.append($('lead-filters'));$('lead-filters').hidden=true;document.querySelectorAll('nav button').forEach(b=>b.classList.toggle('active',b.dataset.page===name));const home=name==='Command Center';$('workspace').hidden=!home;$('stub').hidden=home;$('stub-title').textContent=name;if(home){document.querySelectorAll('[data-live-graph]').forEach(h=>h.dispatchEvent(new Event('graph-dispose')));document.querySelectorAll('[data-shared-investigations]').forEach(h=>h.dispatchEvent(new Event('investigation-dispose')));apply();refreshChrome();refreshOverviewInvestigationMap();return;}const previous=$('section-content');previous.querySelectorAll('[data-live-graph]').forEach(h=>h.dispatchEvent(new Event('graph-dispose')));previous.querySelectorAll('[data-shared-investigations]').forEach(h=>h.dispatchEvent(new Event('investigation-dispose')));const box=previous.cloneNode(false);previous.replaceWith(box);try{if(name==='Lead Console'){box.innerHTML='<div id="console-toolbar"></div><div id="console-table"></div>';$('lead-filters').hidden=false;box.prepend($('lead-filters'));renderConsole();await renderCanonicalLeadWorkflows(box);await renderInvestigationInventory(box);}else if(name==='Watchlist')await renderWatchlist(box);else if(name==='Sources & Collection')await renderSources(box);else if(name==='Outreach')await renderOutreach(box);else if(name==='Project Intelligence'){await renderAnalytics(box);await renderInvestigationInventory(box);}else if(name==='Entity Network'){renderNetwork(box);const live=document.createElement('button');live.id='open-live-relationship-graph';live.textContent='Live Relationship Graph';box.prepend(live);live.onclick=()=>perform(()=>openLiveRelationshipGraph(box));await renderInvestigationInventory(box);}else if(name==='Evidence Chains'){box.innerHTML='<p>Select a source record to inspect its retained evidence and field provenance.</p>'+table(['Project','Source','Row hash'],baseRows().map(r=>[`<button data-open="${esc(r.source_key)}">${esc(r.SITE_NAME)}</button>`,'California SMARTS',`<button data-evidence="${esc(r.source_key)}">${esc(r.row_sha256)}</button>`]));box.querySelectorAll('[data-evidence]').forEach(b=>b.onclick=()=>openDossier(b.dataset.evidence,'evidence'));await renderInvestigationInventory(box);}else if(name==='Site Map'){renderSiteMap(box);await renderInvestigationInventory(box,rows=>{activeInvestigationMapRows=rows;drawMap();});}else if(name==='Bid Studio'){await renderBids(box,key);await renderLegacyCommercial(box,name);}else if(name==='Royalty Ledger'){await renderRoyalties(box);await renderLegacyCommercial(box,name);}drawMap();}catch(e){showError(e);}}
let sortColumn='first_seen',sortDirection=-1,chosen=new Set();
function renderConsole(){if(!$('console-table'))return;const focus=document.activeElement?.id==='console-search',cursor=$('console-search')?.selectionStart;const oldq=$('console-search')?.value||'',oldcontact=$('contact-filter')?.value||'',oldhidden=$('show-hidden')?.checked||false;$('console-toolbar').innerHTML=`${analyticFilter?`<span>Chart: ${esc(analyticFilter.key)} = ${esc(analyticFilter.value)}</span><button id="clear-chart">Clear chart filter</button>`:''}<input id="console-search" aria-label="Filter Lead Console" placeholder="Filter projects, contacts or notes" value="${esc(oldq)}"><select id="contact-filter" aria-label="Contact availability"><option value="">All contact states</option><option value="yes">Contact found</option><option value="no">No contact</option></select><label><input type="checkbox" id="include-excluded" ${includeExcluded?'checked':''}>Include excluded infrastructure</label><label><input type="checkbox" id="show-hidden" ${oldhidden?'checked':''}>Show hidden</label><button id="save-view">Save view</button><select id="saved-view" aria-label="Saved view"><option value="">Saved views</option>${Object.keys(data.settings?.saved_views||{}).map(k=>`<option>${esc(k)}</option>`).join('')}</select><button id="verification-queue">Verify sites</button><button id="bulk-status">Bulk status</button><button id="bulk-watch">Bulk watch</button><button id="bulk-outreach">Bulk outreach</button><button id="console-export">Export CSV</button><button id="call-list-export">Export company call list</button><button id="bulk-import-contacts">Import all captured SMARTS contacts</button>`;$('verification-queue').onclick=()=>openVerificationQueue();if($('clear-chart'))$('clear-chart').onclick=()=>{analyticFilter=null;apply();};$('contact-filter').value=oldcontact;let rows=filtered.filter(r=>!oldcontact||(oldcontact==='yes'?r.sourced_contacts?.length:!r.sourced_contacts?.length));rows.sort((a,b)=>sortDirection*String(a[sortColumn]??a.feedback?.[sortColumn]??'').localeCompare(String(b[sortColumn]??b.feedback?.[sortColumn]??''),undefined,{numeric:true}));$('console-table').innerHTML=table(['Select','Project','County','City','Type','Fit','Status','Contact','Notes'],rows.map(r=>[`<input type="checkbox" data-select="${esc(r.source_key)}" aria-label="Select ${esc(r.SITE_NAME)}" ${chosen.has(r.source_key)?'checked':''}>`,`<button data-open="${esc(r.source_key)}">${esc(r.SITE_NAME)}</button>`,esc(r.SITE_COUNTY),esc(r.SITE_CITY),esc(r.project_type),esc(r.security_fit),esc(r.feedback?.status),`${esc(r.sourced_contacts?.length||0)}${r.sourced_contacts?.length?' · priority '+esc(r.sourced_contacts[0].reliability_score):''}`,`<input data-inline-note="${esc(r.source_key)}" aria-label="Notes for ${esc(r.SITE_NAME)}" value="${esc(r.feedback?.notes||'')}">`]));const columns=['','SITE_NAME','SITE_COUNTY','SITE_CITY','project_type','security_fit','status'];$('console-table').querySelectorAll('th').forEach((th,i)=>{if(columns[i]){th.tabIndex=0;th.onclick=()=>{sortDirection=sortColumn===columns[i]?-sortDirection:1;sortColumn=columns[i];renderConsole();};th.onkeydown=e=>{if(e.key==='Enter')th.click();};}});$('console-search').oninput=apply;$('contact-filter').onchange=renderConsole;$('include-excluded').onchange=e=>{includeExcluded=e.target.checked;apply();};$('show-hidden').onchange=apply;document.querySelectorAll('[data-select]').forEach(el=>el.onchange=()=>el.checked?chosen.add(el.dataset.select):chosen.delete(el.dataset.select));document.querySelectorAll('[data-inline-note]').forEach(el=>el.onchange=()=>perform(async()=>{const r=data.rows.find(r=>r.source_key===el.dataset.inlineNote);await saveNotes(r,{notes:el.value});await reload();}));$('save-view').onclick=()=>{modal('Save Lead Console view',`<form id="view-form">${field('name','View name','', 'text',true)}<button type="submit">Save view</button></form>`);bindForm('view-form',async f=>{const view={region:$('county').value,type:$('type').value,band:$('band').value,status:$('status-filter').value,fresh:$('freshness').value,readiness:readinessFilter,search:oldq,contact:oldcontact,includeExcluded};await api('/api/settings',{saved_views:{...data.settings.saved_views,[f.name]:view}});$('action-dialog').close();await reload();renderConsole();});};$('saved-view').onchange=()=>{const v=data.settings.saved_views[$('saved-view').value];if(!v)return;for(const[id,k]of [['county','region'],['type','type'],['band','band'],['status-filter','status'],['freshness','fresh']])$(id).value=v[k]||'';readinessFilter=v.readiness||'';includeExcluded=Boolean(v.includeExcluded);$('console-search').value=v.search||'';$('contact-filter').value=v.contact||'';apply();};if(focus){$('console-search').focus();$('console-search').setSelectionRange(cursor,cursor);}$('console-export').onclick=()=>downloadCSV(rows,'leads.csv');$('call-list-export').onclick=()=>{const a=document.createElement('a');a.href='/api/call-list.csv';a.download='ConstructionSight-call-list.csv';a.click();};$('bulk-import-contacts').disabled=data.read_only;$('bulk-import-contacts').onclick=()=>perform(async()=>{const button=$('bulk-import-contacts');button.disabled=true;button.textContent='Verifying retained source evidence…';try{const result=await api('/api/smarts-contacts-bulk',{});await reload();modal('Bulk contact import',`<p>One result per captured lead; no messages sent.</p><pre>${esc(JSON.stringify(result.status_counts||{journal_verified:result.journal_verified},null,2))}</pre><button id="bulk-contact-report">Download per-lead results</button>`);$('bulk-contact-report').onclick=()=>download('bulk-contact-results.json',result);}finally{if(button.isConnected){button.disabled=false;button.textContent='Import all captured SMARTS contacts';}}});for(const action of ['status','watch','outreach'])$('bulk-'+action).onclick=()=>bulkAction(action,rows.filter(r=>chosen.has(r.source_key)));}
async function saveNotes(r,patch){const f=r.feedback||{};await api(keyPath('feedback',r.source_key),{status:f.status||'New',notes:f.notes||'',last_contacted:f.last_contacted||'',reason_code:f.reason_code||'',reason_text:f.reason_text||'',...patch});}
function photoForm(key){modal('Site photograph',`<form id="photo-form" class="form-grid"><label>PNG / JPEG up to 1 MB<input name="photo" type="file" accept="image/png,image/jpeg" required></label>${field('source','Photo source / ownership','','text',true)}<button type="submit">Save uploaded photograph</button></form>`);bindForm('photo-form',async f=>{const file=$('photo-form').elements.photo.files[0];if(!file||file.size>1000000)throw Error('Photo must be up to 1 MB');const bytes=new Uint8Array(await file.arrayBuffer());let binary='';for(const byte of bytes)binary+=String.fromCharCode(byte);await api(keyPath('photo',key),{data:btoa(binary),source:f.source});$('action-dialog').close();await reload();});}
function bulkAction(action,rows){if(!rows.length){showError(Error('Select at least one lead'));return;}if(action==='status'){modal('Bulk status',`<form id="bulk-form">${options('status',data.statuses,'Reviewing','Status')}${options('reason_code',[['','—'],...data.reasons],'','Loss / exclusion reason')}<button type="submit">Apply to ${rows.length} leads</button></form>`);bindForm('bulk-form',async f=>{for(const r of rows)await saveNotes(r,f);$('action-dialog').close();await reload();});}else if(action==='watch'){modal('Bulk reminders',`<form id="bulk-form">${field('remind_on','Due date','','date')}${field('note','Reminder','', 'textarea')}<button type="submit">Save ${rows.length} reminders</button></form>`);bindForm('bulk-form',async f=>{for(const r of rows)await api(keyPath('watchlist',r.source_key),{action:'save',...f});$('action-dialog').close();await refreshChrome();});}else perform(async()=>{for(const r of rows)await api(keyPath('outreach',r.source_key),{});await reload();});}
function downloadCSV(rows,name){const fields=['SITE_NAME','SITE_COUNTY','SITE_CITY','WDID','APP_ID','OWNER_NAME','DEVELOPER_NAME','project_type','security_fit','readiness','stage','value','size_sf','status','notes'],quote=value=>{let s=String(value??'');if(/^[\s]*[=+\-@]/.test(s))s="'"+s;return '"'+s.replace(/"/g,'""')+'"';};const csv='\ufeff'+[fields.join(','),...rows.map(r=>fields.map(k=>quote(r[k]??r.feedback?.[k])).join(','))].join('\r\n');download(name,csv);}
function editWatch(key){const row=data.rows.find(r=>r.source_key===key),w=watches.find(w=>w.source_key===key);modal('Watch / remind: '+(row?.SITE_NAME||w?.row.SITE_NAME||'—'),`<form id="reminder-form">${field('remind_on','Due date',w?.remind_on,'date')}${field('note','Reminder note',w?.note,'textarea')}<button type="submit">Save reminder</button></form>`);bindForm('reminder-form',async f=>{await api(keyPath('watchlist',key),{action:'save',...f});$('action-dialog').close();await refreshChrome();if(activePage==='Watchlist')renderWatchlist($('section-content'));});}
async function renderWatchlist(box){box.innerHTML=table(['Project','Due','State','Reminder','Updated','Actions'],watches.map(w=>[`<button data-open="${esc(w.source_key)}">${esc(w.row.SITE_NAME)}</button>`,esc(w.remind_on),esc(w.due?'Overdue / due':w.source_state),esc(w.note),esc(age(w.updated_at)),['edit','snooze','complete','review','remove'].map(action=>`<button data-watch-action="${action}" data-key="${esc(w.source_key)}">${action}</button>`).join(' ')]));if(!watches.length)box.innerHTML+='<p>No saved watches. Add one from a dossier.</p>';box.querySelectorAll('[data-watch-action]').forEach(b=>b.onclick=()=>{const key=b.dataset.key,action=b.dataset.watchAction,w=watches.find(w=>w.source_key===key);if(action==='edit'){editWatch(key);return;}perform(async()=>{const due=new Date();due.setDate(due.getDate()+7);const payload=action==='snooze'?{action:'save',remind_on:due.toISOString().slice(0,10)}:action==='complete'?{action:'save',remind_on:null}:action==='review'?{action:'acknowledge'}:{action:'remove'};await api(keyPath('watchlist',key),payload);await refreshChrome();await renderWatchlist(box);});});
 const canonical=document.createElement('section');
 canonical.className='feature-card';
 canonical.innerHTML='<h3>Shared investigation watches</h3><p role="status">Reading committed investigation evidence…</p>';
 box.append(canonical);
 try{
  const entries=data.read_only?[]:await api('/api/investigation-watches');
  if(!canonical.isConnected)return;
  canonical.innerHTML='<h3>Shared investigation watches</h3>'+
   '<p>Existing committed investigation and source-evidence watches, distinct from commercial lead reminders. No automatic lead qualification, contact or bid.</p>'+
   table(['Canonical investigation','State','Inspect'],entries.map(w=>[
    esc(w.investigation_id),
    w.available?(w.changed?'Retained evidence changed; review required':'Watching committed evidence'):
     'Unavailable: '+esc(w.reason),
    '<button data-investigation-watch-open="'+esc(w.investigation_id)+'">Open shared dossier</button>'
   ]))+(entries.length?'':'<p>No shared investigations watched. Open an investigation dossier to watch it.</p>');
  canonical.querySelectorAll('[data-investigation-watch-open]').forEach(button=>{
   button.onclick=()=>perform(()=>openInvestigationDossier(button.dataset.investigationWatchOpen));
  });
 }catch(error){
  if(canonical.isConnected)canonical.innerHTML='<h3>Shared investigation watches</h3><p role="alert">'+esc(error.message)+'</p>';
 }
}
async function renderSources(box){const runs=await api('/api/runs'),quality=await api('/api/quality'),schedule=data.read_only?null:await api('/api/schedule');if(!box.isConnected)return;box.innerHTML=`<div class="source-toolbar"><b>California SMARTS · Construction Active facilities</b><label><input id="source-enabled" type="checkbox" ${data.settings?.source_enabled?'checked':''} ${data.read_only?'disabled':''}>Enabled</label><button id="capture-now" ${data.read_only?'disabled':''}>Run capture now</button><button id="source-terms">Source terms</button></div><p>Last run: ${esc(runs[0]?.finished_at)} · Next scheduled run: <span id="next-run">${esc(schedule?.next_run)}</span> · Timer ${schedule?.active?'active':'inactive'} · ${schedule?.pending_review?'Schedule configuration awaits reviewed install':'Reviewed units current'}</p><p id="schedule-warning" role="alert">${esc(schedule?.warning||schedule?.manager_error)}</p><button id="daily-schedule" ${data.read_only?'disabled':''}>Daily schedule / Zorin setup</button><p id="capture-progress" role="status"></p><p>${esc(data.captured_at)} · ${data.rows.length} distinct leads · ${data.duplicate_rows} duplicate rows · ${data.missing_identity_rows} without usable identity · ${data.requests} requests</p><details><summary>Classifier quality: ${quality.unknown_percent==null?'—':quality.unknown_percent.toFixed(2)+'%'} unknown · ${quality.excluded} excluded</summary><p>${esc(quality.method)}</p><button id="quality-export">Export quality report</button>${table(['Unknown token','Frequency'],quality.unknown_tokens.map(([token,n])=>[esc(token),esc(n)]))}</details>`+table(['Started','Result','Rows','New','Missing from Active','Requests','Error'],runs.map(r=>[esc(r.started_at),esc(r.outcome),esc(r.rows),esc(r.new_count),esc(r.removed_count),esc(r.requests),esc(r.error)]));$('daily-schedule').onclick=()=>openSchedule(schedule);$('quality-export').onclick=()=>download('classifier-quality.json',quality);$('source-enabled').onchange=()=>perform(async()=>{await api('/api/settings',{source_enabled:$('source-enabled').checked});await reload();});$('source-terms').onclick=()=>perform(async()=>{const terms=await api('/api/terms');modal('Source terms',terms.map(t=>`<h3>${esc(t.source)}</h3><p>${esc(t.summary)}</p>${t.url?`<a href="${esc(t.url)}" target="_blank" rel="noopener">Publisher terms</a>`:''}`).join(''));});$('capture-now').onclick=()=>perform(async()=>{await api('/api/capture',{});async function poll(){const state=await api('/api/capture');if($('capture-progress'))$('capture-progress').textContent=state.message;if(state.running){setTimeout(()=>perform(poll),1000);}else{await reload();if(activePage==='Sources & Collection')await renderSources(box);}}await poll();});await renderRetainedSources(box);}
function mergeTemplate(text,lead,contact){const values={project:lead.SITE_NAME,city:lead.SITE_CITY,contact:contact?.name,company:data.settings?.profile.company,owner:lead.OWNER_NAME,developer:lead.DEVELOPER_NAME};return text.replace(/\{\{(\w+)\}\}/g,(m,key)=>values[key]||'—');}
function renderOutreachLead(lead,box){const contacts=lead.sourced_contacts||[],templates=data.settings?.templates||{},blocked=lead.do_not_contact||lead.feedback?.status==='Not a fit';box.innerHTML=`<p>${blocked?'Do-Not-Contact · external contact links disabled':lead.outreach_queued?'In outreach queue':'Not queued'}</p><button id="outreach-queue" ${blocked||data.read_only?'disabled':''}>${lead.outreach_queued?'Queued':'Add to Outreach'}</button>${options('contact', [['','Choose a sourced contact'],...contacts.map((c,i)=>[String(i),[c.name,c.email,c.phone].filter(Boolean).join(' · ')])],'','Contact')}${options('template-kind',['email','call','voicemail'],'email','Template')}<textarea id="template-text" rows="5">${esc(templates.email||'')}</textarea><button id="save-template" ${data.read_only?'disabled':''}>Save reusable template</button><pre id="template-preview"></pre><div id="contact-links"></div><form id="activity-form" class="form-grid">${options('kind',['called','emailed','replied','voicemail','note'],'called','Record activity')}${field('note','Outcome / note','','textarea')}<button type="submit">Log activity</button></form><button id="outreach-remind">Follow-up reminder</button>`;const contactSelect=box.querySelector('[name=contact]'),kindSelect=box.querySelector('[name=template-kind]');function preview(){const contact=contactSelect.value===''?null:contacts[Number(contactSelect.value)],text=mergeTemplate($('template-text').value,lead,contact);$('template-preview').textContent=text;$('contact-links').innerHTML=blocked||!contact?'':`${contact.email?`<a id="mailto-link" href="mailto:${encodeURIComponent(contact.email)}?subject=${encodeURIComponent(lead.SITE_NAME||'')}&body=${encodeURIComponent(text)}">Open in mail client</a>`:''} ${contact.phone?`<a id="tel-link" href="tel:${esc(contact.phone.replace(/[^+\d]/g,''))}">Open phone link</a>`:''}`;}contactSelect.onchange=preview;kindSelect.onchange=()=>{$('template-text').value=templates[kindSelect.value]||'';preview();};$('template-text').oninput=preview;preview();$('outreach-queue').onclick=()=>perform(async()=>{await api(keyPath('outreach',lead.source_key),{});await reload();renderOutreachLead(data.rows.find(r=>r.source_key===lead.source_key),box);});$('save-template').onclick=()=>perform(async()=>{await api('/api/settings',{templates:{...templates,[kindSelect.value]:$('template-text').value}});await reload();});bindForm('activity-form',async f=>{await api(keyPath('activity',lead.source_key),f);$('activity-form').reset();});$('outreach-remind').onclick=()=>editWatch(lead.source_key);}
async function renderOutreach(box){const queue=await api('/api/outreach'),keys=new Set(queue.map(q=>q.source_key)),rows=baseRows().filter(r=>keys.has(r.source_key));if(!box.isConnected)return;box.innerHTML='<p>Messages, calls and texts require your action. This app never sends.</p>'+table(['Project','Status','Sourced contacts','Actions'],rows.map(r=>[`<button data-open="${esc(r.source_key)}">${esc(r.SITE_NAME)}</button>`,esc(r.feedback.status),esc(r.sourced_contacts?.length||0),`<button data-outreach="${esc(r.source_key)}">Templates / activity / follow-up</button>`]));if(!rows.length)box.innerHTML+='<p>The scoped queue is empty.</p>';box.querySelectorAll('[data-outreach]').forEach(b=>b.onclick=()=>openDossier(b.dataset.outreach,'outreach'));}
async function renderAnalytics(box){const calibration=await api('/api/calibration');if(!box.isConnected)return;const rows=baseRows(),metrics=[['project_type','Project type'],['SITE_COUNTY','County'],['SITE_CITY','City'],['stage','Stage'],['readiness','Readiness funnel'],['DEVELOPER_NAME','Developers'],['score_band','Score distribution'],['week','New observations per week']];box.innerHTML='<p>Charts use scoped, captured rows. Type is a name-based classifier unless manually verified. “New” is first source observation.</p><div class="analytics-grid">'+metrics.map(([key,label])=>{const groups=new Map();for(const r of rows){const v=key==='score_band'?(Math.floor(r.security_fit/10)*10)+'–'+Math.min(100,Math.floor(r.security_fit/10)*10+9):key==='week'?(r.first_seen?weekStart(r.first_seen):'—'):r[key]||'—';groups.set(v,(groups.get(v)||0)+1);}const sorted=[...groups].sort((a,b)=>b[1]-a[1]).slice(0,20),max=Math.max(1,...sorted.map(r=>r[1]));return `<section><h3>${label}</h3>${sorted.map(([v,n])=>`<button class="chart-bar" data-chart-field="${key}" data-chart-value="${esc(v)}"><span>${esc(v)}</span><i style="width:${n/max*100}%"></i><b>${n}</b></button>`).join('')}</section>`;}).join('')+'</div>';box.querySelectorAll('[data-chart-field]').forEach(b=>b.onclick=()=>{const key=b.dataset.chartField,v=b.dataset.chartValue;analyticFilter={key,value:v};openWorkspace('Lead Console');if(key==='SITE_COUNTY')$('county').value=v;else if(key==='SITE_CITY')$('county').value='city:'+v;else if(key==='project_type')$('type').value=v;else if(key==='readiness')readinessFilter=v;apply();});const scopedKeys=new Set(rows.map(r=>r.source_key)),cohorts=calibration.cohorts.map(c=>({...c,source_keys:c.source_keys.filter(k=>scopedKeys.has(k))})).filter(c=>c.source_keys.length);const statuses=['New','Reviewing','Outreach queued','Contacted','Quoted','Won','Lost','Not a fit'];box.insertAdjacentHTML('beforeend','<h3>Outcome calibration</h3><p>Uses score and project type recorded at the last status update. Win rate includes only Won and Lost; no closed outcomes is —. Drill down to inspect each cohort.</p>'+table(['Type','Recorded band',...statuses,'Closed win rate','Cohort'],cohorts.map((c,i)=>{const members=rows.filter(r=>c.source_keys.includes(r.source_key)),counts=Object.fromEntries(statuses.map(s=>[s,members.filter(r=>(r.feedback?.status||'New')===s).length])),closed=counts.Won+counts.Lost;return [esc(c.project_type),esc(c.score_band),...statuses.map(s=>counts[s]),closed?(100*counts.Won/closed).toFixed(1)+'%':'—',`<button data-cohort="${i}">${members.length} leads</button>`];}))+'<button id="review-weights" '+(data.read_only?'disabled':'')+'>Review weights change</button><h3>Weights changelog</h3>'+table(['Saved','Reviewer','Reason','Before → After'],calibration.changes.map(c=>[esc(c.at),esc(c.reviewer),esc(c.reason),esc(Object.keys(c.after).filter(k=>c.before[k]!==c.after[k]).map(k=>`${k}: ${c.before[k]} → ${c.after[k]}`).join('; '))])));box.querySelectorAll('[data-cohort]').forEach(b=>b.onclick=()=>{const c=cohorts[Number(b.dataset.cohort)];modal('Calibration cohort',table(['Project','Recorded score','Status','Evidence'],rows.filter(r=>c.source_keys.includes(r.source_key)).map(r=>[`<button data-open="${esc(r.source_key)}">${esc(r.SITE_NAME)}</button>`,esc(r.feedback?.score_at_update??r.security_fit),esc(r.feedback?.status),esc(r.feedback?.updated_at||'—')])));});$('review-weights').onclick=()=>{const weights=data.settings.weights;modal('Review scoring weights',`<form id="weights-review-form" class="form-grid">${Object.entries(weights).map(([k,v])=>field(k,k,v,'number')).join('')}${field('reason','Reason for change','','text',true)}<label><input type="checkbox" name="reviewed" required> I reviewed the outcome cohorts and these weights</label><p>Weights are operator choices. Applying does not establish verified facts or rewrite past scores.</p><button id="apply-reviewed-weights">Apply reviewed weights</button></form>`);bindForm('weights-review-form',async f=>{await api('/api/weights-reviewed',{weights:Object.fromEntries(Object.keys(weights).map(k=>[k,Number(f[k])])),expected_digest:calibration.weights_digest,reason:f.reason,reviewed:f.reviewed==='on'});$('action-dialog').close();await reload();await openWorkspace('Project Intelligence');});};}
function renderNetwork(box){const rows=baseRows(),nodes=new Map(),edges=[];function add(id,label,type,lead,source){if(!nodes.has(id))nodes.set(id,{id,label,type,leads:new Set(),source});nodes.get(id).leads.add(lead.source_key);return id;}for(const r of rows){const site=add('site:'+r.source_key,r.SITE_NAME||'—','site',r,'SMARTS source record');for(const key of ['DEVELOPER_NAME','OWNER_NAME']){const name=r[key];if(name&&!['NA','N/A','UNKNOWN','NONE','NULL'].includes(name.toUpperCase()))edges.push([add(key+':'+name,name,'party',r,r.field_sources?.[key]?.source||'SMARTS '+key),site]);}for(const c of r.sourced_contacts||[]){const contact=add('contact:'+c.id,c.name||c.email||c.phone,'contact',r,c.source);edges.push([contact,site]);if(c.company)edges.push([add('company:'+c.company,c.company,'party',r,c.source),contact]);}}const values=[...nodes.values()],columns={party:80,site:430,contact:780},positions=new Map();for(const type of Object.keys(columns)){values.filter(n=>n.type===type).forEach((n,i)=>positions.set(n.id,[columns[type],45+i*52]));}const height=Math.max(150,...[...positions.values()].map(p=>p[1]+45));box.innerHTML='<p>Edges come from explicit source fields or entered contacts with provenance. Matching a reported name does not establish legal entity identity.</p><div class="graph-scroll"><svg id="entity-graph" viewBox="0 0 1100 '+height+'" role="img" aria-label="Sourced entity relationships">'+edges.map(([a,b])=>{const [x1,y1]=positions.get(a),[x2,y2]=positions.get(b);return `<path d="M${x1+105} ${y1}L${x2+105} ${y2}" stroke="#665332"/>`;}).join('')+values.map((n,i)=>{const[x,y]=positions.get(n.id);return `<g data-node="${i}" tabindex="0" role="button" aria-label="${esc(n.label)}"><title>${esc(n.source)}</title><rect x="${x}" y="${y-17}" width="210" height="34" rx="5" fill="#242424" stroke="#b58b35"/><text x="${x+9}" y="${y+4}" fill="#ddd">${esc(n.label.slice(0,26))}</text></g>`;}).join('')+'</svg></div><div id="network-leads"></div>';box.querySelectorAll('[data-node]').forEach(node=>{node.onclick=()=>{const n=values[Number(node.dataset.node)];$('network-leads').innerHTML=`<h3>${esc(n.label)}</h3><p>Source: ${esc(n.source)}</p>`+table(['Associated source leads'],rows.filter(r=>n.leads.has(r.source_key)).map(r=>[`<button data-open="${esc(r.source_key)}">${esc(r.SITE_NAME)}</button>`]));};node.onkeydown=e=>{if(e.key==='Enter')node.dispatchEvent(new MouseEvent('click',{bubbles:true}));};});}
function haversine(a,b){const rad=x=>x*Math.PI/180,dlat=rad(a[0]-b[0]),dlon=rad(a[1]-b[1]),h=Math.sin(dlat/2)**2+Math.cos(rad(a[0]))*Math.cos(rad(b[0]))*Math.sin(dlon/2)**2;return 3958.7613*2*Math.atan2(Math.sqrt(h),Math.sqrt(1-h));}
function renderSiteMap(box){box.innerHTML=`<div class="map-toolbar"><select id="full-map-type" aria-label="Project type on full map">${Array.from($('type').options).map(o=>`<option value="${esc(o.value)}" ${o.value===$('type').value?'selected':''}>${esc(o.textContent)}</option>`).join('')}</select><button id="map-fit">Fit to bounds</button>${field('radius-lat','Latitude',center[0])}${field('radius-lon','Longitude',center[1])}${field('radius-miles','Within miles','','number')}<button id="radius-search">Radius search</button><button id="radius-clear">Clear radius</button><button id="visible-export">Export visible leads</button></div><div id="full-map"></div><p id="radius-count"></p>`;$('lead-filters').hidden=false;box.prepend($('lead-filters'));$('full-map-type').onchange=e=>{$('type').value=e.target.value;apply();};$('full-map').append($('map'));$('map-fit').onclick=fitBounds;$('radius-search').onclick=()=>{const get=n=>box.querySelector('[name='+n+']').value,lat=Number(get('radius-lat')),lon=Number(get('radius-lon')),miles=Number(get('radius-miles'));if(!get('radius-lat')||!get('radius-lon')||!Number.isFinite(lat)||!Number.isFinite(lon)||Math.abs(lat)>85||Math.abs(lon)>180||!(miles>0&&miles<=1000)){showError(Error('Enter valid coordinates and a radius from 0 to 1,000 miles'));return;}apply();filtered=filtered.filter(r=>point(r)&&haversine([lat,lon],[+r.SITE_LATITUDE,+r.SITE_LONGITUDE])<=miles);center=[lat,lon];drawMap();$('radius-count').textContent=filtered.length+' leads within '+miles+' miles';};$('radius-clear').onclick=()=>{apply();$('radius-count').textContent='Radius filter cleared';};$('visible-export').onclick=()=>{const[cx,cy]=world(...center),w=$('map').clientWidth,h=$('map').clientHeight;const rows=filtered.filter(r=>{if(!point(r))return false;const[x,y]=world(+r.SITE_LATITUDE,+r.SITE_LONGITUDE);return mapLayers[r.readiness]&&Math.abs(x-cx)<=w/2&&Math.abs(y-cy)<=h/2;});downloadCSV(rows,'visible-leads.csv');};}
async function renderBids(box,leadKey){const bids=data.read_only?[]:await api('/api/bids'),keys=new Set(baseRows().map(r=>r.source_key)),scoped=bids.filter(b=>keys.has(b.source_key));if(!box.isConnected||(box.id==='section-content'&&activePage!=='Bid Studio'))return;box.innerHTML='<button id="new-bid">New estimate</button> <button id="price-book">Price book</button> <button id="scope-templates">Scope templates</button><p>Amounts use exact cents and Decimal quantities. Marking “sent” records your action; the app never sends.</p>'+table(['Project','Estimate','Version','Status','Total','Actions'],scoped.map(b=>[esc(data.rows.find(r=>r.source_key===b.source_key)?.SITE_NAME),esc(b.title),esc(b.version),esc(b.status),moneyText(b.total_minor),`<button data-edit-bid="${esc(b.id)}">Edit / version</button> <button data-history="${esc(b.id)}">Versions</button> <a href="/api/proposal/${esc(b.id)}" download="proposal.pdf">PDF</a>`]));$('new-bid').onclick=()=>editBid(null,leadKey);$('price-book').onclick=()=>openPriceBook();$('scope-templates').onclick=()=>openScopes();box.querySelectorAll('[data-edit-bid]').forEach(b=>b.onclick=()=>editBid(scoped.find(x=>x.id===b.dataset.editBid)));box.querySelectorAll('[data-history]').forEach(b=>b.onclick=()=>perform(async()=>{const versions=await api('/api/bid-history/'+b.dataset.history);modal('Bid versions',table(['Version','Saved','Status','Total','Proposal'],versions.map(v=>[esc(v.version),esc(v.at),esc(v.status),moneyText(v.total_minor),`<a href="/api/proposal/${esc(v.id)}?version=${v.version}" download="proposal-v${v.version}.pdf">PDF</a>`])));}));if(leadKey)await editBid(null,leadKey);}
async function editBid(bid,leadKey){const priceBook=data.read_only?[]:await api('/api/price-book'),scopes=data.read_only?{}:await api('/api/scopes'),rows=baseRows();if(!rows.length){modal('Estimate','<p>No scoped source leads.</p>');return;}let lines=bid?.lines.map(l=>({...l,unit_price:(l.unit_price_minor/100).toFixed(2)}))||[{description:'',category:'equipment',quantity:'',unit_price:'',taxable:false}];modal(bid?'Edit estimate · version '+bid.version:'New estimate',`<form id="bid-form" class="form-grid">${options('lead',rows.map(r=>[r.source_key,r.SITE_NAME||'—']),bid?.source_key||leadKey||rows[0].source_key,'Source lead')}${field('title','Estimate title',bid?.title,'text',true)}${field('prepared_for','Prepared for',bid?.prepared_for,'text',true)}${options('scope_template',[['','Choose a scope template'],...Object.keys(scopes)],'','Scope template')}${field('scope','Scope',bid?.scope,'textarea',true)}${field('basis','Pricing basis / assumptions',bid?.basis,'textarea',true)}<div id="bid-lines" class="wide"></div><button id="add-line" type="button">Add line</button>${field('markup','Markup %',bid?.markup,'text',true)}${field('tax','Tax %',bid?.tax,'text',true)}${options('tax_basis',['taxable_lines','subtotal_and_markup'],bid?.tax_basis||'taxable_lines','Tax basis')}${options('status',['draft','sent','won','lost'],bid?.status||'draft','Status')}${field('contract_value','Actual contract value for won bid',bid?.contract_minor==null?'':(bid.contract_minor/100).toFixed(2))}${options('loss_reason',[['','—'],...data.reasons],bid?.loss_reason||'','Loss reason')}<p>Prices and quantities are entered by you. The tax basis is explicit; rounded cents use round-half-even.</p><button type="submit">Save estimate version</button></form>`);
function readLines(){lines=Array.from($('bid-lines').querySelectorAll('tr[data-line]')).map(tr=>({description:tr.querySelector('[name=description]').value,category:tr.querySelector('[name=category]').value,quantity:tr.querySelector('[name=quantity]').value,unit_price:tr.querySelector('[name=unit_price]').value,taxable:tr.querySelector('[name=taxable]').checked}));}
function renderLines(){$('bid-lines').innerHTML=table(['Description','Category','Qty','Unit price','Taxable','Price book','Remove'],lines.map((l,i)=>[`<input name="description" aria-label="Line ${i+1} description" value="${esc(l.description)}" required>`,options('category',['equipment','labor','materials','permits'],l.category,''),`<input name="quantity" aria-label="Line ${i+1} quantity" value="${esc(l.quantity)}" required>`,`<input name="unit_price" aria-label="Line ${i+1} unit price" value="${esc(l.unit_price)}" required>`,`<input name="taxable" type="checkbox" aria-label="Line ${i+1} taxable" ${l.taxable?'checked':''}>`,options('price',[['','Choose'],...priceBook.map(p=>[p.id,p.description+' · v'+p.version])],'',''),`<button data-remove-line="${i}" type="button">Remove</button>`]));$('bid-lines').querySelectorAll('tbody tr').forEach((tr,i)=>{tr.dataset.line=i;tr.querySelector('[name=price]').onchange=e=>{readLines();const p=priceBook.find(p=>p.id===e.target.value);if(p){lines[i]={...lines[i],description:p.description,category:p.category,unit_price:(p.unit_price_minor/100).toFixed(2)};renderLines();}};});$('bid-lines').querySelectorAll('[data-remove-line]').forEach(b=>b.onclick=()=>{readLines();lines.splice(Number(b.dataset.removeLine),1);renderLines();});}renderLines();$('add-line').onclick=()=>{readLines();lines.push({description:'',category:'equipment',quantity:'',unit_price:'',taxable:false});renderLines();};$('bid-form').elements.scope_template.onchange=e=>{$('bid-form').elements.scope.value=scopes[e.target.value]||'';};if(bid)$('bid-form').elements.lead.disabled=true;bindForm('bid-form',async f=>{readLines();const key=bid?.source_key||f.lead;const payload={id:bid?.id,expected_version:bid?.version||0,title:f.title,prepared_for:f.prepared_for,scope:f.scope,basis:f.basis,lines,markup:f.markup,tax:f.tax,tax_basis:f.tax_basis,status:f.status,contract_value:f.contract_value,loss_reason:f.loss_reason};await api(keyPath('bids',key),payload);$('action-dialog').close();await reload();await renderBids($('section-content'));});}
async function openPriceBook(edit=null){const catalog=await api('/api/catalog'),entries=catalog.prices;modal('Reusable price book',table(['Description','Service','Category','Unit','Price','Basis','Version','Actions'],entries.map(p=>[esc(p.description),esc(p.service),esc(p.category),esc(p.unit),moneyText(p.unit_price_minor),esc(p.basis),p.version,`<button data-price-edit="${esc(p.id)}">Edit</button><button data-price-history="${esc(p.id)}">Versions</button>`]))+`<form id="price-form" data-version="${edit?.version||0}" class="form-grid"><h3>${edit?'Edit price · version '+edit.version:'Add a price'}</h3>${field('description','Description',edit?.description,'text',true)}${options('service',['CCTV','Access control','Intrusion','Structured cabling'],edit?.service||'CCTV','Service')}${options('category',['equipment','labor','materials','permits'],edit?.category||'equipment','Category')}${field('unit','Unit',edit?.unit,'text',true)}${field('unit_price','Unit price (USD)',edit?(edit.unit_price_minor/100).toFixed(2):'','text',true)}${field('basis','Price source / basis',edit?.basis,'textarea',true)}<p>Operator-entered amounts; no market prices are assumed. Saved estimates retain their copied scope and prices.</p><button type="submit">Save price version</button></form>`);bindForm('price-form',async f=>{await api('/api/price-book',{...f,id:edit?.id,expected_version:edit?.version||0});await openPriceBook();});document.querySelectorAll('[data-price-edit]').forEach(b=>b.onclick=()=>openPriceBook(entries.find(p=>p.id===b.dataset.priceEdit)));document.querySelectorAll('[data-price-history]').forEach(b=>b.onclick=()=>modal('Price versions',table(['Version','Saved','Description','Unit price','Basis'],catalog.price_history.filter(p=>p.id===b.dataset.priceHistory).map(p=>[p.version,esc(p.at),esc(p.description),moneyText(p.unit_price_minor),esc(p.basis)]))));}
async function openScopes(edit=null){const catalog=await api('/api/catalog');modal('Reusable scope templates',table(['Name','Service','Version','Actions'],catalog.scopes.map(s=>[esc(s.name),esc(s.service),s.version,`<button data-scope-edit="${esc(s.id)}">Edit</button><button data-scope-history="${esc(s.id)}">Versions</button>`]))+`<form id="scope-form" data-version="${edit?.version||0}" class="form-grid"><h3>${edit?'Edit scope · version '+edit.version:'Add scope template'}</h3>${field('name','Template name',edit?.name,'text',true)}${options('service',['CCTV','Access control','Intrusion','Structured cabling'],edit?.service||'CCTV','Service')}${field('body','Reusable scope text',edit?.body,'textarea',true)}<p>Review scope for each project. Past template and bid versions remain intact.</p><button type="submit">Save scope version</button></form>`);bindForm('scope-form',async f=>{await api('/api/scope-template',{...f,id:edit?.id,expected_version:edit?.version||0});await openScopes();});document.querySelectorAll('[data-scope-edit]').forEach(b=>b.onclick=()=>openScopes(catalog.scopes.find(s=>s.id===b.dataset.scopeEdit)));document.querySelectorAll('[data-scope-history]').forEach(b=>b.onclick=()=>modal('Scope versions',table(['Version','Saved','Name','Scope'],catalog.scope_history.filter(s=>s.id===b.dataset.scopeHistory).map(s=>[s.version,esc(s.at),esc(s.name),esc(s.body)]))));}
async function renderRoyalties(box){const all=await api('/api/royalties'),keys=new Set(baseRows().map(r=>r.source_key)),rows=all.filter(r=>keys.has(r.source_key)),bids=(await api('/api/bids')).filter(b=>b.status==='won'&&keys.has(b.source_key));if(!box.isConnected||(box.id==='section-content'&&activePage!=='Royalty Ledger'))return;box.innerHTML=`<button id="new-royalty" ${!bids.length?'disabled':''}>Record share terms on won contract</button> <button id="royalty-csv">Export CSV</button><p>A calculated share is separate from an invoice and receipt. Receivable = invoiced minus collected. Reversals retain the original transaction.</p>`+table(['Partner','Contract value','Calculated','Invoiced','Collected','Receivable','Credit','Actions'],rows.map(r=>[esc(r.partner),moneyText(r.contract_minor),moneyText(r.calculated_minor),moneyText(r.invoiced_minor),moneyText(r.received_minor),moneyText(r.receivable_minor),moneyText(r.credit_minor),`<button data-contract="${esc(r.id)}">Entries / record transaction</button>`]));$('new-royalty').onclick=()=>{modal('Royalty / share terms',`<form id="contract-form" class="form-grid">${options('bid_id',bids.map(b=>[b.id,b.title+' · '+moneyText(b.contract_minor)]),bids[0].id,'Won bid')}${field('partner','Partner security company','','text',true)}${field('percent','Share %','','text',true)}${field('terms','Agreed terms / basis','','textarea',true)}<button type="submit">Record calculated share</button></form>`);bindForm('contract-form',async f=>{await api('/api/royalty-contract',f);$('action-dialog').close();await renderRoyalties(box);});};$('royalty-csv').onclick=()=>{const fields=['partner','contract_minor','calculated_minor','invoiced_minor','received_minor','receivable_minor','credit_minor'],quote=v=>'"'+String(v??'').replace(/"/g,'""')+'"';download('royalties.csv','\ufeff'+[fields.join(','),...rows.map(r=>fields.map(k=>quote(/^[\s]*[=+\-@]/.test(String(r[k]))?"'"+r[k]:r[k])).join(','))].join('\r\n'));};box.querySelectorAll('[data-contract]').forEach(b=>b.onclick=()=>openLedger(rows.find(r=>r.id===b.dataset.contract)));}
function openLedger(contract){modal(contract.partner+' · ledger',`<p>Calculated ${moneyText(contract.calculated_minor)} · Invoiced ${moneyText(contract.invoiced_minor)} · Collected ${moneyText(contract.received_minor)} · Receivable ${moneyText(contract.receivable_minor)}</p><p>Terms: ${esc(contract.terms)}</p>`+table(['When','State','Amount','Reference','Reverses'],contract.entries.map(e=>[esc(e.at),esc(e.kind),moneyText(e.amount),esc(e.reference),esc(e.reverses)]))+`<form id="ledger-form" class="form-grid">${options('kind',['invoiced','received','reversal'],'invoiced','State')}${field('amount','Amount (USD)','','text')}${field('reference','Invoice, receipt or reversal reference','','text',true)}${options('reverses',[['','Choose entry to reverse'],...contract.entries.filter(e=>!e.reverses&&!contract.entries.some(r=>r.reverses===e.id)).map(e=>[e.id,e.kind+' · '+moneyText(e.amount)+' · '+e.reference])],'','Original entry for reversal')}<button type="submit">Record transaction</button></form>`);bindForm('ledger-form',async f=>{await api('/api/royalty-entry',{contract_id:contract.id,...f});await renderRoyalties($('section-content'));const fresh=(await api('/api/royalties')).find(r=>r.id===contract.id);openLedger(fresh);});}
let countyGeometry;
function renderBasemap(center,zoom,layers){let node=$('county-lines');if(!node){node=document.createElementNS('http://www.w3.org/2000/svg','svg');node.id='county-lines';node.style.cssText='position:absolute;inset:0;width:100%;height:100%;pointer-events:none';$('map').insertBefore(node,$('points'));}node.hidden=!layers.county;node.style.display=layers.county?'block':'none';if(!layers.county)return;if(!countyGeometry){countyGeometry='loading';api('/counties.json').then(value=>{countyGeometry=value;drawMap();}).catch(e=>{countyGeometry=null;showError(e);});return;}if(countyGeometry==='loading')return;const w=$('map').clientWidth,h=$('map').clientHeight,[cx,cy]=world(...center);node.setAttribute('viewBox',`0 0 ${w} ${h}`);node.innerHTML=countyGeometry.features.map(f=>{const polys=f.geometry.type==='MultiPolygon'?f.geometry.coordinates:[f.geometry.coordinates];return polys.map(poly=>`<path d="${poly.map(ring=>ring.map(([lon,lat],i)=>{const[x,y]=world(lat,lon);return(i?'L':'M')+(x-cx+w/2)+','+(y-cy+h/2);}).join('')+'Z').join('')}" fill="none" stroke="#cfa54f" stroke-width="2" stroke-dasharray="6 4"><title>${esc(f.properties.NAME)} · U.S. Census Bureau TIGERweb</title></path>`).join('');}).join('');}

$('app-shell').append($('search-results'));

function weekStart(value){const d=new Date(value);d.setUTCDate(d.getUTCDate()-((d.getUTCDay()+6)%7));return d.toISOString().slice(0,10);}

function analyticMatch(r){const {key,value}=analyticFilter;const actual=key==='week'?(r.first_seen?weekStart(r.first_seen):'—'):key==='score_band'?(Math.floor(r.security_fit/10)*10)+'–'+Math.min(100,Math.floor(r.security_fit/10)*10+9):r[key]||'—';return String(actual)===value;}

$('contact-summary').onclick=()=>perform(async()=>{const coverage=await api('/api/contact-coverage');modal('Captured lead contact coverage',table(['Measure','Count'],Object.entries(coverage).map(([k,v])=>[esc(k.replaceAll('_',' ')),esc(v)]))+'<p>Contacts are source-reported; purchasing authority is unverified. Possible consultants are flagged, not removed.</p><a href="/api/call-list.csv" download="ConstructionSight-call-list.csv">Download company call list</a>');});

function renderHighwayShields(shields,left,top,w,h){let node=$('highway-shields');if(!node){node=document.createElementNS('http://www.w3.org/2000/svg','svg');node.id='highway-shields';node.style.cssText='position:absolute;inset:0;width:100%;height:100%;pointer-events:none';$('map').insertBefore(node,$('points'));}node.setAttribute('viewBox',`0 0 ${w} ${h}`);node.innerHTML=shields.map(s=>{const[x,y]=world(s.lat,s.lon),px=x-left,py=y-top;if(px<0||py<0||px>w||py>h)return '';return `<g><image href="/shield-${s.asset==='interstate'?'interstate':'state'}.svg" x="${px-12}" y="${py-13}" width="24" height="26"/><text x="${px}" y="${py+4}" text-anchor="middle" fill="#eee" font-size="9">${esc(s.ref.replace(/^(I|CA|US)\s*/,'').slice(0,4))}</text><title>${esc(s.ref)} · OSM source road reference</title></g>`;}).join('');}

function openSchedule(schedule){const c=schedule.config;modal('Daily collection schedule · Zorin OS',`<form id="schedule-form" class="form-grid">${field('hour','Hour (0–23)',c.hour,'number',true)}${field('minute','Minute (0–59)',c.minute,'number',true)}${field('timezone','IANA timezone',c.timezone,'text',true)}<button type="submit">Save and preview daily schedule</button></form><p>Next run reported by systemd: ${esc(schedule.next_run)}. Source must be enabled for collection; disabled sources are skipped.</p><p>${esc(schedule.preview.notes)}</p><p role="alert">${esc(schedule.warning||schedule.manager_error)}</p><h3>Exact setup steps</h3><ol>${schedule.preview.steps.map(s=>`<li><code>${esc(s)}</code></li>`).join('')}</ol><h3>Reviewed service unit</h3><pre id="schedule-service">${esc(schedule.preview.service)}</pre><h3>Reviewed timer unit</h3><pre id="schedule-timer">${esc(schedule.preview.timer)}</pre><h3>Reviewed investigation worker</h3><pre id="schedule-worker-service">${esc(schedule.preview.investigation_service)}</pre><h3>Reviewed investigation timer</h3><pre id="schedule-worker-timer">${esc(schedule.preview.investigation_timer)}</pre><p>Investigation timer active: ${schedule.investigation_worker?.active?'Yes':'No'}. Retained evidence processing makes no source requests or commercial submissions.</p><p>Preview SHA-256: ${esc(schedule.preview.digest)}</p><label><input id="schedule-reviewed" type="checkbox"> I reviewed these units and authorize daily collection and investigation processing; CEQA acquisition requires its own reviewed plan</label><button id="schedule-install" ${schedule.available?'':'disabled'}>Install reviewed daily schedule</button><button id="schedule-disable">Disable collection and investigation schedules</button><p id="schedule-result" role="status"></p>`);bindForm('schedule-form',async f=>{const next=await api('/api/schedule',{hour:Number(f.hour),minute:Number(f.minute),timezone:f.timezone});openSchedule(next);});$('schedule-install').onclick=async()=>{try{if(!$('schedule-reviewed').checked)throw Error('Review and acknowledge the unit preview first');const next=await api('/api/schedule-install',{reviewed:true,digest:schedule.preview.digest});$('action-dialog').close();await reload();await openWorkspace('Sources & Collection');if(!next.active)throw Error('Timer is not active');}catch(e){$('schedule-result').textContent=e.message;}};$('schedule-disable').onclick=async()=>{try{const next=await api('/api/schedule-disable',{});openSchedule(next);await reload();}catch(e){$('schedule-result').textContent=e.message;}};}
