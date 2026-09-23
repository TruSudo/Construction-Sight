
"use strict";
const byId = id => document.getElementById(id);
const escapeText = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const identity = row => row.record_kind + ":" + row.record_id;
const WATCH_KEY = "constructionsight:operator:local-watchlist-v1";
let page = null, footprint = null, workflows = null, selected = null, activeQuery = "", pageRequest = 0;
let localWatchlist = {};
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
    '<button type="button" data-remove="' + index + '">Remove</button></div>'
  ).join("") || '<p class="empty" style="padding:12px">No watched source records in this browser.</p>';
  const target = full ? byId("feature-body") : byId("watchlist-summary");
  if (full) {
    target.innerHTML = '<section class="feature-card"><h2>Saved source-record bookmarks</h2><p>These bookmarks are stored only in this browser. They do not subscribe to permit changes, schedule reminders, perform source polling, or send notifications.</p><div id="full-watchlist">' + markup + '</div><a href="/workspace#records">Browse retained source records →</a></section>';
  } else target.innerHTML = markup;
  target.querySelectorAll("[data-remove]").forEach(button => button.onclick = () => {
    const currentKey = (full ? entries : entries.slice(0,4))[Number(button.dataset.remove)]?.[0];
    if (currentKey) { delete localWatchlist[currentKey]; saveWatchlist(); if (full) renderWatchlist(true); }
  });
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
    '<a class="action" href="/workspace#records">Inspect full source evidence →</a></div>';
  byId("watch-selected").onclick = () => toggleWatch(row);
}
function renderRecords() {
  const target = byId("command-records");
  const items = records().slice(0,7);
  target.innerHTML = items.map((row,index) =>
    '<button class="record-row' + (selected === identity(row) ? ' selected' : '') +
    '" data-record="' + index + '" type="button"><i class="dot unknown" title="Unassessed" aria-label="Unassessed"></i><strong>' +
    escapeText(row.title || "Untitled record") + '</strong><small>' + escapeText(valueOrUnknown(row.county)) +
    '</small><small>' + escapeText(row.record_kind.toUpperCase()) + '</small></button>'
  ).join("") || '<p class="empty" style="padding:12px">No retained source records match the current query.</p>';
  target.querySelectorAll("[data-record]").forEach(el => el.onclick = () => selectRow(items[Number(el.dataset.record)]));
  byId("records-scope").textContent = page ? "Showing " + items.length + " of " + page.total +
    " matching source records. Not deduplicated projects or qualified leads." : "Source records unavailable.";
}
function selectRow(row) {
  if (!row) return;
  selected = identity(row); renderDossier(row); renderRecords();
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
      else {selected=null;byId("command-dossier").innerHTML='<span class="badge">SOURCE RECORD · NOT ON CURRENT PAGE</span><h3>'+escapeText(p.title || "Source record")+'</h3><p>'+escapeText(valueOrUnknown(p.county))+' · '+escapeText(p.record_kind)+' · source-claimed location. Open the full map to inspect records outside the current page.</p><a class="action" href="/workspace#map">Open full map →</a>';renderRecords();}};
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
function showSection(name) {
  byId("command-view").hidden=true;byId("feature-view").hidden=false;
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
function showHome(){byId("command-view").hidden=false;byId("feature-view").hidden=true;document.querySelectorAll("[data-section]").forEach(n=>{n.classList.remove("current");n.setAttribute("aria-pressed","false");});document.querySelector('a[href="/"]').classList.add("current");}
async function fetchJson(url){
  const response=await fetch(url,{cache:"no-store"});
  const data=await response.json();
  if(!response.ok) throw Error(data.error || "Local data unavailable.");
  return data;
}
async function loadData(){
  const token=++pageRequest;
  byId("global-notice").textContent="Loading retained local records. Readiness, outreach, bidding, and live watchlist monitoring are not enabled.";
  const filter=new URLSearchParams({kind:"all",limit:"50",offset:"0",q:activeQuery});
  const geo=new URLSearchParams({kind:"all",q:activeQuery});
  try{
    const [newPage,newFootprint,newWorkflow,health]=await Promise.all([
      fetchJson("/api/snapshot?"+filter),fetchJson("/api/footprint?"+geo),
      fetchJson("/api/workflows?limit=50&offset=0"),fetchJson("/api/health")
    ]);
    if(token!==pageRequest)return;
    if(newPage.total!==newFootprint.matching_total)throw Error("Source-list and geographic scope disagree. Refresh the database view.");
    page=newPage;footprint=newFootprint;workflows=newWorkflow;
    byId("source-total").textContent=newPage.total.toLocaleString();
    byId("workflow-total").textContent=newWorkflow.total.toLocaleString();
    selected=null;renderDossier(null);renderRecords();renderMap();
    byId("global-notice").textContent="Retained SQLite records only · "+newPage.total+" matching source records · "+
      (newFootprint.truncated?"map scan truncated · ":"")+"readiness and live collection not enabled · "+
      (health.read_only?"read-only access":"operator status requires review")+".";
  }catch(error){
    if(token!==pageRequest)return;
    page=null;footprint=null;workflows=null;selected=null;
    byId("source-total").textContent="—";byId("workflow-total").textContent="—";
    byId("global-notice").textContent="Data unavailable: "+String(error.message || error)+". Check the selected existing SQLite database; no synthetic records will be substituted.";
    renderDossier(null);renderRecords();renderMap();
  }
}
document.querySelectorAll("[data-section]").forEach(button=>button.onclick=()=>showSection(button.dataset.section));
byId("global-search").onsubmit=event=>{event.preventDefault();activeQuery=byId("search-term").value.trim();showHome();loadData();};
byId("source-stat").onclick=()=>{showHome();byId("command-records").scrollIntoView({block:"nearest"});};
byId("notification-button").onclick=()=>showSection("watchlist");
byId("open-watchlist").onclick=()=>showSection("watchlist");
window.addEventListener("popstate",()=>{if(location.pathname==="/")showHome();});
updateWatchCounters();renderWatchlist();loadData();
