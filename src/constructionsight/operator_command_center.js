
"use strict";
const byId = id => document.getElementById(id);
const escapeText = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const identity = row => row.record_kind + ":" + row.record_id;
const WATCH_KEY = "constructionsight:operator:local-watchlist-v1";
let page = null, footprint = null, workflows = null, selected = null, selectedRecord = null, activeQuery = "", pageRequest = 0, featureRequest = 0, pageOffset = 0;
let localWatchlist = {};
let sourceRevision = null, sourceProbeActive = false;
let activeKind = "all", activeCounty = "";
try { const stored = JSON.parse(localStorage.getItem(WATCH_KEY) || "{}"); if (stored && typeof stored === "object" && !Array.isArray(stored)) localWatchlist = stored; } catch (_) { /* Browser-local preferences are optional. */ }
const records = () => page && Array.isArray(page.projects) ? page.projects : [];
function updateWatchCounters() { const count = Object.keys(localWatchlist).length; byId("watched-count").textContent = String(count); byId("notification-count").textContent = String(count); }
function saveWatchlist() {
  try { localStorage.setItem(WATCH_KEY, JSON.stringify(localWatchlist)); }
  catch (_) { byId("global-notice").textContent = "Browser storage is unavailable. Watchlist changes will not be retained. No source monitoring or alerts are active."; }
  updateWatchCounters(); renderWatchlist();
}
function toggleWatch(row) {
  if (!row || !["ceqa","permit"].includes(row.record_kind) || !row.record_id) return;
  const key = identity(row);
  if (localWatchlist[key]) delete localWatchlist[key];
  else localWatchlist[key] = {record_kind:row.record_kind,record_id:row.record_id,title:row.title || "Untitled source record",county:row.county || "County unrecorded"};
  saveWatchlist(); renderDossier(row);
}
function renderWatchlist(full = false) {
  const entries = Object.entries(localWatchlist);
  const markup = (full ? entries : entries.slice(0,4)).map(([key,entry],index) =>
    '<div class="watch-entry"><i class="dot unknown" aria-hidden="true"></i><span><b>' + escapeText(entry.title) +
    '</b><br><small>' + escapeText(entry.county) + ' · browser-local bookmark · unassessed</small></span>' +
    '<button type="button" data-open="' + index + '">Open record</button><button type="button" data-remove="' + index + '">Remove</button></div>'
  ).join("") || '<p class="empty" style="padding:12px">No watched source records in this browser.</p>';
  const target = full ? byId("feature-body") : byId("watchlist-summary");
  if (full) {
    target.innerHTML = '<section class="feature-card"><h2>Saved source-record bookmarks</h2><p>These bookmarks are stored only in this browser. They do not subscribe to permit changes, schedule reminders, perform source polling, or send notifications.</p><div id="full-watchlist">' + markup + '</div><a href="/workspace#records">Browse retained source records →</a></section>';
  } else target.innerHTML = markup;
  target.querySelectorAll("[data-open]").forEach(button => button.onclick = () => {
    const currentKey = (full ? entries : entries.slice(0,4))[Number(button.dataset.open)]?.[0];
    if (currentKey) openWatchBookmark(currentKey);
  });
  target.querySelectorAll("[data-remove]").forEach(button => button.onclick = () => {
    const currentKey = (full ? entries : entries.slice(0,4))[Number(button.dataset.remove)]?.[0];
    if (currentKey) { delete localWatchlist[currentKey]; saveWatchlist(); if (full) renderWatchlist(true); }
  });
}
async function openExactStoredRecord(entry,key,origin) {
  if (!entry || !["ceqa","permit"].includes(entry.record_kind) ||
      typeof entry.record_id !== "string" || !entry.record_id || entry.record_id.length > 255 ||
      identity(entry) !== key) return;
  // Re-resolve exact source identity against the current read-only database.
  // Never treat cached bookmark labels or a historical event as current source facts.
  showHome();
  const token = ++featureRequest;
  byId("global-notice").textContent = "Looking up selected exact source record in the current local database…";
  try {
    const params = new URLSearchParams({kind:entry.record_kind,record_id:entry.record_id});
    const result = await fetchJson("/api/candidate-preview?" + params);
    if (token !== featureRequest || byId("command-view").hidden) return;
    const row = result.source_record;
    if (!row || identity(row) !== key || result.read_only !== true)
      throw Error("Selected record identity or read-only state could not be verified.");
    selectRow(row);
    byId("global-notice").textContent = "Opened an exact "+origin+" source record from the current local database. " +
      "It may be outside the active search/filter or displayed page. " +
      (origin==="bookmark" ? "Bookmark is not monitoring or outreach approval." :
        "Historical source event is not proof of current site activity or commercial qualification.");
  } catch (error) {
    if (token === featureRequest && !byId("command-view").hidden)
      byId("global-notice").textContent = "Selected source record unavailable in this database: " +
        String(error.message || error) + ". No cached source facts were substituted.";
  }
}
async function openWatchBookmark(key) {
  const entry = localWatchlist[key];
  return openExactStoredRecord(entry,key,"bookmark");
}
function valueOrUnknown(value) { return value === null || value === undefined || value === "" ? "Not established" : String(value); }
function renderDossier(row) {
  const target = byId("command-dossier");
  if (!row) { target.innerHTML = '<p class="empty">Select a retained source record to inspect its recorded facts and evidence.</p>'; return; }
  const provenances = Array.isArray(row.provenance) ? row.provenance : [];
  const sources = provenances.slice(0,3).map(p => escapeText(p.source_name || "Unnamed source")).join("; ") || "No provenance recorded";
  const point = row.point ? "Source-claimed coordinates available" : valueOrUnknown(row.map_reason);
  const watch = Boolean(localWatchlist[identity(row)]);
  target.innerHTML = '<span class="badge">UNASSESSED SOURCE RECORD</span><h3>' + escapeText(row.title || "Untitled record") + '</h3>' +
    '<p>' + escapeText(valueOrUnknown(row.county)) + ' · ' + escapeText(row.record_kind.toUpperCase()) +
    ' · Not a verified active construction site</p><dl>' +
    '<dt>Source record</dt><dd>' + escapeText(row.source_record_number || row.record_id) + '</dd>' +
    '<dt>Source status</dt><dd>' + escapeText(valueOrUnknown(row.source_status)) + '</dd>' +
    '<dt>Address</dt><dd>' + escapeText(valueOrUnknown(row.address)) + '</dd>' +
    '<dt>Parcel / APN</dt><dd>' + escapeText(valueOrUnknown(row.apn)) + '</dd>' +
    '<dt>Location evidence</dt><dd>' + escapeText(point) + '</dd>' +
    '<dt>Named parties</dt><dd>' + escapeText(Array.isArray(row.entities) && row.entities.length ? row.entities.map(x => x.name + " (" + x.role + ")").join("; ") : "Not established") + '</dd>' +
    '<dt>Sources</dt><dd>' + sources + '</dd></dl>' +
    '<p>Readiness, verified decision-maker contact and present construction stage have not been evaluated. No outreach or bid authorization is implied.</p>' +
    '<div class="dossier-actions"><button type="button" class="action primary" id="watch-selected">' + (watch ? "★ Remove bookmark" : "☆ Watch source record") + '</button>' +
    '<button type="button" class="action" id="inspect-selected">Inspect evidence, parcels &amp; review gaps →</button>' +
    '<a class="action" href="/workspace#records">Open Project Intelligence →</a></div>';
  byId("watch-selected").onclick = () => toggleWatch(row);
  byId("inspect-selected").onclick = () => showSection("evidence");
}
function renderRecords() {
  const target = byId("command-records");
  const items = records();
  target.innerHTML = items.map((row,index) =>
    '<button class="record-row' + (selected === identity(row) ? ' selected' : '') +
    '" data-record="' + index + '" type="button"><i class="dot unknown" title="Unassessed" aria-label="Unassessed"></i><strong>' +
    escapeText(row.title || "Untitled record") + '</strong><small>' + escapeText(valueOrUnknown(row.county)) +
    '</small><small>' + escapeText(row.record_kind.toUpperCase()) + '</small></button>'
  ).join("") || '<p class="empty" style="padding:12px">No retained source records match the current query.</p>';
  target.querySelectorAll("[data-record]").forEach(el => el.onclick = () => selectRow(items[Number(el.dataset.record)]));
  byId("records-scope").textContent = page ? "Showing " + (page.total ? page.offset + 1 : 0) + "–" + (page.offset + page.returned) + " of " + page.total +
    " matching source records on this bounded page. Not deduplicated projects or qualified leads." : "Source records unavailable.";
  byId("previous-records").disabled = !page || page.offset === 0;
  byId("next-records").disabled = !page || !page.has_more;
}
function selectRow(row) {
  if (!row) return;
  selected = identity(row); selectedRecord = row; ++featureRequest; renderDossier(row); renderRecords();
  byId("command-dossier").closest(".dossier-panel").scrollIntoView({block:"nearest",behavior:"auto"});
}
function renderMap() {
  const svg = byId("command-map");
  const points = footprint && Array.isArray(footprint.points) ? footprint.points : [];
  const display = points.filter(p => p.point && Number.isFinite(p.point.latitude) && Number.isFinite(p.point.longitude));
  svg.setAttribute("viewBox","0 0 700 320");
  let content = "";
  for (let x=30;x<700;x+=55) content += '<line class="grid-line" x1="'+x+'" y1="0" x2="'+x+'" y2="320"/>';
  for (let y=25;y<320;y+=45) content += '<line class="grid-line" x1="0" y1="'+y+'" x2="700" y2="'+y+'"/>';
  if (display.length) {
    const xs=display.map(p=>p.point.longitude), ys=display.map(p=>p.point.latitude);
    const minX=Math.min(...xs), maxX=Math.max(...xs), minY=Math.min(...ys), maxY=Math.max(...ys);
    const dx=Math.max(maxX-minX,.025), dy=Math.max(maxY-minY,.025);
    content += display.map((p,i) => {
      const x=35+(p.point.longitude-minX)/dx*630, y=285-(p.point.latitude-minY)/dy*250;
      return '<circle class="location-pin" tabindex="0" role="button" data-point="'+i+'" cx="'+x+'" cy="'+y+'" r="6" aria-label="'+escapeText(p.title || "Source record")+'"><title>'+escapeText(p.title || "Source record")+' · unassessed source location</title></circle>';
    }).join("");
  }
  svg.innerHTML=content;
  svg.querySelectorAll("[data-point]").forEach(el=>{
    const choose=()=>{const p=display[Number(el.dataset.point)];const row=records().find(r=>identity(r)===identity(p));if(row)selectRow(row);
      else loadData(Math.floor(p.ordinal/50)*50,identity(p));};
    el.onclick=choose;el.onkeydown=e=>{if(e.key==="Enter"||e.key===" "){e.preventDefault();choose();}};
  });
  byId("map-message").hidden=display.length>0;
  if (!display.length) byId("map-message").textContent="No source-supported coordinates in the scanned records.";
  byId("map-scope").textContent = footprint ?
    display.length+" mapped source records in a bounded scan of "+footprint.records_scanned+" of "+footprint.matching_total+
    (footprint.truncated?" matching records (truncated).":" matching records.")+
    " Coordinate overview; no street basemap or verified jobsite footprints." :
    "Coordinate map not available. No live construction or street basemap.";
}
const sections = {
  entities:["Entity Network","Explore recorded names and their source-key relationships.","Entity neighborhood inspection is available for a selected source record in Project Intelligence. Exact stored-key co-occurrence is not proof of independently verified corporate identity.","/workspace#records","Inspect source relationships →"],
  evidence:["Evidence Chains","Inspect attributable claims, named parties, and historical source milestones.","Full provenance, source URLs, source-claimed locations, parcel candidate inspection and historical milestone views are available in Project Intelligence. Records do not establish current construction activity.","/workspace#records","Open evidence-backed records →"],
  outreach:["Outreach","Commercial messaging and contact management.","No message delivery or outreach preview is available in this read-only operator. Source claims and unassessed records are not approved contacts or actionable leads. Outbound messages require a separately authorized workflow.","/workspace#workflow","Inspect persisted lead workflows →"],
  bid:["Bid Studio","Security proposals and request-driven pricing.","Bid preparation and submission controls are not wired to this operator. A green outreach status alone would not authorize a bid; a documented customer request, scope and commercial approval are required.","/workspace#workflow","Inspect retained workflow records →"],
  royalty:["Royalty Ledger","Contract attribution, payments, and reconciliation.","No royalty transaction ledger or payment posting is exposed through this read-only operator. Existing result/share services must be connected and validated before balances or payment status can be shown.","/workspace#workflow","Inspect retained workflow records →"],
  sources:["Sources & Collection","Review available data and collection boundaries.","This application reads a selected local SQLite database only. Live collection is disabled; matching source-record counts do not establish coverage of all permitting jurisdictions.","/workspace#records","Review retained source records →"]
};

