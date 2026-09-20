"use strict";
const $ = id => document.getElementById(id);
const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
let mode = "records", snapshot = null, selected = null, offset = 0, requestId = 0, controller;
let query = "", kind = "all", county = "";
const LIMIT = 50;
const rows = () => snapshot ? (mode === "records" ? snapshot.projects : snapshot.leads) : [];
const rowId = row => row.record_kind ? `${row.record_kind}:${row.record_id}` : row.workflow_id;
function bullets(items) { return items?.length ? "<ul>" + items.map(x => "<li>" + esc(x) + "</li>").join("") + "</ul>" : '<p class="empty">None recorded.</p>'; }
function datum(label, value) { return '<div class="datum"><span>' + esc(label) + '</span>' + esc(value ?? "Not recorded") + '</div>'; }
function evidence(items) {
  if (!items?.length) return '<p class="empty">No provenance recorded.</p>';
  return items.map(p => {
    let link = "";
    try { const url = new URL(p.source_url); if (["http:","https:"].includes(url.protocol) && !url.username && !url.password) link = '<a target="_blank" rel="noopener noreferrer" href="' + esc(url.href) + '">Open source record</a>'; } catch (_) { /* Missing URLs remain plain text. */ }
    return '<div class="evidence"><b>' + esc(p.source_name) + '</b><small>Captured: ' + esc(p.captured_at || "not recorded") + ' · Source verification flag: ' + (p.verified ? "true" : "false") + '</small>' + link + (p.evidence_text ? '<p>' + esc(p.evidence_text) + '</p>' : '') + (p.raw_reference ? '<small>Retained reference: ' + esc(p.raw_reference) + '</small>' : '') + (p.notes ? '<p>' + esc(p.notes) + '</p>' : '') + '</div>';
  }).join("");
}
function selectRecord(id) {
  selected = id;
  const row = rows().find(x => rowId(x) === id);
  if (!row) { $("detail").innerHTML = '<p class="empty">Select a record to inspect its evidence.</p>'; return; }
  if (mode === "records") {
    $("detail").innerHTML = '<div class="eyebrow">' + esc(row.record_kind) + ' · source record</div><h2>' + esc(row.title) + '</h2><p>' + esc(row.description || "No description recorded.") + '</p><div class="detail-grid">' + datum("County", row.county) + datum("Jurisdiction / agency", row.jurisdiction) + datum("Source status / document", row.source_status) + datum("Source record number", row.source_record_number) + datum("Address", row.address) + datum("APN", row.apn) + datum("Record identity", row.record_id) + datum("Coordinates", row.point ? `${row.point.latitude.toFixed(6)}, ${row.point.longitude.toFixed(6)}` : null) + '</div><p>' + esc(row.map_reason) + '</p><h3>Named parties · source claims</h3>' + (row.entities.map(e => '<div class="party"><b>' + esc(e.name) + '</b> · ' + esc(e.role) + evidence(e.provenance) + '</div>').join("") || '<p class="empty">No named parties recorded.</p>') + '<h3>Record evidence</h3>' + evidence(row.provenance) + (row.point ? '<h3>Location evidence</h3>' + evidence(row.point.provenance) : '') + '<h3>Limitations</h3>' + bullets(row.limitations);
  } else {
    $("detail").innerHTML = '<div class="eyebrow">' + esc(row.status) + ' · persisted workflow</div><h2>' + esc(row.summary || row.base_candidate_id) + '</h2><div class="detail-grid">' + datum("Workflow", row.workflow_id) + datum("Exact review package", row.package_id) + datum("Candidate", row.base_candidate_id) + datum("Recorded score", row.lead_score) + '</div><h3>Evidence notes</h3>' + bullets(row.evidence_notes) + '<h3>Workflow notes</h3>' + bullets(row.notes) + '<h3>Limitations</h3>' + bullets(row.limitations) + '<h3>Recorded history</h3>' + bullets(row.events.map(e => `${e.created_at}: ${e.current_status} — ${e.reason}`));
  }
  renderList(); renderMap();
}
function renderList() {
  $("records").innerHTML = rows().map(row => '<button class="record ' + (rowId(row) === selected ? 'selected' : '') + '" data-id="' + esc(rowId(row)) + '"><span class="tag">' + esc(mode === "records" ? row.record_kind : row.status) + '</span><strong>' + esc(row.title || row.summary || row.base_candidate_id) + '</strong><small>' + esc(mode === "records" ? (row.county || "County unknown") + ' · ' + (row.jurisdiction || "Agency unknown") : 'Score ' + row.lead_score + ' · ' + row.workflow_id) + '</small><small>' + esc(mode === "records" ? (row.point ? "Source coordinates available" : "Location not mapped") + (row.coverage === "outside_target_counties" ? " · Outside target counties" : "") : row.package_id) + '</small></button>').join("") || '<p class="empty">No stored records match this view. Use the existing intake commands to populate this database.</p>';
  $("records").querySelectorAll("button[data-id]").forEach(el => el.onclick = () => selectRecord(el.dataset.id));
}
async function load() {
  const id = ++requestId;
  controller?.abort(); controller = new AbortController(); snapshot = null; selected = null;
  $("error").hidden = true; $("status").textContent = "Reading stored data…";
  $("records").innerHTML = '<p class="empty">Loading…</p>'; $("detail").innerHTML = '<p class="empty">Select a record to inspect its evidence.</p>';
  $("previous").disabled = true; $("next").disabled = true; $("visible").textContent = ""; $("page-count").textContent = ""; renderMap();
  const parameters = new URLSearchParams({limit: LIMIT, offset});
  if (mode === "records") { parameters.set("kind", kind); parameters.set("q", query); parameters.set("county", county); }
  try {
    const response = await fetch((mode === "records" ? "/api/snapshot?" : "/api/workflows?") + parameters, {signal: controller.signal});
    const data = await response.json();
    if (!response.ok) throw Error(data.error || "Unable to read stored data.");
    if (id !== requestId) return;
    snapshot = data;
    $("visible").textContent = data.total + " matching";
    $("page-count").textContent = data.returned ? `${offset + 1}–${offset + data.returned} of ${data.total}` : `0 of ${data.total}`;
    $("previous").disabled = offset === 0; $("next").disabled = !data.has_more;
    $("status").textContent = mode === "records" ? `${data.returned} source records on this page · ${data.mapped_on_page} mapped · ${data.returned - data.mapped_on_page} unmapped. Records and historical status do not establish qualified leads or current construction activity.` : `${data.returned} workflows on this page. Status and scores are retained values; external actions remain unavailable.`;
    renderList(); fitMap();
  } catch (error) {
    if (id !== requestId || error.name === "AbortError") return;
    $("error").textContent = error.message; $("error").hidden = false; $("status").textContent = "Data unavailable.";
    $("records").innerHTML = '<p class="empty">Check the selected database, then refresh.</p>';
  }
}
function switchMode(next) {
  mode = next; offset = 0;
  $("filters").hidden = mode !== "records"; $("map-card").hidden = mode !== "records";
  $("heading").textContent = mode === "records" ? "Project records" : "Lead workflow";
  $("list-title").textContent = mode === "records" ? "Source records" : "Persisted workflows";
  ["records", "workflow"].forEach(v => { const active = (v === "records") === (mode === "records"); $(v + "-tab").classList.toggle("active", active); $(v + "-tab").setAttribute("aria-pressed", active); });
  load();
}
// World coordinates are normalized Web Mercator units. One scale serves both axes.
function project(lat, lon) { return [(lon + 180) / 360, (1 - Math.asinh(Math.tan(lat * Math.PI / 180)) / Math.PI) / 2]; }
function unproject(x, y) { return [Math.atan(Math.sinh(Math.PI * (1 - 2 * y))) * 180 / Math.PI, x * 360 - 180]; }
let center = project(34.0, -116.8), scale = 12000;
const svg = $("map");
const points = () => mode === "records" ? rows().filter(x => x.point) : [];
function fitMap() {
  const available = points();
  if (available.length) {
    const coords = available.map(r => project(r.point.latitude, r.point.longitude));
    const xs = coords.map(v => v[0]), ys = coords.map(v => v[1]);
    const xmin = Math.min(...xs), xmax = Math.max(...xs), ymin = Math.min(...ys), ymax = Math.max(...ys);
    center = [(xmin + xmax) / 2, (ymin + ymax) / 2];
    const w = svg.clientWidth || 500, h = svg.clientHeight || 350;
    scale = Math.max(150, Math.min(2000000, (w - 100) / Math.max(xmax - xmin, .0005), (h - 110) / Math.max(ymax - ymin, .0005)));
  } else { center = project(34.0, -116.8); scale = 12000; }
  renderMap();
}
function renderMap() {
  const width = svg.clientWidth || 500, height = svg.clientHeight || 350;
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  const xy = (lat, lon) => { const p = project(lat, lon); return [width / 2 + (p[0] - center[0]) * scale, height / 2 + (p[1] - center[1]) * scale]; };
  const span = width / scale * 360;
  const step = [0.001,0.005,0.01,0.05,0.1,0.25,0.5,1,2,5,10,20,30,60].find(s => s >= span / 8) || 60;
  const left = Math.max(-180, (center[0] - width / scale / 2) * 360 - 180), right = Math.min(180, (center[0] + width / scale / 2) * 360 - 180);
  let content = '';
  for (let lon = Math.ceil(left / step) * step; lon <= right; lon += step) {
    const [x] = xy(0, lon);
    content += `<line class="grid-line" x1="${x}" y1="0" x2="${x}" y2="${height}"/><text class="grid-label" x="${x + 4}" y="${height - 8}">${lon.toFixed(step < .01 ? 3 : 2)}°</text>`;
  }
  const south = Math.max(-85, unproject(0, center[1] + height / scale / 2)[0]), north = Math.min(85, unproject(0, center[1] - height / scale / 2)[0]);
  for (let lat = Math.ceil(south / step) * step; lat <= north; lat += step) {
    const [,y] = xy(lat, 0);
    content += `<line class="grid-line" x1="0" y1="${y}" x2="${width}" y2="${y}"/><text class="grid-label" x="${width - 64}" y="${y - 5}">${lat.toFixed(step < .01 ? 3 : 2)}°</text>`;
  }
  let inView = 0;
  for (const row of points()) {
    const [x,y] = xy(row.point.latitude, row.point.longitude);
    if (x < 0 || x > width || y < 0 || y > height) continue;
    inView++;
    content += `<circle class="pin ${selected === rowId(row) ? 'selected' : ''}" cx="${x}" cy="${y}" r="7" tabindex="0" role="button" aria-label="${esc(row.title)}" data-id="${esc(rowId(row))}"><title>${esc(row.title)} · source-claimed location</title></circle>`;
  }
  svg.innerHTML = content;
  svg.querySelectorAll(".pin").forEach(el => { el.onclick = () => selectRecord(el.dataset.id); el.onkeydown = e => { if (["Enter"," "].includes(e.key)) { e.preventDefault(); selectRecord(el.dataset.id); } }; });
  $("map-empty").hidden = points().length > 0;
  $("map-count").textContent = `${inView} in view / ${points().length} on page`;
}
function zoom(factor, x = svg.clientWidth / 2, y = svg.clientHeight / 2) {
  const next = Math.max(150, Math.min(2000000, scale * factor));
  center[0] += (x - svg.clientWidth / 2) * (1 / scale - 1 / next);
  center[1] += (y - svg.clientHeight / 2) * (1 / scale - 1 / next);
  scale = next; renderMap();
}
let drag = null;
svg.addEventListener("pointerdown", e => { if (e.target.closest(".pin")) return; drag = [e.clientX, e.clientY, ...center]; svg.setPointerCapture(e.pointerId); });
svg.addEventListener("pointermove", e => { if (!drag) return; center = [drag[2] - (e.clientX - drag[0]) / scale, drag[3] - (e.clientY - drag[1]) / scale]; renderMap(); });
svg.addEventListener("pointerup", () => { drag = null; }); svg.addEventListener("pointercancel", () => { drag = null; });
svg.addEventListener("wheel", e => { e.preventDefault(); const r = svg.getBoundingClientRect(); zoom(e.deltaY < 0 ? 1.2 : 1 / 1.2, e.clientX - r.left, e.clientY - r.top); }, {passive:false});
svg.addEventListener("keydown", e => {
  if (e.target !== svg) return;
  if (["+","=","-"].includes(e.key)) { e.preventDefault(); zoom(e.key === "-" ? 1 / 1.5 : 1.5); }
  const moves = {ArrowLeft:[-1,0],ArrowRight:[1,0],ArrowUp:[0,-1],ArrowDown:[0,1]};
  if (moves[e.key]) { e.preventDefault(); center = center.map((c,i) => c + moves[e.key][i] * 50 / scale); renderMap(); }
});
new ResizeObserver(renderMap).observe(svg);
$("zoom-in").onclick = () => zoom(1.5); $("zoom-out").onclick = () => zoom(1 / 1.5);
$("fit").onclick = fitMap; $("region").onclick = () => { center = project(34.0, -116.8); scale = 12000; renderMap(); };
$("records-tab").onclick = () => switchMode("records"); $("workflow-tab").onclick = () => switchMode("workflow");
$("filters").onsubmit = e => { e.preventDefault(); query = $("search").value.trim(); kind = $("kind").value; county = $("county").value; offset = 0; load(); };
$("refresh").onclick = load;
$("previous").onclick = () => { offset = Math.max(0, offset - LIMIT); load(); };
$("next").onclick = () => { offset += LIMIT; load(); };
load();
