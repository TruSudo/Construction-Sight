'use strict';
async function openLiveRelationshipGraph(box){
 box.querySelectorAll('[data-shared-investigations]').forEach(h=>h.dispatchEvent(new Event('investigation-dispose')));
 const host=document.createElement('section');host.className='live-graph';host.dataset.liveGraph='true';box.replaceChildren(host);
 host.innerHTML='<div class="graph-toolbar"><strong>Relationship Graph</strong><button data-graph-full>Expand full screen</button><button data-graph-pause>Pause display</button><button data-graph-refresh>Reconnect / refresh</button><button data-graph-back>Entity inventory</button></div>'+
 '<div class="graph-toolbar"><label>Root ID <input data-graph-root aria-label="Graph root ID" placeholder="All retained roots (bounded)" maxlength="255"></label><label>Depth <select data-graph-depth aria-label="Graph relationship depth"><option>1</option><option>2</option><option>3</option></select></label><button data-graph-load>Load retained neighborhood</button><input data-graph-search aria-label="Find graph node" placeholder="Find in this snapshot"><label>Relationships <select data-graph-status-filter aria-label="Graph relationship status"><option value="">All current</option><option value="confirmed">Confirmed assertion</option><option value="possible">Possible</option><option value="conflicting">Conflicting</option><option value="retained_reference">Retained evidence references</option></select></label><button data-graph-fit>Reset view</button><button data-graph-group>Arrange by node type</button><button data-graph-family-group>Group by retained source</button><label><input type="checkbox" data-graph-activity> Highlight actual activity</label></div>'+
 '<div class="graph-toolbar graph-investigation-controls"><label>Source family <select data-graph-source aria-label="Filter graph by retained source family"><option value="">All retained families</option></select></label><label>Record updated since <input type="date" data-graph-since aria-label="Filter graph by retained record date"></label><label>Minimum assertion confidence <input data-graph-confidence type="number" min="0" max="100" step="10" value="0" aria-label="Minimum assertion confidence"></label><label><input type="checkbox" data-graph-collapse-evidence> Collapse evidence nodes</label><button data-graph-clear-filters>Clear filters</button></div>'+
 '<div class="graph-toolbar graph-saved-controls"><label>View name <input data-graph-view-name maxlength="60" aria-label="Name this local graph layout" placeholder="e.g. Riverside permits"></label><button data-graph-save>Save local view</button><label>Saved local views <select data-graph-view-list aria-label="Select saved graph view"><option value="">Select view…</option></select></label><button data-graph-restore>Restore view</button><button data-graph-delete>Delete view</button><span data-graph-storage-status role="status" class="graph-key"></span></div>'+
 '<div class="graph-toolbar graph-history-controls"><strong>Retained history</strong><label>Revision <select data-graph-history aria-label="Select a retained graph revision"><option value="">Select a recorded revision…</option></select></label><button data-graph-history-open>View historical state</button><button data-graph-history-more>Older revisions</button><button data-graph-history-compare>Compare with current</button><button data-graph-history-live>Return to live</button><span data-graph-history-status role="status"></span></div><p data-graph-history-diff class="graph-key" aria-live="polite"></p>'+
 '<p class="graph-key">Filters affect display only. Date means retained observation/retrieval or last update, not physical construction. Confidence is a source-backed assertion score, not identity verification. Layouts/filters are stored only in this browser, never as evidence.</p><p data-graph-filter-summary class="graph-key" aria-live="polite"></p>'+
 '<p data-graph-connection role="status">Loading authoritative graph…</p><p class="graph-key">Solid: retained reference or confirmed assertion · dashed: unresolved assertion · red: conflict. Source-claimed identity and construction remain unverified.</p>'+
 '<div class="graph-body"><div class="graph-canvas-wrap"><svg data-graph-canvas role="img" aria-label="Live retained investigation relationship graph" viewBox="0 0 1100 650"><g data-graph-world></g></svg><div class="graph-zoom"><button data-graph-zoom="1.2" aria-label="Zoom graph in">+</button><button data-graph-zoom="0.833333" aria-label="Zoom graph out">−</button></div></div><div class="graph-inspector" data-graph-inspector><h3>Evidence inspector</h3><p>Select a retained node or relationship.</p></div></div>'+
 '<details open><summary>Actual recorded processing and graph events</summary><p>Pausing or closing this display does not stop the worker. Activity below is persisted; no simulated investigations are shown. Showing at most 100 delivered events.</p><ol data-graph-events></ol></details>';
 const canvas=host.querySelector('[data-graph-canvas]'),world=host.querySelector('[data-graph-world]'),connection=host.querySelector('[data-graph-connection]'),inspector=host.querySelector('[data-graph-inspector]');
 let snapshot=null,cursor=0,eventCursor=null,anchor=null,disposed=false,paused=false,timer=null,request=0,busy=false,selection=null;
 let transform={x:0,y:0,k:1},drag=null,historyMode=null,historyBefore=0,historyItems=[];const positions=new Map(),seenEvents=new Set(),eventLog=[];
 let highlightedIds=new Set();
 const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
 const viewKey='constructionsight.graph-layouts.v1';
 const viewStatus=host.querySelector('[data-graph-storage-status]');
 let pinnedLayout=false;
 let localViews=[];
 function viewMessage(message){viewStatus.textContent=message;}
 function readLocalViews(){
  try{
   const raw=JSON.parse(localStorage.getItem(viewKey)||'[]');
   return Array.isArray(raw)?raw.filter(v=>v&&typeof v.name==='string'&&v.name.length>0&&v.name.length<=60&&
    typeof v.root==='string'&&v.root.length<=255&&Number.isInteger(v.depth)&&v.depth>=1&&v.depth<=3&&
    Array.isArray(v.points)&&v.points.length<=250&&v.points.every(p=>Array.isArray(p)&&p.length===3&&
     typeof p[0]==='string'&&p[0].length<=255&&Number.isFinite(p[1])&&Number.isFinite(p[2]))).slice(0,12):[];
  }catch(e){viewMessage('Browser storage unavailable or unreadable; retained evidence unaffected.');return [];}
 }
 function listLocalViews(selected=''){
  const select=host.querySelector('[data-graph-view-list]');
  select.innerHTML='<option value="">Select view…</option>'+localViews.map((v,i)=>
   '<option value="'+i+'">'+esc(v.name)+'</option>').join('');
  if(selected!=='')select.value=String(selected);
 }
 function saveLocalView(){
  if(!snapshot){viewMessage('Load a retained graph first.');return;}
  const name=host.querySelector('[data-graph-view-name]').value.trim();
  if(!name||name.length>60){viewMessage('View name must have 1–60 characters.');return;}
  const filters={source:host.querySelector('[data-graph-source]').value,
   since:host.querySelector('[data-graph-since]').value,
   confidence:Math.max(0,Math.min(100,Number(host.querySelector('[data-graph-confidence]').value)||0)),
   collapseEvidence:host.querySelector('[data-graph-collapse-evidence]').checked,
   status:host.querySelector('[data-graph-status-filter]').value};
  const view={name,root:host.querySelector('[data-graph-root]').value.trim(),
   depth:Number(host.querySelector('[data-graph-depth]').value),filters,
   transform:{...transform},points:[...positions].slice(0,250).map(([id,p])=>[id,p.x,p.y])};
  const duplicate=localViews.findIndex(v=>v.name.toLowerCase()===name.toLowerCase()),next=localViews.slice();
  if(duplicate>=0)next[duplicate]=view;
  else{if(next.length>=12){viewMessage('Maximum 12 browser-local views; delete one first.');return;}next.push(view);}
  try{
   localStorage.setItem(viewKey,JSON.stringify(next));localViews=next;
   listLocalViews(duplicate>=0?duplicate:next.length-1);
   viewMessage('Layout saved locally; no evidence or identities were copied.');
  }catch(e){viewMessage('Browser storage refused the view; retained graph unchanged.');}
 }
 async function restoreLocalView(){
  const selection=host.querySelector('[data-graph-view-list]').value,index=Number(selection),view=localViews[index];
  if(selection===''||!view){viewMessage('Select a saved view.');return;}
  host.querySelector('[data-graph-root]').value=view.root;
  host.querySelector('[data-graph-depth]').value=String(view.depth);
  if(!await loadSnapshot()){viewMessage('The saved root is unavailable; current graph history was not fabricated.');return;}
  const f=view.filters||{};
  host.querySelector('[data-graph-source]').value=f.source||'';
  host.querySelector('[data-graph-since]').value=f.since||'';
  host.querySelector('[data-graph-confidence]').value=String(Math.max(0,Math.min(100,Number(f.confidence)||0)));
  host.querySelector('[data-graph-collapse-evidence]').checked=Boolean(f.collapseEvidence);
  host.querySelector('[data-graph-status-filter]').value=f.status||'';
  const ids=new Set(snapshot.nodes.map(n=>n.id));
  positions.clear();
  for(const [id,x,y] of view.points)if(ids.has(id)&&Math.abs(x)<=100000&&Math.abs(y)<=100000)positions.set(id,{x,y});
  pinnedLayout=true;locate();
  const t=view.transform||{};
  transform={x:Number.isFinite(t.x)?Math.max(-100000,Math.min(100000,t.x)):0,
   y:Number.isFinite(t.y)?Math.max(-100000,Math.min(100000,t.y)):0,
   k:Number.isFinite(t.k)?Math.max(.2,Math.min(5,t.k)):1};
  host.querySelector('[data-graph-view-name]').value=view.name;
  render();viewMessage('Restored layout on current retained graph; historical state not implied.');
 }
 function deleteLocalView(){
  const selected=host.querySelector('[data-graph-view-list]').value,index=Number(selected);
  if(selected===''||!localViews[index]){viewMessage('Select a saved view.');return;}
  const next=localViews.filter((_,i)=>i!==index);
  try{localStorage.setItem(viewKey,JSON.stringify(next));localViews=next;listLocalViews();
   viewMessage('Saved browser layout deleted; retained graph unchanged.');}
  catch(e){viewMessage('Unable to change browser storage.');}
 }
 localViews=readLocalViews();listLocalViews();
 function applyTransform(){world.setAttribute('transform','translate('+transform.x+' '+transform.y+') scale('+transform.k+')');}
 function color(node){return node.status==='conflicting'?'#f05c66':node.kind==='evidence'?'#87a9b1':node.kind==='investigation'?'#f2b647':'#b8c0c7';}
 function locate(){
  const count=snapshot.nodes.length;
  snapshot.nodes.forEach((node,i)=>{if(!positions.has(node.id)){const angle=(i*2.399963229728653),radius=50+230*Math.sqrt((i+1)/Math.max(1,count));positions.set(node.id,{x:550+Math.cos(angle)*radius,y:325+Math.sin(angle)*radius});}});
  for(const key of positions.keys())if(!snapshot.nodes.some(n=>n.id===key))positions.delete(key);
  // A bounded force layout computes positions only; it never creates relationships.
  const nodes=snapshot.nodes;
  if(pinnedLayout)return;
  for(let turn=0;turn<35;turn++){
   for(let i=0;i<nodes.length;i++)for(let j=i+1;j<nodes.length;j++){
    const a=positions.get(nodes[i].id),b=positions.get(nodes[j].id);let dx=a.x-b.x,dy=a.y-b.y,d2=dx*dx+dy*dy;
    if(d2<1){dx=1;dy=1;d2=2;}const force=Math.min(2,800/d2),fx=dx*force*.08,fy=dy*force*.08;
    a.x+=fx;a.y+=fy;b.x-=fx;b.y-=fy;
   }
   for(const edge of snapshot.edges){const a=positions.get(edge.source),b=positions.get(edge.target);if(!a||!b)continue;
    const dx=b.x-a.x,dy=b.y-a.y,length=Math.hypot(dx,dy)||1,f=(length-115)*.008;
    a.x+=dx/length*f;a.y+=dy/length*f;b.x-=dx/length*f;b.y-=dy/length*f;
   }
   for(const point of positions.values()){point.x=Math.max(50,Math.min(1050,point.x+(550-point.x)*.001));point.y=Math.max(40,Math.min(600,point.y+(325-point.y)*.001));}
  }
 }
 function render(){
  if(!snapshot)return;
  const focusedNode=document.activeElement?.dataset?.liveNode,focusedEdge=document.activeElement?.dataset?.liveEdge;
  const query=host.querySelector('[data-graph-search]').value.trim().toLowerCase(),status=host.querySelector('[data-graph-status-filter]').value;
  const source=host.querySelector('[data-graph-source]').value,
   since=host.querySelector('[data-graph-since]').value,
   confidence=Math.max(0,Math.min(100,Number(host.querySelector('[data-graph-confidence]').value)||0)),
   collapsed=host.querySelector('[data-graph-collapse-evidence]').checked;
  const edges=snapshot.edges.filter(e=>(!status||e.status===status)&&
   (!source||e.source_family===source)&&
   (!since||(typeof e.last_seen==='string'&&e.last_seen.slice(0,10)>=since))&&
   (!collapsed||e.kind!=='retained_reference')&&
   (e.kind!=='relationship'||e.confidence>=confidence)),visible=new Set();
  for(const e of edges){visible.add(e.source);visible.add(e.target);}
  const filterActive=Boolean(status||source||since||collapsed||confidence);
  const nodes=snapshot.nodes.filter(n=>(!collapsed||n.kind!=='evidence')&&
   (!filterActive||visible.has(n.id))&&(!query||[n.label,n.id,n.kind].join(' ').toLowerCase().includes(query)));
  host.querySelector('[data-graph-filter-summary]').textContent=
   'Displaying '+nodes.length+' of '+snapshot.nodes.length+' retained nodes; '+
   edges.length+' of '+snapshot.edges.length+' edges pass relationship filters. No graph facts were changed.';
  const ids=new Set(nodes.map(n=>n.id));
  world.innerHTML=edges.filter(e=>ids.has(e.source)&&ids.has(e.target)).map(e=>{
   const a=positions.get(e.source),b=positions.get(e.target),uncertain=['possible','probable','unresolved'].includes(e.status);
   return '<path data-live-edge="'+esc(e.id)+'" tabindex="0" role="button" aria-label="'+esc(e.predicate+' · '+e.status)+'" d="M'+a.x+' '+a.y+'L'+b.x+' '+b.y+'" fill="none" stroke="'+(e.status==='conflicting'?'#f05c66':uncertain?'#b89145':'#65737a')+'" stroke-width="2" stroke-dasharray="'+(uncertain?'6 4':'none')+'"><title>'+esc(e.predicate+' · '+e.status)+'</title></path>';
  }).join('')+nodes.map(n=>{const p=positions.get(n.id),fill=color(n),chosen=selection?.id===n.id;
   const active=!historyMode&&host.querySelector('[data-graph-activity]').checked&&highlightedIds.has(n.id);
   return '<g data-live-node="'+esc(n.id)+'" transform="translate('+p.x+' '+p.y+')" tabindex="0" role="button" aria-label="'+esc(n.kind+': '+n.label)+'"><circle r="'+(chosen?17:12)+'" fill="#222a30" stroke="'+(active?'#fff2b7':fill)+'" stroke-width="'+(chosen||active?4:2)+'"/><circle r="4" fill="'+fill+'"/><text y="31" text-anchor="middle" fill="#dce0e2">'+esc(n.label.slice(0,31))+'</text><title>'+esc(n.label+' · '+n.kind+' · '+n.id)+'</title></g>';
  }).join('');
  applyTransform();
  world.querySelectorAll('[data-live-node]').forEach(g=>{g.onclick=()=>inspectNode(g.dataset.liveNode);g.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();inspectNode(g.dataset.liveNode);}};});
  world.querySelectorAll('[data-live-edge]').forEach(g=>{g.onclick=()=>inspectEdge(g.dataset.liveEdge);g.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();inspectEdge(g.dataset.liveEdge);}};});
  if(focusedNode)[...world.querySelectorAll('[data-live-node]')].find(g=>g.dataset.liveNode===focusedNode)?.focus();
  else if(focusedEdge)[...world.querySelectorAll('[data-live-edge]')].find(g=>g.dataset.liveEdge===focusedEdge)?.focus();
  if(!reduced)host.dataset.reducedMotion='false';
 }
 function inspectEdge(id){
  const edge=snapshot.edges.find(e=>e.id===id);if(!edge)return;selection={id,kind:'edge'};
  inspector.innerHTML='<h3>'+esc(edge.predicate)+'</h3><p>'+esc(edge.status)+' · persisted assertion/reference, not independent identity verification.</p><p>Source: '+esc(edge.source_family||'not reported')+' · Last retained date: '+esc(edge.last_seen||'not reported')+' · Basis: '+esc(edge.date_basis||'not reported')+'</p><pre>'+esc(JSON.stringify(edge,null,2))+'</pre>';
 }
 function inspectNode(id){
  const node=snapshot.nodes.find(n=>n.id===id);if(!node)return;selection={id,kind:'node'};
  inspector.innerHTML='<h3>'+esc(node.label)+'</h3><p>'+esc(node.kind)+' · '+esc(node.status)+'</p><code>'+esc(node.id)+'</code><p>Identity independently verified: No. Commercial authority is not granted by this view.</p>'+
   '<button data-graph-expand-node>Expand retained neighborhood</button>'+
   (node.kind==='investigation'&&!historyMode?'<button data-graph-dossier>Open canonical dossier</button><button data-graph-map>Locate source-claimed point on Site Map</button>':node.kind==='investigation'?'<p>Historical view: current dossiers and map points are intentionally unavailable here; do not confuse them with period evidence.</p>':'')+
   '<h4>Retained evidence</h4>'+(node.evidence_ids||[]).map((e,i)=>'<button data-graph-evidence="'+i+'">'+esc(e)+'</button>').join('')+'<div data-graph-artifact></div>';
  inspector.querySelector('[data-graph-expand-node]').onclick=()=>{host.querySelector('[data-graph-root]').value=node.id;loadSnapshot();};
  const dossier=inspector.querySelector('[data-graph-dossier]');if(dossier)dossier.onclick=()=>perform(()=>openInvestigationDossier(node.canonical_id||node.id));
  const mapButton=inspector.querySelector('[data-graph-map]');
  if(mapButton)mapButton.onclick=()=>perform(async()=>{
   const id=node.canonical_id||node.id;
   const investigation=await api('/api/investigations/'+encodeURIComponent(id));
   if(disposed||!host.isConnected||selection?.id!==node.id)return;
   const points=(investigation.source_claimed_points||[]).filter(p=>
    typeof p.latitude==='number'&&typeof p.longitude==='number'&&Number.isFinite(p.latitude)&&
    Number.isFinite(p.longitude)&&Math.abs(p.latitude)<=85&&Math.abs(p.longitude)<=180);
   if(!points.length){
    mapButton.insertAdjacentHTML('afterend','<p role="status">Unmapped investigation: no complete retained source-claimed coordinates. No map location is inferred.</p>');
    return;
   }
   await openWorkspace('Site Map');
   if(activePage!=='Site Map')return;
   if(!activeInvestigationMapRows.some(row=>row.investigation_id===id))
    activeInvestigationMapRows.push({investigation_id:id,
     title:investigation.investigation?.project_name||id,points});
   center=[points[0].latitude,points[0].longitude];zoom=14;drawMap();
  });
  inspector.querySelectorAll('[data-graph-evidence]').forEach(b=>b.onclick=()=>perform(async()=>{
   const evidenceId=node.evidence_ids[Number(b.dataset.graphEvidence)],value=await api('/api/investigation-graph/evidence?id='+encodeURIComponent(evidenceId));
   if(disposed||selection?.id!==node.id)return;
   const artifact=inspector.querySelector('[data-graph-artifact]');if(artifact)artifact.innerHTML='<pre>'+esc(JSON.stringify(value.evidence,null,2))+'</pre>';
  }));
  render();
 }
 function arrangeByKind(){
  if(!snapshot)return;
  const groups=[...new Set(snapshot.nodes.map(n=>n.kind))].sort();
  const columns=Math.min(4,Math.max(1,Math.ceil(Math.sqrt(groups.length))));
  const tileWidth=1000/columns,tileRows=Math.ceil(groups.length/columns),tileHeight=550/tileRows;
  positions.clear();
  for(const [index,kind] of groups.entries()){
   const members=snapshot.nodes.filter(n=>n.kind===kind).sort((a,b)=>a.id.localeCompare(b.id));
   const countColumns=Math.min(8,Math.max(1,Math.ceil(Math.sqrt(members.length))));
   const horizontal=Math.max(35,Math.min(110,(tileWidth-20)/countColumns));
   const vertical=Math.max(20,Math.min(70,(tileHeight-20)/Math.ceil(members.length/countColumns)));
   const startX=55+(index%columns)*tileWidth,startY=55+Math.floor(index/columns)*tileHeight;
   members.forEach((n,i)=>positions.set(n.id,{x:startX+(i%countColumns)*horizontal,
    y:startY+Math.floor(i/countColumns)*vertical}));
  }
  pinnedLayout=true;transform={x:0,y:0,k:1};render();
  viewMessage('Arranged exact retained nodes by recorded kind; no new relationships or inferred clusters.');
 }
 function arrangeBySource(){
  if(!snapshot)return;
  const buckets=new Map();
  for(const node of snapshot.nodes){
   const sourceFamilies=[...new Set(snapshot.edges.filter(e=>e.source===node.id||e.target===node.id)
    .map(e=>e.source_family).filter(Boolean))].sort();
   const source=sourceFamilies[0]||node.source_family||'unknown source';
   if(!buckets.has(source))buckets.set(source,[]);
   buckets.get(source).push(node);
  }
  const keys=[...buckets.keys()].sort();
  const columns=Math.min(4,Math.max(1,Math.ceil(Math.sqrt(keys.length))));
  positions.clear();
  for(const [groupIndex,source] of keys.entries()){
   const members=buckets.get(source).sort((a,b)=>a.id.localeCompare(b.id));
   const x=80+(groupIndex%columns)*1000/columns;
   const y=70+Math.floor(groupIndex/columns)*Math.max(90,520/Math.ceil(keys.length/columns));
   members.forEach((n,i)=>positions.set(n.id,{x:x+(i%5)*35,y:y+Math.floor(i/5)*38}));
  }
  pinnedLayout=true;transform={x:0,y:0,k:1};render();
  viewMessage('Arranged by recorded source-family attribution (unknowns separate); edges and identities unchanged.');
 }
 async function loadHistoryIndex(){
  try{
   const params=historyBefore?'?after='+historyBefore:'';
   const result=await api('/api/investigation-graph/history-index'+params);
   if(disposed||!host.isConnected)return;
   for(const item of result.events||[]){
    if(!historyItems.some(old=>old.sequence===item.sequence))historyItems.push(item);
   }
   const select=host.querySelector('[data-graph-history]'),previous=select.value;
   select.innerHTML='<option value="">Select a recorded revision…</option>'+historyItems.map((v,i)=>
    '<option value="'+i+'">'+esc(v.created_at)+' · '+esc(v.message)+' (#'+v.sequence+')</option>').join('');
   if(previous)select.value=previous;
   historyBefore=result.next_before||0;
   host.querySelector('[data-graph-history-more]').disabled=!result.has_more;
   host.querySelector('[data-graph-history-status]').textContent=historyItems.length+' recorded revision choices; bounded to 100 per page.';
  }catch(e){if(!disposed)host.querySelector('[data-graph-history-status]').textContent='Retained history index unavailable: '+e.message;}
 }
 async function openHistorical(){
  const choice=host.querySelector('[data-graph-history]').value;
  if(choice===''){host.querySelector('[data-graph-history-status]').textContent='Select a retained revision.';return;}
  const chosen=historyItems[Number(choice)];if(!chosen)return;
  const previous=historyMode;
  historyMode={sequence:chosen.sequence,event_id:chosen.event_id};
  highlightedIds.clear();pinnedLayout=false;positions.clear();
  if(!await loadSnapshot()){
   historyMode=previous;positions.clear();
   await loadSnapshot();
   host.querySelector('[data-graph-history-status]').textContent='Historical replay unavailable for that revision; current display restored.';
   return;
  }
  host.querySelector('[data-graph-history-diff]').textContent='';
  host.querySelector('[data-graph-history-status]').textContent=
   'Replaying exact retained revision #'+chosen.sequence+'; live worker remains independent.';
 }
 async function returnToLive(){
  historyMode=null;pinnedLayout=false;positions.clear();
  await loadSnapshot();host.querySelector('[data-graph-history-diff]').textContent='';
  host.querySelector('[data-graph-history-status]').textContent='Current committed graph; historical source truth is never inferred.';
 }
 async function compareHistory(){
  if(!historyMode||!snapshot){host.querySelector('[data-graph-history-diff]').textContent='Select a historical view to compare.';return;}
  const params=new URLSearchParams({depth:host.querySelector('[data-graph-depth]').value});
  const root=host.querySelector('[data-graph-root]').value.trim();if(root)params.set('root',root);
  const latest=await api('/api/investigation-graph?'+params);
  if(!latest.available)return;
  const compare=(older,newer)=>{
   const old=new Map(older.map(x=>[x.id,JSON.stringify(x)]));
   const now=new Map(newer.map(x=>[x.id,JSON.stringify(x)]));
   return {added:[...now.keys()].filter(x=>!old.has(x)),removed:[...old.keys()].filter(x=>!now.has(x)),
    changed:[...old.keys()].filter(x=>now.has(x)&&old.get(x)!==now.get(x))};
  };
  const nodes=compare(snapshot.nodes,latest.nodes),edges=compare(snapshot.edges,latest.edges);
  host.querySelector('[data-graph-history-diff]').textContent='Compared with currently retained graph: nodes +'+nodes.added.length+
   ' / -'+nodes.removed.length+' / revised '+nodes.changed.length+'; relationships +'+edges.added.length+
   ' / -'+edges.removed.length+' / revised '+edges.changed.length+
   '. Differences are between bounded snapshots, not a claim of exhaustive jurisdictional history.';
 }
 function stateLabel(extra=''){
  connection.textContent=(historyMode?'Historical retained graph (not live)':paused?'Display paused':'Connected')+' · committed revision '+cursor+' · '+(snapshot?.nodes.length||0)+' nodes / '+(snapshot?.edges.length||0)+' edges'+
   (snapshot?.truncated?' · bounded neighborhood: more retained graph data exist':'')+(extra?' · '+extra:'');
  host.dataset.graphCursor=String(cursor);
 }
 async function loadSnapshot(resetEvents=false){
  if(disposed||!host.isConnected)return;
  const ticket=++request;busy=true;
  try{
   const params=new URLSearchParams({depth:host.querySelector('[data-graph-depth]').value}),root=host.querySelector('[data-graph-root]').value.trim();if(root)params.set('root',root);
   if(historyMode){params.set('after',String(historyMode.sequence));params.set('anchor',historyMode.event_id);}
   const value=await api('/api/investigation-graph'+(historyMode?'/history':'')+'?'+params);
   if(disposed||!host.isConnected||ticket!==request)return;
   if(!value.available){connection.textContent='Investigation store unavailable. No graph count is asserted.';return;}
   snapshot=value;cursor=value.cursor;if(!historyMode&&(eventCursor===null||resetEvents)){eventCursor=value.cursor;anchor=value.anchor;}
   const sourceSelect=host.querySelector('[data-graph-source]'),currentSource=sourceSelect.value;
   const families=[...new Set(value.edges.map(e=>e.source_family).filter(f=>typeof f==='string'&&f))].sort();
   sourceSelect.innerHTML='<option value="">All retained families</option>'+families.map(f=>
    '<option value="'+esc(f)+'">'+esc(f)+'</option>').join('');
   if(families.includes(currentSource))sourceSelect.value=currentSource;
   locate();render();stateLabel();
   if(selection?.kind==='node'&&snapshot.nodes.some(n=>n.id===selection.id))inspectNode(selection.id);
   else if(selection?.kind==='edge'&&snapshot.edges.some(e=>e.id===selection.id))inspectEdge(selection.id);
   else if(selection){selection=null;inspector.innerHTML='<p>The selected item is outside the current retained snapshot. Refresh or select another item.</p>';}
   return true;
  }catch(e){if(!disposed&&ticket===request)connection.textContent='Disconnected: '+e.message+'. Retained display may be stale.';return false;}
  finally{if(ticket===request)busy=false;}
 }
 async function poll(){
  if(disposed||!host.isConnected)return;
  try{
   if(!paused&&!historyMode&&!busy&&!document.hidden){
    const ticket=request,params=new URLSearchParams({after:String(eventCursor??cursor)});if(anchor)params.set('anchor',anchor);
    const value=await api('/api/investigation-graph/events?'+params);
    if(disposed||!host.isConnected||ticket!==request)return;
    if(!value.available){connection.textContent='Investigation store unavailable; retained graph may be stale.';}
    else if(value.reset_required){seenEvents.clear();eventLog.length=0;host.querySelector('[data-graph-events]').replaceChildren();await loadSnapshot(true);}
    else{
     for(const event of value.events||[])if(!seenEvents.has(event.event_id)){
      seenEvents.add(event.event_id);eventLog.push(event);
     }
     while(eventLog.length>100){seenEvents.delete(eventLog.shift().event_id);}
     host.querySelector('[data-graph-events]').innerHTML=eventLog.slice().reverse().map(e=>'<li data-graph-event="'+esc(e.event_id)+'"><time>'+esc(e.created_at)+'</time> <strong>'+esc(e.event_type)+'</strong> '+esc(e.message)+'</li>').join('');
     eventCursor=value.cursor;anchor=value.anchor;
     highlightedIds=new Set((value.events||[]).flatMap(e=>[...(e.entity_refs||[]),...(e.project_cluster_refs||[])]));
     if(value.events?.length)await loadSnapshot();else {render();stateLabel('event connection current');}
    }
   }
  }catch(e){if(!disposed)connection.textContent='Disconnected: '+e.message+'. Retained display may be stale; reconnect will recover from the durable cursor.';}
  finally{if(!disposed&&host.isConnected)timer=setTimeout(poll,1500);}
 }
 function dispose(){disposed=true;request++;clearTimeout(timer);document.removeEventListener('keydown',escape);}
 function escape(e){if(e.key==='Escape'&&host.classList.contains('graph-expanded')){host.classList.remove('graph-expanded');host.querySelector('[data-graph-full]').textContent='Expand full screen';}}
 host.addEventListener('graph-dispose',dispose,{once:true});document.addEventListener('keydown',escape);
 host.querySelector('[data-graph-full]').onclick=()=>{host.classList.toggle('graph-expanded');host.querySelector('[data-graph-full]').textContent=host.classList.contains('graph-expanded')?'Return to embedded graph':'Expand full screen';};
 host.querySelector('[data-graph-pause]').onclick=()=>{paused=!paused;host.querySelector('[data-graph-pause]').textContent=paused?'Resume display':'Pause display';stateLabel();if(!paused)loadSnapshot();};
 host.querySelector('[data-graph-refresh]').onclick=()=>loadSnapshot();
 host.querySelector('[data-graph-load]').onclick=()=>loadSnapshot();
 host.querySelector('[data-graph-back]').onclick=()=>{dispose();openWorkspace('Entity Network');};
 host.querySelector('[data-graph-search]').oninput=render;host.querySelector('[data-graph-status-filter]').onchange=render;
 for(const selector of ['[data-graph-source]','[data-graph-since]','[data-graph-confidence]','[data-graph-collapse-evidence]'])
  host.querySelector(selector).addEventListener('change',render);
 host.querySelector('[data-graph-clear-filters]').onclick=()=>{
  host.querySelector('[data-graph-search]').value='';
  host.querySelector('[data-graph-status-filter]').value='';
  host.querySelector('[data-graph-source]').value='';
  host.querySelector('[data-graph-since]').value='';
  host.querySelector('[data-graph-confidence]').value='0';
  host.querySelector('[data-graph-collapse-evidence]').checked=false;render();
 };
 host.querySelector('[data-graph-save]').onclick=saveLocalView;
 host.querySelector('[data-graph-restore]').onclick=()=>perform(restoreLocalView);
 host.querySelector('[data-graph-delete]').onclick=deleteLocalView;
 host.querySelector('[data-graph-fit]').onclick=()=>{transform={x:0,y:0,k:1};applyTransform();};
 host.querySelector('[data-graph-group]').onclick=arrangeByKind;
 host.querySelector('[data-graph-family-group]').onclick=arrangeBySource;
 host.querySelector('[data-graph-activity]').onchange=render;
 host.querySelector('[data-graph-history-open]').onclick=()=>perform(openHistorical);
 host.querySelector('[data-graph-history-more]').onclick=()=>perform(loadHistoryIndex);
 host.querySelector('[data-graph-history-live]').onclick=()=>perform(returnToLive);
 host.querySelector('[data-graph-history-compare]').onclick=()=>perform(compareHistory);
 host.querySelectorAll('[data-graph-zoom]').forEach(b=>b.onclick=()=>{transform.k=Math.max(.2,Math.min(5,transform.k*Number(b.dataset.graphZoom)));applyTransform();});
 canvas.onwheel=e=>{e.preventDefault();transform.k=Math.max(.2,Math.min(5,transform.k*(e.deltaY<0?1.1:1/1.1)));applyTransform();};
 function coords(e){const matrix=canvas.getScreenCTM();if(!matrix)return {x:0,y:0};const p=new DOMPoint(e.clientX,e.clientY).matrixTransform(matrix.inverse());return {x:p.x,y:p.y};}
 canvas.onpointerdown=e=>{const p=coords(e),node=e.target.closest('[data-live-node]')?.dataset.liveNode;drag={x:p.x,y:p.y,node,edge:e.target.closest('[data-live-edge]')?.dataset.liveEdge};canvas.setPointerCapture(e.pointerId);};
 canvas.onpointermove=e=>{if(!drag)return;const p=coords(e),dx=p.x-drag.x,dy=p.y-drag.y;drag.x=p.x;drag.y=p.y;if(drag.node){const n=positions.get(drag.node);n.x+=dx/transform.k;n.y+=dy/transform.k;render();}else{transform.x+=dx;transform.y+=dy;applyTransform();}};
 canvas.onpointerup=()=>{const previous=drag;drag=null;if(previous?.node)inspectNode(previous.node);else if(previous?.edge)inspectEdge(previous.edge);};
 await loadSnapshot();if(!disposed&&host.isConnected)await loadHistoryIndex();
 if(!disposed&&host.isConnected)timer=setTimeout(poll,1500);
}