function safeSourceLink(raw) {
  try {
    const url = new URL(String(raw));
    return ["http:", "https:"].includes(url.protocol) ? '<a rel="noopener noreferrer" target="_blank" href="'+escapeText(url.href)+'">Open public source ↗</a>' : "";
  } catch (_) { return ""; }
}
function evidenceItem(provenance) {
  return '<div class="evidence-item"><strong>'+escapeText(provenance.source_name || "Unnamed source")+'</strong>'+
    '<p>'+escapeText(valueOrUnknown(provenance.evidence_text))+'</p>'+
    '<small>Captured: '+escapeText(valueOrUnknown(provenance.captured_at))+
    ' · Reference: '+escapeText(valueOrUnknown(provenance.raw_reference))+'</small> '+
    safeSourceLink(provenance.source_url)+'</div>';
}
function featureIntro(name, message) {
  byId("feature-heading").textContent=name;
  byId("feature-description").textContent=message;
}
async function showEvidence() {
  const token=++featureRequest, row=selectedRecord;
  featureIntro("Evidence Chains", "Retained exact-source evidence, historical claims and review gaps · read only");
  if(!row){
    byId("feature-body").innerHTML='<section class="feature-card"><h2>Select a source record</h2><p>Select a project in the Command Center or Site Map to inspect its evidence.</p><button type="button" class="action" id="return-records">Return to source records</button></section>';
    byId("return-records").onclick=showHome;
    return;
  }
  byId("feature-body").innerHTML='<section class="feature-card"><p role="status">Loading exact-source evidence…</p></section>';
  try {
    const params=new URLSearchParams({kind:row.record_kind,record_id:row.record_id});
    const [result, parcels]=await Promise.all([
      fetchJson("/api/candidate-preview?"+params),
      fetchJson("/api/parcel-candidates?"+params).catch(error=>({error:String(error.message || error)}))
    ]);
    if(token!==featureRequest || byId("feature-view").hidden)return;
    if(identity(result.source_record)!==identity(row) || JSON.stringify(result.source_record)!==JSON.stringify(row))
      throw Error("The retained source changed since selection. Refresh and inspect the new revision.");
    const provenance=Array.isArray(result.source_snapshot.provenance)?result.source_snapshot.provenance:[];
    const siteSources=Array.isArray(result.source_snapshot.site?.provenance)?result.source_snapshot.site.provenance:[];
    const milestones=Array.isArray(row.milestones)?row.milestones:[];
    const checks=Array.isArray(result.checks)?result.checks:[];
    const parcelCurrent=parcels.source_kind===row.record_kind && parcels.source_record_id===row.record_id &&
      parcels.source_apn===row.apn && parcels.source_county===row.county &&
      parcels.read_only===true && parcels.linked_site_verified===false;
    const parcelClaims=parcelCurrent && Array.isArray(parcels.matches)?parcels.matches:[];
    const parcelSection='<section class="feature-card"><h2>Retained parcel candidates</h2>'+
      (parcels.error?'<p role="alert">Parcel inspection unavailable: '+escapeText(parcels.error)+'</p>':
      !parcelCurrent?'<p role="alert">Parcel inspection returned an inconsistent source identity or authority state.</p>':
      '<p>Source APN: '+escapeText(valueOrUnknown(parcels.source_apn))+' · Normalized APN: '+
      escapeText(valueOrUnknown(parcels.normalized_apn))+' · '+parcels.matching_total+
      ' exact APN/county co-occurrences'+(parcels.truncated?' (result truncated)':'')+
      '. These are unverified source claims, not confirmed parcel/site links or surveyed boundaries.</p>'+
      (parcelClaims.map(item=>'<div class="evidence-item"><strong>'+escapeText(item.apn)+
        '</strong> · '+escapeText(item.county)+' · '+escapeText(item.source_key)+
        '<p>Address: '+escapeText(valueOrUnknown(item.address))+
        ' · Zoning: '+escapeText(valueOrUnknown(item.zoning))+
        ' · Land use: '+escapeText(valueOrUnknown(item.land_use))+'</p>'+
        '<small>Record: '+escapeText(item.parcel_record_id)+' · '+escapeText(item.map_reason)+'</small></div>').join("")||
        '<p>No retained parcel candidate matched the exact APN and county. This does not establish that no parcel exists.</p>'))+
      '</section>';
    byId("feature-body").innerHTML=
      '<section class="feature-card"><span class="badge">SOURCE RECORD · '+escapeText(result.state.toUpperCase())+'</span><h2>'+escapeText(row.title)+'</h2>'+
      '<p>'+escapeText(row.record_kind.toUpperCase())+' / '+escapeText(row.record_id)+
      ' · '+escapeText(valueOrUnknown(row.county))+' · Record digest: <code>'+escapeText(result.normalized_source_sha256)+'</code></p>'+
      '<p>Read-only preview. No commercial lead, outreach authorization, or bid authorization is created.</p></section>'+
      '<section class="feature-card"><h2>Source evidence ('+provenance.length+')</h2>'+
      (provenance.map(evidenceItem).join("") || '<p>No source provenance retained. Review is on hold.</p>')+'</section>'+
      '<section class="feature-card"><h2>Linked site evidence ('+siteSources.length+')</h2>'+
      (siteSources.map(evidenceItem).join("") || '<p>No linked site provenance retained.</p>')+'</section>'+
      '<section class="feature-card"><h2>Historical source milestones</h2>'+
      (milestones.map(m=>'<p>'+escapeText(m.recorded_date)+' · '+escapeText(m.event_kind.replaceAll("_"," "))+' (source claimed)</p>').join("") || '<p>No dated events retained.</p>')+'</section>'+
      parcelSection+
      '<section class="feature-card"><h2>Opportunity review gaps</h2>'+
      checks.map(c=>'<p><strong>'+escapeText(c.key.replaceAll("_"," "))+' · '+escapeText(c.state)+'</strong><br>'+escapeText(c.detail)+'</p>').join("")+
      '<p>Review status is not approval. Full normalized evidence remains in the read-only Project Intelligence view.</p></section>';
  } catch(error) {
    if(token===featureRequest && !byId("feature-view").hidden)
      byId("feature-body").innerHTML='<section class="feature-card"><h2>Evidence unavailable</h2><p role="alert">'+escapeText(error.message || error)+'</p><button type="button" class="action" id="return-records">Return to source records</button></section>';
    if(byId("return-records"))byId("return-records").onclick=showHome;
  }
}
function showEntities() {
  ++featureRequest;const row=selectedRecord;
  featureIntro("Entity Network", "Exact stored-entity-key co-occurrence across retained CEQA and permit records");
  if(!row){showEntityIndex();return;}
  const entities=Array.isArray(row.entities)?row.entities:[];
  byId("feature-body").innerHTML='<section class="feature-card"><span class="badge">SOURCE-CLAIMED PARTIES</span><h2>'+escapeText(row.title)+'</h2>'+
    '<p>Matching an exact stored entity key does not independently verify legal identity, ownership, or a real-world project relationship.</p>'+
    (entities.map((e,index)=>'<div class="evidence-item"><strong>'+escapeText(e.name)+'</strong> · '+escapeText(e.role)+
      '<br><small>Stored key: '+escapeText(e.entity_key)+'</small><br><button type="button" class="action" data-entity="'+index+'">Inspect matching records</button></div>').join("") ||
      '<p>No named entities retained on this source record.</p>')+
    '<button type="button" class="action" id="browse-entity-index">Browse all retained entity keys →</button></section><section class="feature-card" id="entity-results"><p>Select a named party to inspect exact-key source co-occurrences.</p></section>';
  byId("browse-entity-index").onclick=()=>showEntityIndex();
  byId("feature-body").querySelectorAll("[data-entity]").forEach(button=>button.onclick=async()=>{
    const key=entities[Number(button.dataset.entity)]?.entity_key, currentToken=++featureRequest;
    if(typeof key!=="string" || !key || key.length>255)return;
    byId("entity-results").innerHTML='<p role="status">Inspecting exact-key source co-occurrences…</p>';
    try {
      const neighborhood=await fetchJson("/api/entity-neighborhood?"+new URLSearchParams({kind:"all",entity_key:key}));
      if(currentToken!==featureRequest || byId("feature-view").hidden)return;
      if(neighborhood.entity_key!==key)throw Error("Entity identity changed while loading.");
      const matches=Array.isArray(neighborhood.records)?neighborhood.records:[];
      const target=byId("entity-results");
      target.innerHTML='<h2>Exact-key matches ('+neighborhood.matching_records_in_scan+')</h2>'+
        '<p>'+neighborhood.scanned_source_records+' of '+neighborhood.total_source_records+' source records scanned. '+
        (neighborhood.source_scan_truncated?"Source scan truncated. ":"")+
        (neighborhood.matching_records_truncated?"Result list truncated. ":"")+
        'Equal stored keys indicate co-occurrence only, not independently confirmed entity identity.</p>'+
        (matches.map((match,index)=>'<button type="button" class="related-record" data-related="'+index+'">'+escapeText(match.title)+
          ' · '+escapeText(match.record_kind)+' / '+escapeText(match.record_id)+'</button>').join("") ||
          '<p>No source records matched within the bounded scan.</p>');
      target.querySelectorAll("[data-related]").forEach(item=>item.onclick=()=>{
        const record=matches[Number(item.dataset.related)];
        if(record){showHome();selectRow(record);}
      });
    } catch(error) {
      if(currentToken===featureRequest && !byId("feature-view").hidden)
        byId("entity-results").innerHTML='<p role="alert">Entity inspection unavailable: '+escapeText(error.message || error)+'</p>';
    }
  });
}


