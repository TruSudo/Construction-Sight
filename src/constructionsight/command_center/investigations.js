'use strict';
// Read-only projections of the worker-owned investigation state. No local matching.
const investigationFilters={text:'',source:'',location:''};
let investigationSearchTicket=0,currentInvestigationIdentity=null,investigationDossierRevision=null;
async function refreshOpenInvestigationDossier(revision){
 if(currentInvestigationIdentity&&$('action-dialog').open&&investigationRevision(revision)!==investigationDossierRevision)
  await openInvestigationDossier(currentInvestigationIdentity,true);
}
function investigationParams(after,extra={}){
 const region=$('county').value,p=new URLSearchParams();
 if(after)p.set('after',after);
 const values={q:investigationFilters.text,source:investigationFilters.source,location:investigationFilters.location,
  ...(region.startsWith('city:')?{city:region.slice(5)}:{county:region}),...extra};
 for(const [k,v] of Object.entries(values))if(v)p.set(k,v);
 return '/api/investigations'+(p.size?'?'+p:'');
}
function investigationRegionOptions(rows){
 if(data.mockup_parity)return;
 const region=$('county'),existing=new Set([...region.options].map(o=>o.value));
 for(const row of rows)for(const [key,values] of [['county',row.counties||[]],['city',row.cities||[]]])
  for(const value of values){const id=key==='city'?'city:'+value:value;if(!existing.has(id)){
   const option=document.createElement('option');option.value=id;option.textContent=key==='city'?value+', CA (source-claimed)':value;
   region.append(option);existing.add(id);
  }}
}
async function renderInvestigationInventory(box,onPage=()=>{}){
 const host=document.createElement('section');host.className='feature-card';host.dataset.sharedInvestigations='true';box.append(host);
 host.innerHTML='<h3>Shared investigations</h3><div class="map-toolbar">'+
  '<input data-investigation-search aria-label="Search shared investigations" maxlength="255" placeholder="Search retained projects, identifiers and parties">'+
  '<label>Source <select data-investigation-source aria-label="Investigation source"><option value="">All sources</option>'+
  ['smarts','ceqa','permit','planning','parcel','agenda','document','intake'].map(x=>'<option>'+x+'</option>').join('')+'</select></label>'+
  '<label>Location <select data-investigation-location aria-label="Investigation location"><option value="">All locations</option><option value="mapped">Source-claimed point</option><option value="unmapped">Unmapped review queue</option></select></label>'+
  '<button data-investigation-reset>Clear investigation filters</button><button data-investigation-refresh>Refresh</button></div>'+
  '<p data-investigation-status role="status"></p><div data-investigation-rows></div>'+
  '<div data-investigation-network></div>';
 const status=host.querySelector('[data-investigation-status]'),results=host.querySelector('[data-investigation-rows]');
 let after=null,cursor=null,revisionKey=null,request=0,busy=false,networkId=null,networkTicket=0,pollTimer=null,disposed=false;
 const network=host.querySelector('[data-investigation-network]');
 const input=host.querySelector('[data-investigation-search]'),source=host.querySelector('[data-investigation-source]'),location=host.querySelector('[data-investigation-location]');
 input.value=investigationFilters.text;source.value=investigationFilters.source;location.value=investigationFilters.location;
 async function showNetwork(id){
  if(disposed)return;
  networkId=id;const ticket=++networkTicket;
  try{const dossier=await api('/api/investigations/'+encodeURIComponent(id));
   if((host.isConnected&&!disposed)&&ticket===networkTicket)renderSharedEntityNetwork(network,dossier);
  }catch(e){if((host.isConnected&&!disposed)&&ticket===networkTicket)network.innerHTML='<p role="alert">'+esc(e.message)+'</p>';}
 }
 async function page(nextAfter,quiet=false){
  if(disposed)return;
  const ticket=++request;busy=true;
  if(!quiet)status.textContent='Loading committed investigation state…';
  try{
   const snapshot=await api(investigationParams(nextAfter));
   if(!(host.isConnected&&!disposed)||ticket!==request)return;
   after=nextAfter;cursor=snapshot.event_cursor;revisionKey=investigationRevision(snapshot);
   if(!snapshot.available){onPage([]);results.replaceChildren();network.replaceChildren();status.textContent='Investigation store unavailable: the local worker has not initialized it. No count is asserted.';return;}
   const rows=snapshot.rows||[];investigationRegionOptions(rows);
   for(const r of rows)for(const record of r.source_records||[])if(record.source_family&&![...source.options].some(o=>o.value===record.source_family)){
    const option=document.createElement('option');option.value=record.source_family;option.textContent=record.source_family;source.append(option);
   }
   onPage(rows);
   status.textContent=rows.length+' matching investigations on this scan page · '+(snapshot.scanned_on_page??rows.length)+' records scanned · '+snapshot.total+' total retained (all scopes) · committed revision '+cursor+'.'+
    (snapshot.has_more?' More retained records remain; use Next records.':' End of retained inventory.')+
    ' Source claims do not establish current construction or commercial readiness.';
   results.innerHTML=table(['Investigation','County / city claims','Retained sources','Assessment','Explore'],rows.map(r=>[
    '<button data-investigation-id="'+esc(r.investigation_id)+'">'+esc(r.title||r.investigation_id)+'</button>',
    esc([...(r.counties||[]),...(r.cities||[])].join(', ')||'—'),
    esc((r.source_records||[]).map(x=>x.source_family).join(', ')||'—'),
    'Identity '+(r.assessment?.identity_independently_verified?'reviewed':'unverified')+
     (r.points?.length?' · source point claimed':' · unmapped')+' · readiness '+esc(r.assessment?.commercial_readiness||'unassessed'),
    '<button data-investigation-network-id="'+esc(r.investigation_id)+'">Entity relationships</button> '+
     '<button data-investigation-live-graph-id="'+esc(r.investigation_id)+'">Open live graph</button>'
   ]))+(rows.length?'':'<p>No matches on this scan page.'+(snapshot.has_more?' More records remain to search.':'')+'</p>')+
   (nextAfter?'<button data-investigation-first>First records</button> ':'')+
   (snapshot.has_more?'<button id="next-investigation-page" data-investigation-next>Next records</button>':'');
   results.querySelectorAll('[data-investigation-id]').forEach(b=>b.onclick=()=>perform(()=>openInvestigationDossier(b.dataset.investigationId)));
   results.querySelectorAll('[data-investigation-network-id]').forEach(b=>b.onclick=()=>showNetwork(b.dataset.investigationNetworkId));
   results.querySelectorAll('[data-investigation-live-graph-id]').forEach(b=>b.onclick=()=>perform(async()=>{
    const investigationId=b.dataset.investigationLiveGraphId;
    await openWorkspace('Entity Network');
    const section=$('section-content');
    await openLiveRelationshipGraph(section);
    const graph=section.querySelector('[data-live-graph]');
    if(graph){graph.querySelector('[data-graph-root]').value=investigationId;
     graph.querySelector('[data-graph-load]').click();}
   }));
   const next=results.querySelector('[data-investigation-next]');if(next)next.onclick=()=>page(snapshot.next_cursor);
   const first=results.querySelector('[data-investigation-first]');if(first)first.onclick=()=>page(null);
   if(networkId&&rows.some(r=>r.investigation_id===networkId))await showNetwork(networkId);
   else {networkId=null;network.replaceChildren();if(activePage==='Entity Network'&&rows.length)await showNetwork(rows[0].investigation_id);}
   if(!data.mockup_parity)for(const option of ['type','band','freshness','status-filter'])$(option).title='Commercial lead filter; shared investigations retain their independent evidence assessment.';
  }catch(e){if((host.isConnected&&!disposed)&&ticket===request){status.textContent='Investigation refresh failed: '+e.message+'. Previously displayed records may be stale.';}}
  finally{if(ticket===request)busy=false;}
 }
 let debounce;
 function change(){
  investigationFilters.text=input.value;investigationFilters.source=source.value;investigationFilters.location=location.value;
  clearTimeout(debounce);debounce=setTimeout(()=>page(null),200);
 }
 input.oninput=change;source.onchange=change;location.onchange=change;
 host.querySelector('[data-investigation-reset]').onclick=()=>{input.value='';source.value='';location.value='';change();};
 host.querySelector('[data-investigation-refresh]').onclick=()=>page(after);
 host.addEventListener('investigation-scope-change',()=>page(null));
 async function poll(){
  if(!(host.isConnected&&!disposed))return;
  try{
   if(!busy&&!document.hidden){
    const revision=await api('/api/investigations?revision=1');
    if(!(host.isConnected&&!disposed))return;
    if(!revision.available)status.textContent='Live refresh unavailable; investigation store is absent. Previously displayed records may be stale.';
    if(revision.available&&investigationRevision(revision)!==revisionKey){
     await page(after,true);
     if(currentInvestigationIdentity&&$('action-dialog').open)await openInvestigationDossier(currentInvestigationIdentity,true);
    }
   }
  }catch(e){if((host.isConnected&&!disposed))status.textContent='Live refresh disconnected; retained display may be stale. '+e.message;}
  finally{if((host.isConnected&&!disposed))pollTimer=setTimeout(poll,5000);}
 }
 await page(null);
 if((host.isConnected&&!disposed))pollTimer=setTimeout(poll,5000);
 // Timer owns only this connected view; detached views perform no further requests.
 host.addEventListener('investigation-dispose',()=>{disposed=true;clearTimeout(pollTimer);clearTimeout(debounce);request++;networkTicket++;},{once:true});
}
function renderSharedEntityNetwork(host,dossier){
 const root=dossier.investigation.project_cluster_id,nodes=new Map(),edges=new Map();
 nodes.set(root,{id:root,label:dossier.investigation.project_name||root,kind:'Investigation'});
 for(const s of dossier.source_membership||[])nodes.set(s.source_id,{id:s.source_id,label:s.source_family+': '+s.source_record_id,kind:'Source record',evidence:s.current_evidence_id});
 for(const p of dossier.source_parties||[]){
  nodes.set(p.entity.entity_id,{id:p.entity.entity_id,label:p.entity.canonical_name,kind:'Source-claimed '+p.entity.entity_type,evidence:p.entity.evidence_record_ids?.join(', ')});
  if(!nodes.has(p.relationship.object_entity_id))nodes.set(p.relationship.object_entity_id,{id:p.relationship.object_entity_id,label:p.relationship.object_entity_id,kind:'Retained investigation context'});
  edges.set(p.relationship.relationship_id,p.relationship);
 }
 for(const c of dossier.candidate_source_links||[])nodes.set(c.candidate_investigation_id,{id:c.candidate_investigation_id,label:'Candidate: '+c.candidate_investigation_id,kind:'Unresolved candidate'});
 for(const r of dossier.relationships||[])if(nodes.has(r.subject_entity_id)&&nodes.has(r.object_entity_id))edges.set(r.relationship_id,r);
 const inactive=new Set(['rejected','stale','superseded']),links=[...edges.values()].filter(r=>!inactive.has(r.relationship_status));
 const values=[...nodes.values()],positions=new Map(values.map((n,i)=>[n.id,[n.id===root?420:20+(i%2)*800,n.id===root?45:100+Math.floor(i/2)*75]]));
 const height=Math.max(180,140+Math.ceil(values.length/2)*75);
 host.innerHTML='<h3>Persisted entity relationships</h3><p>Canonical investigation: <code>'+esc(root)+'</code>. Source claims and candidates remain unverified; name similarity never creates an edge.</p>'+
  '<button data-network-dossier>Open this investigation dossier</button><div class="graph-scroll"><svg data-shared-entity-graph viewBox="0 0 1100 '+height+'" role="img" aria-label="Persisted investigation relationships">'+
  links.map(r=>{const a=positions.get(r.subject_entity_id),b=positions.get(r.object_entity_id);if(!a||!b)return '';return '<path data-relationship-id="'+esc(r.relationship_id)+'" d="M'+(a[0]+110)+' '+a[1]+'L'+(b[0]+110)+' '+b[1]+'" stroke="'+(r.relationship_status==='conflicting'?'#f13e44':'#b58b35')+'" stroke-dasharray="'+(['possible','probable','unresolved'].includes(r.relationship_status)?'5 4':'none')+'"><title>'+esc(r.predicate+' · '+r.relationship_status+' · '+r.evidence_summary)+'</title></path>';}).join('')+
  values.map((n,i)=>{const [x,y]=positions.get(n.id);return '<g data-shared-node="'+i+'" tabindex="0" role="button" aria-label="'+esc(n.kind+': '+n.label)+'"><rect x="'+x+'" y="'+(y-18)+'" width="220" height="36" rx="5" fill="#242424" stroke="#b58b35"/><text x="'+(x+8)+'" y="'+(y+4)+'" fill="#ddd">'+esc(n.label.slice(0,27))+'</text><title>'+esc(n.kind+' · '+n.label+' · '+n.id)+'</title></g>';}).join('')+'</svg></div><div data-shared-node-detail></div>'+
  table(['Relationship ID','Predicate','Status','Supporting evidence','Contradictory evidence'],links.map(r=>[esc(r.relationship_id),esc(r.predicate),esc(r.relationship_status),esc((r.supporting_evidence_ids||[]).join(', ')),esc((r.contradictory_evidence_ids||[]).join(', '))]))+
  '<p>'+(dossier.relationships_truncated||dossier.parties_truncated||dossier.candidate_links_truncated?'Projection is bounded; additional relationships may exist.':'Retained relationships for this dossier projection.')+'</p>';
 host.querySelector('[data-network-dossier]').onclick=()=>perform(()=>openInvestigationDossier(root));
 host.querySelectorAll('[data-shared-node]').forEach(b=>{
  b.onclick=()=>{const n=values[Number(b.dataset.sharedNode)];host.querySelector('[data-shared-node-detail]').innerHTML='<p>'+esc(n.kind)+': '+esc(n.label)+' · <code>'+esc(n.id)+'</code></p><p>Retained evidence: '+esc(n.evidence||'See relationship evidence above')+'</p>';};
  b.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();b.dispatchEvent(new MouseEvent('click',{bubbles:true}));}};
 });
}
async function appendInvestigationSearch(q){
 const ticket=++investigationSearchTicket;if(!q||data.mockup_parity)return;
 try{
  let after=null,found=[],remaining=false;
  // Bound each interactive search turn; expose continuation rather than assert completeness.
  for(let page=0;page<5;page++){
   const snapshot=await api(investigationParams(after,{q,source:'',location:''}));
   if(ticket!==investigationSearchTicket||$('search-results').hidden||$('search').value.trim().toLowerCase()!==q)return;
   if(!snapshot.available){$('search-results').insertAdjacentHTML('beforeend','<p>Shared investigation store unavailable; no investigation search count is asserted.</p>');return;}
   found.push(...snapshot.rows);remaining=snapshot.has_more;after=snapshot.next_cursor;
   if(found.length>=25||!remaining)break;
  }
  const host=$('search-results');host.insertAdjacentHTML('beforeend','<h4>Shared investigations</h4>');
  for(const r of found.slice(0,25)){
   const i=searchResults.length;searchResults.push({investigation:r.investigation_id});
   host.insertAdjacentHTML('beforeend','<button role="option" data-search-index="'+i+'" aria-selected="false"><b>'+esc(r.title||r.investigation_id)+'</b><span>'+esc((r.source_records||[]).map(s=>s.source_family).join(', '))+' · investigation, readiness unassessed</span></button>');
  }
  if(!found.length)host.insertAdjacentHTML('beforeend','<p>No matching investigations in the scanned records.</p>');
  if(remaining||found.length>25){host.insertAdjacentHTML('beforeend','<button data-search-investigations>Continue in shared investigation search</button>');host.querySelector('[data-search-investigations]').onclick=()=>{investigationFilters.text=q;investigationFilters.source='';investigationFilters.location='';hideSearch();openWorkspace('Project Intelligence');};}
 }catch(e){if(ticket===investigationSearchTicket&&!$('search-results').hidden)$('search-results').insertAdjacentHTML('beforeend','<p role="alert">Investigation search unavailable: '+esc(e.message)+'</p>');}
}

$('county').addEventListener('change',()=>document.querySelectorAll('[data-shared-investigations]').forEach(h=>h.dispatchEvent(new Event('investigation-scope-change'))));