async function showEntityIndex(role="") {
  const token=++featureRequest;
  featureIntro("Entity Network", "Exact stored entity keys across retained source records · read only");
  byId("feature-body").innerHTML='<section class="feature-card"><p role="status">Reading bounded source-claimed entity index…</p></section>';
  const kind=activeKind, county=activeCounty;
  try {
    const data=await fetchJson("/api/entity-index?"+new URLSearchParams({kind,county,role}));
    if(token!==featureRequest || byId("feature-view").hidden)return;
    if(data.read_only!==true || data.live_collection_enabled!==false ||
      data.selection!==kind || data.county_filter!==county || data.role_filter!==role ||
      !Array.isArray(data.entries) || !Number.isSafeInteger(data.matching_source_records) ||
      !Number.isSafeInteger(data.scanned_source_records) ||
      !Number.isSafeInteger(data.distinct_keys_in_scan) ||
      data.returned!==data.entries.length || data.returned>data.result_limit ||
      data.source_scan_truncated!==(data.matching_source_records>data.scanned_source_records) ||
      data.result_truncated!==(data.distinct_keys_in_scan>data.returned))
      throw Error("Retained entity index scope or bounds are inconsistent.");
    const keys=new Set();
    for(const entry of data.entries){
      if(!entry || typeof entry.entity_key!=="string" || !entry.entity_key || entry.entity_key.length>255 ||
        keys.has(entry.entity_key) || !Array.isArray(entry.source_claimed_names) ||
        !Array.isArray(entry.source_claimed_roles) || !Number.isSafeInteger(entry.matching_records_in_scan) ||
        entry.matching_records_in_scan<1 ||
        entry.san_bernardino_records+entry.riverside_records+entry.other_or_unknown_records!==entry.matching_records_in_scan ||
        entry.appears_in_both_target_counties!==Boolean(entry.san_bernardino_records&&entry.riverside_records))
        throw Error("Retained entity key or source counts are inconsistent.");
      keys.add(entry.entity_key);
    }
    const items=data.entries.map((entry,index)=>
      '<button type="button" class="lead-record" data-index-entity="'+index+'"><strong>'+
      escapeText(entry.source_claimed_names.join("; ") || "Unnamed stored entity key")+'</strong><small>'+
      escapeText(entry.source_claimed_roles.join("; ") || "Role not recorded")+
      ' · '+entry.matching_records_in_scan+' source records in scan'+
      (entry.appears_in_both_target_counties?' · source-claimed in BOTH counties':'')+
      ' · San Bernardino '+entry.san_bernardino_records+' / Riverside '+entry.riverside_records+
      ' / Other or unknown '+entry.other_or_unknown_records+
      '</small><small>Exact stored key: '+escapeText(entry.entity_key)+'</small></button>').join("")||
      '<p>No stored entity keys appear in this bounded retained source scan.</p>';
    const roleOptions=[["","All recorded roles"],["owner","Owner"],["developer","Developer"],
      ["general_contractor","General contractor"],["contractor","Contractor"],
      ["applicant","Applicant"],["agency","Agency"],["architect","Architect"],
      ["engineer","Engineer"],["civil_engineer","Civil engineer"],
      ["representative","Representative"],["unknown","Unknown role"]];
    byId("feature-body").innerHTML='<section class="feature-card"><span class="badge">UNVERIFIED SOURCE-CLAIMED ENTITY INDEX</span>'+
      '<p><label for="entity-index-role">Recorded party role</label> <select id="entity-index-role" aria-label="Filter entity index by stored party role">'+
      roleOptions.map(([value,label])=>'<option value="'+value+'"'+(role===value?' selected':'')+'>'+label+'</option>').join("")+
      '</select></p>'+
      '<h2>Recorded companies and parties</h2><p>Scanned '+data.scanned_source_records+' of '+
      data.matching_source_records+' source records; '+data.distinct_keys_in_scan+
      ' distinct stored keys in scan; '+data.returned+' displayed. '+
      (data.source_scan_truncated?'Source-record scan truncated. ':'')+
      (data.result_truncated?'Entity-key list truncated. ':'')+
      'Exact stored keys and two-county co-occurrence do not independently verify legal entity identity, project relationships, current operations or qualified security leads.</p>'+
      '<div class="lead-records">'+items+'</div></section>'+
      '<section class="feature-card" id="entity-results"><p>Select a stored key to inspect source-record co-occurrences.</p></section>';
    byId("entity-index-role").onchange=()=>showEntityIndex(byId("entity-index-role").value);
    byId("feature-body").querySelectorAll("[data-index-entity]").forEach(button=>button.onclick=()=>{
      const entry=data.entries[Number(button.dataset.indexEntity)];
      if(entry)showIndexedEntityMatches(entry.entity_key,kind,county,role);
    });
  }catch(error){
    if(token===featureRequest && !byId("feature-view").hidden)
      byId("feature-body").innerHTML='<section class="feature-card"><h2>Entity index unavailable</h2><p role="alert">'+
        escapeText(error.message||error)+'</p></section>';
  }
}
async function showIndexedEntityMatches(key,kind,county,role="") {
  if(typeof key!=="string" || !key || key.length>255)return;
  const token=++featureRequest, target=byId("entity-results");
  if(!target)return;
  target.innerHTML='<p role="status">Inspecting matching retained source records…</p>';
  try {
    const data=await fetchJson("/api/entity-neighborhood?"+new URLSearchParams({kind,county,entity_key:key}));
    if(token!==featureRequest || byId("feature-view").hidden || target!==byId("entity-results"))return;
    if(data.read_only!==true || data.entity_key!==key || data.selection!==kind ||
      data.county_filter!==county || !Array.isArray(data.records) ||
      data.returned!==data.records.length || !Number.isSafeInteger(data.matching_records_in_scan))
      throw Error("Exact entity neighborhood identity or bounds are inconsistent.");
    target.innerHTML='<h2>Exact-key source records ('+data.matching_records_in_scan+')</h2>'+
      '<p>Scanned '+data.scanned_source_records+' of '+data.total_source_records+' retained source records. '+
      (data.source_scan_truncated?'Source scan truncated. ':'')+
      (data.matching_records_truncated?'Matching-record list truncated. ':'')+
      (role?'The neighborhood includes all source-claimed roles for this exact key; the role filter only constrains the entity index. ':'')+
      'Stored key co-occurrence is not verified real-world identity, ownership or an active project.</p>'+
      (data.records.map((row,index)=>'<button type="button" class="related-record" data-index-record="'+index+'">'+
        escapeText(row.title)+' · '+escapeText(row.record_kind)+' / '+escapeText(row.record_id)+
        ' · '+escapeText(valueOrUnknown(row.county))+'</button>').join("")||
        '<p>No source records matched in the bounded scan.</p>');
    target.querySelectorAll("[data-index-record]").forEach(button=>button.onclick=()=>{
      const row=data.records[Number(button.dataset.indexRecord)];
      if(row)openExactStoredRecord(row,identity(row),"entity index");
    });
  }catch(error){
    if(token===featureRequest && !byId("feature-view").hidden && target===byId("entity-results"))
      target.innerHTML='<p role="alert">Exact-key record inspection unavailable: '+escapeText(error.message||error)+'</p>';
  }
}

async function showHistoricalPulse() {
  const token=++featureRequest;
  const target=byId("historical-pulse");
  if(!target || byId("feature-view").hidden)return;
  const kind=activeKind,county=activeCounty,query=activeQuery;
  target.innerHTML='<p role="status">Reading retained historical source milestones for the active filters…</p>';
  try {
    const data=await fetchJson("/api/timeline?"+new URLSearchParams({kind,county,q:query}));
    if(token!==featureRequest || byId("feature-view").hidden || target!==byId("historical-pulse"))return;
    if(data.read_only!==true || data.live_collection_enabled!==false ||
      data.selection!==kind || !Number.isSafeInteger(data.matching_total) ||
      !Number.isSafeInteger(data.records_scanned) || !Number.isSafeInteger(data.milestones_in_scan) ||
      !Array.isArray(data.events) || data.returned_events!==data.events.length ||
      data.source_scan_truncated!==(data.matching_total>data.records_scanned))
      throw Error("Historical source timeline returned inconsistent scope or bounds.");
    const history=data.events.map((event,index)=>
      '<div class="evidence-item"><strong>'+escapeText(valueOrUnknown(event.recorded_date))+
      ' · '+escapeText(valueOrUnknown(event.event_kind).replaceAll("_"," "))+'</strong>'+
      '<p>'+escapeText(valueOrUnknown(event.title))+' · '+escapeText(valueOrUnknown(event.county))+
      ' · '+escapeText(event.record_kind)+' / '+escapeText(event.record_id)+'</p>'+
      (event.source_date_order_conflict?'<small>Retained source date-order conflict; inspect underlying evidence.</small>':'')+
      '<button type="button" class="action" data-history="'+index+'">Open exact source record →</button>'+
      '</div>').join("") || '<p>No dated milestones appear within this bounded retained source scan.</p>';
    target.innerHTML='<h2>Historical source milestones</h2><p>'+data.records_scanned+
      ' of '+data.matching_total+' matching source records scanned; '+data.milestones_in_scan+
      ' dated source events in scan; '+data.returned_events+' shown. '+
      (data.source_scan_truncated?'Source scan truncated. ':'')+
      (data.event_result_truncated?'Event list truncated. ':'')+
      'Historical source-claimed dates are not evidence of current site activity, new live acquisition, or qualified security opportunities.</p>'+history;
    target.querySelectorAll("[data-history]").forEach(button=>button.onclick=()=>{
      const event=data.events[Number(button.dataset.history)];
      if(event)openExactStoredRecord(event,identity(event),"historical timeline");
    });
  }catch(error){
    if(token===featureRequest && !byId("feature-view").hidden && target===byId("historical-pulse"))
      target.innerHTML='<p role="alert">Historical source milestones unavailable: '+escapeText(error.message||error)+'</p>';
  }
}
function prepareCeqanetCapture() {
  const raw=byId("capture-sch-number").value.trim();
  const target=byId("capture-instructions");
  if(!/^[0-9]{10}$/.test(raw)){
    target.textContent="Enter an exact 10-digit SCH number from the official public source. No collection was attempted.";
    return;
  }
  // This is a command preview, not a network request or automatic approval.
  // The operator must verify public access, execute the command locally, then
  // independently inspect both exact digests before the separately governed apply.
  const stamp=new Date().toISOString().replace(/[-:]/g,"").replace(/\.\d{3}/,"");
  const base="evidence/manual/ceqanet-"+raw+"-"+stamp;
  const command="constructionsight-ceqanet-reviewed-import capture-preview"+
    " --sch-number "+raw+" --output "+base+".json"+
    " --plan-output "+base+"-reviewed-plan.json"+
    " --authorization-reason 'Operator-reviewed official public CEQAnet project CSV'"+
    " --execute-live";
  target.innerHTML='<p>Official CEQAnet project page: <a href="https://ceqanet.lci.ca.gov/'+raw+
    '" target="_blank" rel="noopener noreferrer">Inspect SCH '+raw+' ↗</a></p>'+
    '<p>After checking applicable source-access restrictions, run this command locally. It performs one separately authorized public GET and produces retained evidence plus a proposed, unapplied write plan:</p>'+
    '<pre class="capture-command" id="capture-command"></pre>'+
    '<p>Review the retained source rows, county scope and the source/plan SHA-256 digests printed by that command. To import, independently approve both exact digests using the separate <code>constructionsight-ceqanet-reviewed-import apply --help</code> workflow and its explicit write authorization. Once applied to this operator database, the Command Center refreshes on the next local revision check. No collection, import, lead qualification, outreach or bids have been initiated by this preview.</p>';
  byId("capture-command").textContent=command;
}
function renderSourceRegistry(registry) {
  if(!registry || registry.read_only!==true || registry.network_collection_enabled!==false ||
    registry.verification_metadata_is_authority!==false || !Number.isSafeInteger(registry.total) ||
    registry.total<0 || !Number.isSafeInteger(registry.returned) || registry.returned<0 ||
    !Number.isSafeInteger(registry.result_limit) || registry.result_limit<1 ||
    !Array.isArray(registry.entries) || registry.returned!==registry.entries.length ||
    registry.returned>registry.result_limit || registry.truncated!==(registry.total>registry.returned))
    throw Error("Persisted source registry returned inconsistent bounds or authority state.");
  const statuses=new Set(["unverified","verified","partial","failed","blocked"]);
  const rows=registry.entries.map(entry=>{
    if(!entry || typeof entry.source_name!=="string" || !entry.source_name ||
      typeof entry.jurisdiction_name!=="string" || !entry.jurisdiction_name ||
      typeof entry.county!=="string" || !entry.county ||
      typeof entry.platform_family!=="string" || !entry.platform_family ||
      !Array.isArray(entry.record_categories) || !statuses.has(entry.verification_status) ||
      typeof entry.adapter_status!=="string" || !entry.adapter_status ||
      typeof entry.adapter_live!=="boolean" ||
      typeof entry.latest_verification_present!=="boolean")
      throw Error("Persisted source registry entry is inconsistent.");
    const latest=entry.latest_verification_present;
    if(latest && (
      typeof entry.latest_verification_checked_at!=="string" ||
      !entry.latest_verification_checked_at ||
      typeof entry.latest_verification_url_reachable!=="boolean" ||
      typeof entry.latest_detected_platform_family!=="string" ||
      !entry.latest_detected_platform_family ||
      !Number.isSafeInteger(entry.latest_verification_confidence_score) ||
      entry.latest_verification_confidence_score<0 ||
      entry.latest_verification_confidence_score>100 ||
      typeof entry.verification_metadata_consistent!=="boolean" ||
      ![null,true,false].includes(entry.latest_public_search_available) ||
      ![null,true,false].includes(entry.latest_login_required) ||
      ![null,"string"].includes(
        entry.latest_verification_notes===null ? null : typeof entry.latest_verification_notes
      )
    )) throw Error("Latest retained source verification is inconsistent.");
    if(!latest && (
      entry.latest_verification_checked_at!==null ||
      entry.latest_verification_url_reachable!==null ||
      entry.latest_detected_platform_family!==null ||
      entry.latest_public_search_available!==null ||
      entry.latest_login_required!==null ||
      entry.latest_verification_confidence_score!==null ||
      entry.latest_verification_notes!==null ||
      entry.verification_metadata_consistent!==null
    )) throw Error("Absent source verification carries unexpected retained claims.");
    const latestDetail=latest ?
      '<small class="'+(entry.verification_metadata_consistent?'source-verification-ok':'source-verification-warning')+
      '">latest retained check: '+(entry.latest_verification_url_reachable?'reachable':'not reachable')+
      ' · '+escapeText(entry.latest_verification_checked_at)+
      ' · detected '+escapeText(entry.latest_detected_platform_family)+
      ' · confidence '+entry.latest_verification_confidence_score+'/100'+
      (entry.verification_metadata_consistent?' · registry metadata agrees':
        ' · registry metadata DIFFERS; inspect retained verification history')+'</small>' :
      '<small>no linked retained verification observation</small>';
    return '<tr><th scope="row">'+escapeText(entry.source_name)+
      '<small>'+escapeText(entry.jurisdiction_name)+' · '+escapeText(entry.county)+'</small></th>'+
      '<td>'+escapeText(entry.platform_family)+'<small>adapter '+escapeText(entry.adapter_status)+
      (entry.adapter_live?' · live-capable software':' · not live-capable')+'</small></td>'+
      '<td>'+escapeText(entry.verification_status)+'<small>stored confidence '+
      escapeText(entry.confidence_score)+'/100 · checked '+
      escapeText(valueOrUnknown(entry.last_checked_date))+'</small>'+latestDetail+'</td>'+
      '<td>'+escapeText(entry.record_categories.join(", ") || "No categories")+
      '<small>'+escapeText(valueOrUnknown(entry.update_frequency))+'</small></td>'+
      '<td>'+safeSourceLink(entry.public_url)+'</td></tr>';
  }).join("") || '<tr><td colspan="5">No public-source registry rows are retained in this database.</td></tr>';
  return '<section class="feature-card"><span class="badge">PERSISTED SOURCE REGISTRY · READ ONLY</span>'+
    '<h2>Configured public sources ('+registry.returned+(registry.truncated?' of '+registry.total:'')+')</h2>'+
    '<p>Verification state, confidence, update cadence and adapter maturity are retained metadata. The newest linked verification observation is shown separately when available, including any disagreement with the registry row. Historical checks do not prove current reachability, complete jurisdiction coverage, or authority for recurring collection.</p>'+
    '<div class="source-inventory-scroll"><table class="source-inventory source-registry-table"><thead>'+
    '<tr><th>Source</th><th>Platform / adapter</th><th>Registry verification</th>'+
    '<th>Declared records / cadence</th><th>Official source</th></tr></thead><tbody>'+
    rows+'</tbody></table></div>'+
    (registry.truncated?'<p>Registry display is truncated at '+registry.result_limit+' rows.</p>':'')+
    '</section>';
}

function renderCaptureQueue(queue) {
  if(!queue || queue.schema_version!=="constructionsight.operator_capture_queue.v1" ||
    queue.read_only!==true || queue.network_executed!==false ||
    queue.persistence_mutated!==false || queue.commercial_leads_created!==false ||
    !Number.isSafeInteger(queue.candidate_count) || queue.candidate_count<0 ||
    !Array.isArray(queue.candidates) || queue.candidate_count!==queue.candidates.length)
    throw Error("Retained exact-SCH review queue returned an inconsistent authority state.");
  if(!queue.configured){
    if(queue.candidate_count!==0)
      throw Error("Unconfigured review queue reported retained candidates.");
    return '<section class="feature-card"><h2>Exact-SCH review queue</h2>'+
      '<p>No retained review queue is configured for this operator session. To display one, restart the local '+
      'operator with <code>--capture-queue &lt;review-queue.json&gt;</code>. This does not enable remote collection.</p></section>';
  }
  const seen=new Set();
  for(const item of queue.candidates){
    if(!item || typeof item.sch_number!=="string" || !/^[0-9]{10}$/.test(item.sch_number) ||
      seen.has(item.sch_number) || !["San Bernardino","Riverside"].includes(item.source_claimed_county) ||
      typeof item.source_claimed_title!=="string" || !item.source_claimed_title ||
      item.candidate_only!==true || item.review_state!=="unverified_source_claim" ||
      item.network_executed_for_candidate!==false || item.persistence_mutated!==false)
      throw Error("Retained exact-SCH review queue candidate is inconsistent.");
    seen.add(item.sch_number);
  }
  const rows=queue.candidates.map((item,index)=>
    '<div class="capture-queue-entry"><div><strong>'+escapeText(item.source_claimed_title)+
    '</strong><small>SCH '+escapeText(item.sch_number)+' · '+escapeText(item.source_claimed_county)+
    ' · observed '+item.source_observation_count+' time(s) in retained listing evidence'+
    (item.title_requires_detail_enrichment?' · title/detail enrichment still required':'')+
    '</small></div><div class="capture-queue-actions">'+safeSourceLink(item.official_detail_url)+
    '<button type="button" class="action" data-capture-queue="'+index+'">Prepare reviewed capture →</button></div></div>'
  ).join("") || '<p>No target-county exact-SCH candidates were retained in this reviewed listing queue.</p>';
  return '<section class="feature-card"><span class="badge">RETAINED REVIEW QUEUE · CANDIDATES ONLY</span>'+
    '<h2>Exact-SCH review queue ('+queue.candidate_count+')</h2>'+
    '<p>Derived from '+queue.listing_pages_reviewed+' retained listing page(s) and '+
    queue.listing_records_parsed+' parsed source observations. Listing artifact SHA-256: <code>'+
    escapeText(queue.listing_artifact_sha256)+'</code>. Candidates are source claims, not verified active '+
    'construction sites. Selecting one only prepares the existing local one-request capture instructions.</p>'+
    '<div class="capture-queue">'+rows+'</div></section>';
}
function bindCaptureQueue(queue) {
  if(!queue || !queue.configured)return;
  byId("feature-body").querySelectorAll("[data-capture-queue]").forEach(button=>button.onclick=()=>{
    const item=queue.candidates[Number(button.dataset.captureQueue)];
    if(!item || !/^[0-9]{10}$/.test(item.sch_number))return;
    byId("capture-sch-number").value=item.sch_number;
    prepareCeqanetCapture();
    byId("capture-source-form").scrollIntoView({block:"nearest",behavior:"auto"});
  });
}

async function showSources() {
  const token=++featureRequest;
  featureIntro("Sources & Collection", "Actual retained CEQA and permit counts from the selected local database");
  byId("feature-body").innerHTML='<section class="feature-card"><p role="status">Reading stored source-family and county counts…</p></section>';
  const families=["ceqa","permit"], counties=["","San Bernardino","Riverside"];
  try {
    const queries=families.flatMap(kind=>counties.map(county=>({kind,county})));
    const [data,captureQueue,sourceRegistry]=await Promise.all([
      Promise.all(queries.map(async item=>
        fetchJson("/api/snapshot?"+new URLSearchParams({
          kind:item.kind,county:item.county,limit:"1",offset:"0"
        }))
      )),
      fetchJson("/api/capture-queue"),
      fetchJson("/api/source-registry")
    ]);
    if(token!==featureRequest || byId("feature-view").hidden)return;
    if(data.some((result,index)=>result.selection!==queries[index].kind || !Number.isSafeInteger(result.total) || result.total<0))
      throw Error("Stored source scope changed or could not be verified.");
    const rows=families.map((kind,index)=>{
      const [all,sanBernardino,riverside]=data.slice(index*3,index*3+3).map(result=>result.total);
      if(sanBernardino+riverside>all)throw Error("Source counts disagree across county filters.");
      const countButton=(count,county)=>'<button type="button" class="source-count" data-source-kind="'+kind+'" data-source-county="'+county+'" aria-label="Show '+kind+' source records'+(county?' in '+county+' County':' across retained counties')+'">'+count+'</button>';
      return '<tr><th scope="row">'+escapeText(kind.toUpperCase())+'</th><td>'+countButton(all,'')+'</td><td>'+countButton(sanBernardino,'San Bernardino')+'</td><td>'+countButton(riverside,'Riverside')+'</td><td>'+(all-sanBernardino-riverside)+'</td></tr>';
    }).join("");
    byId("feature-body").innerHTML='<section class="feature-card"><span class="badge">RETAINED SQLITE RECORDS · READ ONLY</span><h2>Source inventory</h2>'+
      '<p>Counts are source records, not deduplicated projects, live construction sites, or approved commercial leads. Other/unknown includes records with missing or out-of-scope county claims.</p>'+
      '<div class="source-inventory-scroll"><table class="source-inventory"><thead><tr><th>Source family</th><th>All counties</th><th>San Bernardino</th><th>Riverside</th><th>Other / unknown</th></tr></thead><tbody>'+rows+'</tbody></table></div></section>'+
      renderSourceRegistry(sourceRegistry)+
      '<section class="feature-card"><h2>Collection status</h2><p>This local operator does not run live source acquisition, subscription monitoring, scheduled updates or remote data import. Import and retained-source validation remain separate governed workflows.</p>'+
      '<a href="/workspace#records">Inspect stored source evidence →</a></section>'+
      renderCaptureQueue(captureQueue)+
      '<section class="feature-card"><h2>Review a newly available CEQAnet project</h2><p>Prepare a single-project, manually authorized capture using the existing offline-review and SQLite import services. This read-only dashboard cannot issue remote requests or authorize imports.</p>'+
      '<form id="capture-source-form"><label for="capture-sch-number">Official 10-digit SCH number</label> <input id="capture-sch-number" type="text" inputmode="numeric" maxlength="10" pattern="[0-9]{10}" placeholder="0000000000" required> <button type="submit" class="action">Prepare local capture instructions</button></form>'+
      '<div id="capture-instructions" aria-live="polite"><p>No collection has been attempted. Verify the public source and its access conditions before executing any command.</p></div></section>'+
      '<section class="feature-card"><h2>Historical source activity</h2><p>Inspect dated historical observations for the current search, source-family and county filters. This is not real-time site monitoring.</p>'+
      '<button type="button" class="action" id="show-historical-pulse">Load retained timeline →</button><div id="historical-pulse"></div></section>';
    byId("capture-source-form").onsubmit=event=>{event.preventDefault();prepareCeqanetCapture();};
    bindCaptureQueue(captureQueue);
    byId("show-historical-pulse").onclick=showHistoricalPulse;
    byId("feature-body").querySelectorAll("[data-source-kind]").forEach(button=>button.onclick=()=>{
      const kind=button.dataset.sourceKind, county=button.dataset.sourceCounty;
      if(["ceqa","permit"].includes(kind) && ["","San Bernardino","Riverside"].includes(county))
        applySourceFilter(kind,county);
    });
  } catch(error) {
    if(token===featureRequest && !byId("feature-view").hidden)
      byId("feature-body").innerHTML='<section class="feature-card"><h2>Source inventory unavailable</h2><p role="alert">'+escapeText(error.message || error)+'</p></section>';
  }
}

function workflowDetails(row) {
  const notes=(items,label)=>'<section class="lead-details-group"><h3>'+label+'</h3>'+
    (Array.isArray(items)&&items.length?items.map(item=>'<p>'+escapeText(item)+'</p>').join(""):'<p>None retained.</p>')+'</section>';
  const history=Array.isArray(row.events)?row.events:[];
  return '<section class="feature-card"><span class="badge">PERSISTED WORKFLOW · '+escapeText(valueOrUnknown(row.status).toUpperCase())+'</span>'+
    '<h2>'+escapeText(valueOrUnknown(row.summary||row.base_candidate_id))+'</h2>'+
    '<p>A stored workflow status or lead score does not independently verify the source record, permit activity, approved contact, or authority to perform outreach or submit a bid.</p>'+
    '<dl class="lead-detail-grid">'+
    '<dt>Workflow ID</dt><dd>'+escapeText(row.workflow_id)+'</dd>'+
    '<dt>Exact review package</dt><dd>'+escapeText(valueOrUnknown(row.package_id))+'</dd>'+
    '<dt>Candidate ID</dt><dd>'+escapeText(valueOrUnknown(row.base_candidate_id))+'</dd>'+
    '<dt>Recorded status</dt><dd>'+escapeText(valueOrUnknown(row.status))+'</dd>'+
    '<dt>Stored lead score</dt><dd>'+escapeText(valueOrUnknown(row.lead_score))+'</dd>'+
    '<dt>Last recorded update</dt><dd>'+escapeText(valueOrUnknown(row.updated_at))+'</dd></dl>'+
    notes(row.evidence_notes,"Exact review package evidence notes")+
    notes(row.notes,"Workflow notes")+notes(row.limitations,"Retained limitations")+
    '<section class="lead-details-group"><h3>Recorded workflow events</h3>'+
    (history.length?history.map(event=>'<p>'+escapeText(valueOrUnknown(event.created_at))+' · '+escapeText(valueOrUnknown(event.current_status))+
      ' · '+escapeText(valueOrUnknown(event.reason))+'</p>').join(""):'<p>No historical events retained.</p>')+'</section>'+
    '<a href="/workspace#workflow">Open full read-only workflow workspace →</a></section>';
}
async function showLeads(offset=0) {
  const token=++featureRequest;
  featureIntro("Lead Console", "Persisted, exact-package reviewed workflows · local read-only inspection");
  byId("feature-body").innerHTML='<section class="feature-card"><p role="status">Loading persisted workflows…</p></section>';
  try {
    const data=await fetchJson("/api/workflows?"+new URLSearchParams({limit:"25",offset:String(offset)}));
    if(token!==featureRequest || byId("feature-view").hidden)return;
    if(data.read_only!==true || !Number.isSafeInteger(data.total) || data.total<0 ||
      data.offset!==offset || data.limit!==25 || !Array.isArray(data.leads) ||
      data.returned!==data.leads.length || data.returned>25 ||
      data.has_more!==(offset+data.returned<data.total))throw Error("Stored workflow page is inconsistent.");
    const ids=new Set();
    for(const row of data.leads){
      if(typeof row.workflow_id!=="string" || !row.workflow_id || ids.has(row.workflow_id) ||
        typeof row.package_id!=="string" || !row.package_id ||
        typeof row.base_candidate_id!=="string" || !row.base_candidate_id ||
        !Array.isArray(row.limitations))throw Error("Stored workflow identity or evidence is inconsistent.");
      ids.add(row.workflow_id);
    }
    const markup=data.leads.map((row,index)=>'<button class="lead-record" type="button" data-lead="'+index+
      '"><span class="badge">'+escapeText(valueOrUnknown(row.status))+'</span><strong>'+
      escapeText(valueOrUnknown(row.summary||row.base_candidate_id))+'</strong><small>'+
      escapeText(row.workflow_id)+' · exact package '+escapeText(row.package_id)+'</small></button>').join("")||
      '<p>No retained lead workflows. Unassessed source records are not automatically commercial leads.</p>';
    byId("feature-body").innerHTML='<section class="feature-card"><h2>Persisted lead workflows</h2><p>Showing '+
      (data.total?offset+1:0)+'–'+(offset+data.returned)+' of '+data.total+
      ' workflow rows. These are not distinct verified construction projects or automatically approved contacts.</p>'+
      '<div class="lead-records">'+markup+'</div><div class="record-pager">'+
      '<button type="button" id="leads-prev" '+(offset===0?'disabled':'')+'>← Previous</button>'+
      '<button type="button" id="leads-next" '+(!data.has_more?'disabled':'')+'>Next →</button></div></section>'+
      '<div id="lead-detail"><section class="feature-card"><p>Select a retained workflow to inspect its exact review package and recorded history.</p></section></div>';
    byId("leads-prev").onclick=()=>{if(offset>0)showLeads(Math.max(0,offset-25));};
    byId("leads-next").onclick=()=>{if(data.has_more)showLeads(offset+25);};
    byId("feature-body").querySelectorAll("[data-lead]").forEach(button=>button.onclick=()=>{
      if(token!==featureRequest)return;
      const row=data.leads[Number(button.dataset.lead)];
      if(row)byId("lead-detail").innerHTML=workflowDetails(row);
    });
  }catch(error){
    if(token===featureRequest && !byId("feature-view").hidden)
      byId("feature-body").innerHTML='<section class="feature-card"><h2>Workflows unavailable</h2><p role="alert">'+
      escapeText(error.message||error)+
      '</p><p>No synthetic lead records were substituted.</p><a href="/workspace#workflow">Open full workflow inspector →</a></section>';
  }
}

function renderResultHistory(entry) {
  const current=entry.current, share=current.share;
  const amount=value=>value===null || value===undefined ? "Not recorded" : escapeText(String(value));
  return '<section class="feature-card"><span class="badge">RETAINED RESULT · REVISION '+escapeText(current.revision)+'</span>'+
    '<h2>'+escapeText(entry.workflow_id)+'</h2><p>Latest retained outcome: '+escapeText(current.status)+
    ' · exact review package '+escapeText(entry.package_id)+'</p>'+
    '<p>Recorded gross value: '+amount(current.gross_value)+
    ' · Share state: '+escapeText(current.share_status)+'</p>'+
    (share?'<p>Stored share rate: '+amount(share.share_rate)+
      ' · Calculated share value: '+amount(share.share_value)+
      ' (stored numerical amounts; currency, entitlement, payment and ownership not verified).</p>':
      '<p>No calculated share attached to the current result revision.</p>')+
    '<p>No royalty entitlement, payment, outstanding balance or disbursement is verified by these records.</p>'+
    '<h3>Immutable result revisions ('+entry.revision_count+')</h3>'+
    entry.history.map(row=>'<div class="evidence-item"><strong>Revision '+escapeText(row.revision)+
      ' · '+escapeText(row.status)+'</strong><p>Ledger key: '+escapeText(row.ledger_id)+
      ' · Date: '+escapeText(valueOrUnknown(row.decided_date))+'</p>'+
      '<p>Prior revision: '+escapeText(valueOrUnknown(row.supersedes_ledger_id))+
      ' · Correction: '+escapeText(valueOrUnknown(row.correction_reason))+'</p>'+
      (Array.isArray(row.reasons)?row.reasons.map(reason=>'<p>'+escapeText(reason)+'</p>').join(""):"")+
      (Array.isArray(row.limitations)?row.limitations.map(note=>'<p>'+escapeText(note)+'</p>').join(""):"")+
      '</div>').join("")+'</section>';
}
async function showRoyaltyLedger(offset=0) {
  const token=++featureRequest;
  featureIntro("Royalty Ledger", "Stored outcome and share calculations · no royalty entitlement or payment verification");
  byId("feature-body").innerHTML='<section class="feature-card"><p role="status">Reading validated result histories…</p></section>';
  try {
    const data=await fetchJson("/api/results?"+new URLSearchParams({limit:"25",offset:String(offset)}));
    if(token!==featureRequest || byId("feature-view").hidden)return;
    if(data.read_only!==true || data.payment_status_verified!==false ||
      data.royalty_entitlement_verified!==false || !Number.isSafeInteger(data.total) ||
      data.total<0 || data.offset!==offset || data.limit!==25 ||
      !Array.isArray(data.results) || data.returned!==data.results.length ||
      data.returned>25 || data.has_more!==(offset+data.returned<data.total))
      throw Error("Stored results page or its authority state is inconsistent.");
    const ids=new Set();
    for(const entry of data.results){
      if(!entry || typeof entry.workflow_id!=="string" || !entry.workflow_id ||
        ids.has(entry.workflow_id) || !entry.current ||
        entry.current.workflow_id!==entry.workflow_id ||
        entry.current.package_id!==entry.package_id ||
        !Array.isArray(entry.history) || !Number.isSafeInteger(entry.revision_count) ||
        entry.revision_count!==entry.history.length || entry.revision_count===0 ||
        entry.history[entry.history.length-1].ledger_id!==entry.current.ledger_id)
        throw Error("Stored result revision identity is inconsistent.");
      ids.add(entry.workflow_id);
    }
    const markup=data.results.map((entry,index)=>'<button type="button" class="lead-record" data-result="'+index+
      '"><span class="badge">'+escapeText(entry.current.status)+'</span><strong>'+escapeText(entry.workflow_id)+
      '</strong><small>Latest result revision '+escapeText(entry.current.revision)+
      ' · share state '+escapeText(entry.current.share_status)+'</small></button>').join("")||
      '<p>No retained result revisions exist in this database. No payout or royalty balance is inferred.</p>';
    byId("feature-body").innerHTML='<section class="feature-card"><h2>Persisted outcomes and calculated shares</h2>'+
      '<p>Showing '+(data.total?offset+1:0)+'–'+(offset+data.returned)+' of '+data.total+
      ' workflows with retained outcome histories. A calculated result share is not proof of a royalty agreement, '+
      'entitlement, receipt, currency, or payment status. Previous corrected revisions must not be summed.</p>'+
      '<div class="lead-records">'+markup+'</div><div class="record-pager">'+
      '<button type="button" id="results-prev" '+(offset===0?'disabled':'')+'>← Previous</button>'+
      '<button type="button" id="results-next" '+(!data.has_more?'disabled':'')+'>Next →</button></div></section>'+
      '<div id="result-detail"><section class="feature-card"><p>Select a retained result to inspect its validated revision history.</p></section></div>';
    byId("results-prev").onclick=()=>{if(offset>0)showRoyaltyLedger(Math.max(0,offset-25));};
    byId("results-next").onclick=()=>{if(data.has_more)showRoyaltyLedger(offset+25);};
    byId("feature-body").querySelectorAll("[data-result]").forEach(button=>button.onclick=()=>{
      if(token!==featureRequest)return;
      const row=data.results[Number(button.dataset.result)];
      if(row)byId("result-detail").innerHTML=renderResultHistory(row);
    });
  }catch(error){
    if(token===featureRequest && !byId("feature-view").hidden)
      byId("feature-body").innerHTML='<section class="feature-card"><h2>Result ledger unavailable</h2>'+
        '<p role="alert">'+escapeText(error.message||error)+'</p>'+
        '<p>No payout, balance, or synthetic result was substituted.</p></section>';
  }
}

function showAiCenter() {
  featureIntro("AI Center", "Optional research assistance and ambient intelligence · not connected");
  byId("feature-body").innerHTML =
    '<section class="feature-card ai-status-card"><span class="badge">AI OFF · NO MODEL CONNECTED</span>'+
    '<h2>ConstructionSight AI Center</h2>'+
    '<p>The application continues to acquire, retain, search, inspect and display source records independently of AI. '+
    'This development interface does not invoke a model, perform background inference, or send source records to an AI provider.</p>'+
    '<p>Provider: not configured · Remote data transmission: disabled · Background analysis: inactive</p></section>'+
    '<section class="feature-card"><h2>AI Research Assistant · planned</h2>'+
    '<p>Optional, operator-initiated analysis of already retained and permitted evidence: cited dossier explanations, '+
    'research questions, competing source claims and proposed entity matches. Proposed findings require source links and '+
    'separate review; they never become authoritative source facts automatically.</p>'+
    '<a href="/workspace#records">Inspect existing evidence without AI →</a></section>'+
    '<section class="feature-card"><h2>Ambient Intelligence · planned</h2>'+
    '<p>Optional background analysis of authorized record-change events, with bounded queues, cancellation, '+
    'deduplicated analysis, separate findings storage and explicit provenance. It will not block core workflows '+
    'or independently authorize outreach, bids, payments or changes to source records.</p>'+
    '<p>Current status: inactive. No monitoring, alerts or AI suggestions are running.</p></section>'+
    '<section class="feature-card"><h2>Model and privacy controls · planned</h2>'+
    '<p>A future provider connection will require explicit activation and clear disclosure before any remote data '+
    'transmission. Local and remote models will use a replaceable adapter; timeouts or provider failures must not '+
    'interrupt the normal ConstructionSight workflow.</p>'+
    '<p>There is no live model selector or enable switch yet. The AI Center is reserved for this optional feature.</p></section>';
}

function showSection(name) {
  ++featureRequest;
  byId("command-view").hidden=true;byId("feature-view").hidden=false;
  if(name==="entities"){document.querySelectorAll("[data-section]").forEach(n=>{n.classList.toggle("current",n.dataset.section===name);n.setAttribute("aria-pressed",String(n.dataset.section===name));});document.querySelector('a[href="/"]').classList.remove("current");showEntities();return;}
  if(name==="evidence"){document.querySelectorAll("[data-section]").forEach(n=>{n.classList.toggle("current",n.dataset.section===name);n.setAttribute("aria-pressed",String(n.dataset.section===name));});document.querySelector('a[href="/"]').classList.remove("current");showEvidence();return;}
  if(name==="sources"){document.querySelectorAll("[data-section]").forEach(n=>{n.classList.toggle("current",n.dataset.section===name);n.setAttribute("aria-pressed",String(n.dataset.section===name));});document.querySelector('a[href="/"]').classList.remove("current");showSources();return;}
  if(name==="ai"){document.querySelectorAll("[data-section]").forEach(n=>{n.classList.toggle("current",n.dataset.section===name);n.setAttribute("aria-pressed",String(n.dataset.section===name));});document.querySelector('a[href="/"]').classList.remove("current");showAiCenter();return;}
  if(name==="leads"){document.querySelectorAll("[data-section]").forEach(n=>{n.classList.toggle("current",n.dataset.section===name);n.setAttribute("aria-pressed",String(n.dataset.section===name));});document.querySelector('a[href="/"]').classList.remove("current");showLeads();return;}
  if(name==="royalty"){document.querySelectorAll("[data-section]").forEach(n=>{n.classList.toggle("current",n.dataset.section===name);n.setAttribute("aria-pressed",String(n.dataset.section===name));});document.querySelector('a[href="/"]').classList.remove("current");showRoyaltyLedger();return;}
  document.querySelectorAll("[data-section]").forEach(n=>{n.classList.toggle("current",n.dataset.section===name);n.setAttribute("aria-pressed",String(n.dataset.section===name));});
  document.querySelector('a[href="/"]').classList.remove("current");
  if(name==="watchlist"){
    byId("feature-heading").textContent="Watchlist";byId("feature-description").textContent="Browser-local source bookmarks · monitoring and reminders not yet connected";
    renderWatchlist(true);return;
  }
  const [title,subtitle,warning,link,label]=sections[name]||sections.sources;
  byId("feature-heading").textContent=title;byId("feature-description").textContent=subtitle;
  byId("feature-body").innerHTML='<section class="feature-card"><span class="badge">FUNCTIONALITY STATUS · PARTIAL / NOT CONNECTED</span><h2>'+escapeText(title)+'</h2><p>'+escapeText(warning)+'</p><a href="'+link+'">'+escapeText(label)+'</a></section>'+
    (name==="sources" ? '<section class="feature-card"><h2>Current local source scope</h2><p id="source-scope-detail">'+escapeText(page ? page.total+" matching retained records in the selected database.": "Reading local source record status…")+'</p></section>' : "");
}
function showHome(){++featureRequest;byId("command-view").hidden=false;byId("feature-view").hidden=true;document.querySelectorAll("[data-section]").forEach(n=>{n.classList.remove("current");n.setAttribute("aria-pressed","false");});document.querySelector('a[href="/"]').classList.add("current");}
async function fetchJson(url){
  const response=await fetch(url,{cache:"no-store"});
  const data=await response.json();
  if(!response.ok) throw Error(data.error || "Local data unavailable.");
  return data;
}
async function loadData(offset=pageOffset, focusIdentity=null){
  const token=++pageRequest;++featureRequest;
  byId("global-notice").textContent="Loading retained local records. Readiness, outreach, bidding, and live watchlist monitoring are not enabled.";
  const filter=new URLSearchParams({kind:activeKind,county:activeCounty,limit:"50",offset:String(offset),q:activeQuery});
  const geo=new URLSearchParams({kind:activeKind,county:activeCounty,q:activeQuery});
  try{
    const [newPage,newFootprint,newWorkflow,health,workflowStatus,sourceState]=await Promise.all([
      fetchJson("/api/snapshot?"+filter),fetchJson("/api/footprint?"+geo),
      fetchJson("/api/workflows?limit=50&offset=0"),fetchJson("/api/health"),
      fetchJson("/api/workflow-summary").catch(error=>({error:String(error.message || error)})),
      fetchJson("/api/source-revision").catch(()=>null)
    ]);
    if(token!==pageRequest)return;
    if(newPage.selection!==activeKind || newFootprint.selection!==activeKind ||
      newPage.total!==newFootprint.matching_total)throw Error("Source-list and geographic scope disagree. Refresh the database view.");
    page=newPage;footprint=newFootprint;workflows=newWorkflow;pageOffset=offset;
    if(sourceState && sourceState.read_only===true && sourceState.live_collection_enabled===false &&
      /^[0-9a-f]{64}$/.test(sourceState.revision_identity))sourceRevision=sourceState.revision_identity;
    byId("source-total").textContent=newPage.total.toLocaleString();
    byId("workflow-total").textContent=newWorkflow.total.toLocaleString();
    const counts=workflowStatus.statuses;
    const known=counts && Object.values(counts).every(n=>Number.isSafeInteger(n) && n>=0);
    const validStatus=workflowStatus.read_only===true && workflowStatus.outreach_authorized===false &&
      Number.isSafeInteger(workflowStatus.unclassified) && workflowStatus.unclassified>=0 &&
      known && Object.values(counts).reduce((a,b)=>a+b,workflowStatus.unclassified)===workflowStatus.total &&
      workflowStatus.total===newWorkflow.total;
    for(const [status,id] of [["ready","workflow-ready"],["review","workflow-review"],["hold","workflow-hold"]])
      byId(id).textContent=validStatus && Number.isSafeInteger(counts[status]) ? String(counts[status]) : "—";
    selected=null;selectedRecord=null;renderDossier(null);renderRecords();renderMap();
    const focus=focusIdentity ? records().find(r=>identity(r)===focusIdentity) : null;
    if(focus)selectRow(focus);
    byId("global-notice").textContent="Retained SQLite records only · "+newPage.total+" matching "+activeKind+" source records"+
      (activeCounty?" in "+activeCounty+" County":" across retained counties")+" · "+
      (newFootprint.truncated?"map scan truncated · ":"")+"readiness and live collection not enabled · "+
      (health.read_only?"read-only access":"operator status requires review")+"."+
      (!validStatus?" Workflow-status breakdown unavailable or inconsistent.":"")+
      (focusIdentity && !focus ? " Selected map point moved or disappeared from its recorded position; refresh before inspecting it." : "");
  }catch(error){
    if(token!==pageRequest)return;
    page=null;footprint=null;workflows=null;selected=null;selectedRecord=null;
    byId("source-total").textContent="—";byId("workflow-total").textContent="—";
    for(const id of ["workflow-ready","workflow-review","workflow-hold"])byId(id).textContent="—";
    byId("global-notice").textContent="Data unavailable: "+String(error.message || error)+". Check the selected existing SQLite database; no synthetic records will be substituted.";
    renderDossier(null);renderRecords();renderMap();
  }
}
async function refreshAfterExternalSourceChange() {
  if(sourceProbeActive || !page || byId("command-view").hidden ||
    document.visibilityState==="hidden" || document.activeElement===byId("search-term"))
    return;
  sourceProbeActive=true;
  const observedPageRequest=pageRequest;
  try {
    const state=await fetchJson("/api/source-revision");
    if(observedPageRequest!==pageRequest || byId("command-view").hidden)return;
    if(state.read_only!==true || state.live_collection_enabled!==false ||
      typeof state.revision_identity!=="string" ||
      !/^[0-9a-f]{64}$/.test(state.revision_identity))return;
    if(sourceRevision!==null && state.revision_identity!==sourceRevision){
      const previousSelection=selected, previousOffset=pageOffset;
      await loadData(previousOffset,previousSelection);
      if(page)byId("global-notice").textContent +=
        " Refreshed after a change in local SQLite source records. Remote collection is not running.";
    } else if(sourceRevision===null)sourceRevision=state.revision_identity;
  }catch(_){
    // A local revision probe is optional: never block or fabricate core records.
  }finally{
    sourceProbeActive=false;
  }
}
if(typeof window.setInterval==="function")
  window.setInterval(refreshAfterExternalSourceChange,90_000);

document.querySelectorAll("[data-section]").forEach(button=>button.onclick=()=>showSection(button.dataset.section));
function applySourceFilter(kind,county){
  byId("filter-kind").value=kind;byId("filter-county").value=county;
  activeKind=kind;activeCounty=county;activeQuery=byId("search-term").value.trim();
  pageOffset=0;showHome();loadData(0);
}
byId("global-search").onsubmit=event=>{event.preventDefault();applySourceFilter(byId("filter-kind").value,byId("filter-county").value);};
for (const id of ["filter-kind","filter-county"]) byId(id).onchange=()=>applySourceFilter(byId("filter-kind").value,byId("filter-county").value);
byId("previous-records").onclick=()=>{if(page&&page.offset>0)loadData(Math.max(0,page.offset-50));};
byId("next-records").onclick=()=>{if(page&&page.has_more)loadData(page.offset+page.limit);};
byId("source-stat").onclick=()=>{showHome();byId("command-records").scrollIntoView({block:"nearest"});};
byId("notification-button").onclick=()=>showSection("watchlist");
byId("open-watchlist").onclick=()=>showSection("watchlist");
window.addEventListener("popstate",()=>{if(location.pathname==="/")showHome();});
updateWatchCounters();renderWatchlist();loadData();
