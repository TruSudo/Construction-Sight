"use strict";
const $ = id => document.getElementById(id);
const esc = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
let mode = "records", snapshot = null, footprint = null, timeline = null, selected = null, pendingSelection = null, offset = 0, requestId = 0, controller;
let query = "", kind = "all", county = "";
let entityRequestId = 0, candidateRequestId = 0, parcelRequestId = 0, relatedIds = new Set();
let parcelOverlay = [];
let lastLoadedScope = null;
const LIMIT = 50;
const rows = () => snapshot ? (mode === "records" ? snapshot.projects : snapshot.leads) : [];
const rowId = row => row.record_kind ? `${row.record_kind}:${row.record_id}` : row.workflow_id;
function bullets(items) { return items?.length ? "<ul>" + items.map(x => "<li>" + esc(x) + "</li>").join("") + "</ul>" : '<p class="empty">None recorded.</p>'; }
const milestoneNames = {
  ceqa_received: "CEQA received",
  ceqa_posted: "CEQA posted",
  permit_applied: "Permit application",
  permit_issued: "Permit issuance",
  permit_finaled: "Permit finalization"
};
function milestoneHistory(items) {
  if (!items?.length) return '<p class="empty">No dated source milestones recorded.</p>';
  return '<ol class="milestones">' + items.map(item =>
    '<li><time datetime="' + esc(item.recorded_date) + '">' +
    esc(item.recorded_date) + '</time> · ' +
    esc(milestoneNames[item.event_kind] || "Unrecognized source event") +
    ' <small>Source-claimed record date</small></li>'
  ).join("") + '</ol>';
}
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
  entityRequestId++; candidateRequestId++; parcelRequestId++;
  relatedIds = new Set(); parcelOverlay = [];
  selected = id;
  const row = rows().find(x => rowId(x) === id);
  if (!row) { $("detail").innerHTML = '<p class="empty">Select a record to inspect its evidence.</p>'; return; }
  if (mode === "records") {
    $("detail").innerHTML = '<div class="eyebrow">' + esc(row.record_kind) + ' · source record</div><h2>' + esc(row.title) + '</h2><p>' + esc(row.description || "No description recorded.") + '</p><div class="detail-grid">' + datum("County", row.county) + datum("Jurisdiction / agency", row.jurisdiction) + datum("Source status / document", row.source_status) + datum("Source record number", row.source_record_number) + datum("Address", row.address) + datum("APN", row.apn) + datum("Record identity", row.record_id) + datum("Coordinates", row.point ? `${row.point.latitude.toFixed(6)}, ${row.point.longitude.toFixed(6)}` : null) + '</div><p>' + esc(row.map_reason) + '</p><h3>Parcel observations · unverified APN candidates</h3><button type="button" id="inspect-parcels">Inspect retained parcel claims</button><div id="parcel-candidates" class="parcel-candidates" aria-live="polite"></div><h3>Candidate review · no commercial authorization</h3><button type="button" id="preview-candidate">Inspect review gaps</button><div id="candidate-preview" class="candidate-preview" aria-live="polite"></div><h3>Recorded milestones · historical source claims</h3>' + milestoneHistory(row.milestones) + '<p class="entity-warning">Recorded dates do not verify site activity, construction start, or a current project phase.</p><h3>Named parties · source claims</h3>' + (row.entities.map(e => '<div class="party"><b>' + esc(e.name) + '</b> · ' + esc(e.role) + ' <button type="button" class="entity-link" data-entity-key="' + esc(e.entity_key) + '">Find shared-key source records</button>' + evidence(e.provenance) + '</div>').join("") || '<p class="empty">No named parties recorded.</p>') + '<div id="entity-related" class="entity-related" aria-live="polite"></div><h3>Record evidence</h3>' + evidence(row.provenance) + (row.point ? '<h3>Location evidence</h3>' + evidence(row.point.provenance) : '') + '<h3>Limitations</h3>' + bullets(row.limitations);
  } else {
    $("detail").innerHTML = '<div class="eyebrow">' + esc(row.status) + ' · persisted workflow</div><h2>' + esc(row.summary || row.base_candidate_id) + '</h2><div class="detail-grid">' + datum("Workflow", row.workflow_id) + datum("Exact review package", row.package_id) + datum("Candidate", row.base_candidate_id) + datum("Recorded score", row.lead_score) + '</div><h3>Evidence notes</h3>' + bullets(row.evidence_notes) + '<h3>Workflow notes</h3>' + bullets(row.notes) + '<h3>Limitations</h3>' + bullets(row.limitations) + '<h3>Recorded history</h3>' + bullets(row.events.map(e => `${e.created_at}: ${e.current_status} — ${e.reason}`));
  }
  const parcelButton = $("inspect-parcels");
  if (parcelButton && mode === "records") parcelButton.onclick = inspectParcels;
  const previewButton = $("preview-candidate");
  if (previewButton && mode === "records") previewButton.onclick = inspectCandidate;
  $("detail").querySelectorAll("button[data-entity-key]").forEach(button => {
    button.onclick = () => inspectEntity(button.dataset.entityKey);
  });
  renderList(); renderMap();
}
function renderList() {
  $("records").innerHTML = rows().map(row => '<button class="record ' + (rowId(row) === selected ? 'selected' : '') + '" data-id="' + esc(rowId(row)) + '"><span class="tag">' + esc(mode === "records" ? row.record_kind : row.status) + '</span><strong>' + esc(row.title || row.summary || row.base_candidate_id) + '</strong><small>' + esc(mode === "records" ? (row.county || "County unknown") + ' · ' + (row.jurisdiction || "Agency unknown") : 'Score ' + row.lead_score + ' · ' + row.workflow_id) + '</small><small>' + esc(mode === "records" ? (row.point ? "Source coordinates available" : "Location not mapped") + (row.coverage === "outside_target_counties" ? " · Outside target counties" : "") : row.package_id) + '</small></button>').join("") || '<p class="empty">No stored records match this view. Use the existing intake commands to populate this database.</p>';
  $("records").querySelectorAll("button[data-id]").forEach(el => el.onclick = () => selectRecord(el.dataset.id));
}
function resetPulse(message = "—") {
  ["pulse-matching", "pulse-mapped", "pulse-unmapped", "pulse-scan"].forEach(id => {
    $(id).textContent = message;
  });
  $("pulse-scan-note").textContent = "Counts cover retained source records in the current filters.";
}
function renderPulse(data, mapData) {
  $("pulse-matching").textContent = data.total.toLocaleString();
  $("pulse-mapped").textContent = mapData.mapped_in_scan.toLocaleString();
  $("pulse-unmapped").textContent = (mapData.records_scanned - mapData.mapped_in_scan).toLocaleString();
  const mismatch = data.total !== mapData.matching_total;
  $("pulse-scan").textContent = mismatch ? "Read mismatch"
    : mapData.truncated ? "Capped" : "Complete";
  $("pulse-scan-note").textContent = mismatch
    ? "List and coordinate map were read separately and disagree. Refresh before using record positions."
    : mapData.truncated
      ? `${mapData.records_scanned.toLocaleString()} of ${mapData.matching_total.toLocaleString()} matching records scanned; additional records may be unmapped or uncounted.`
      : `${mapData.records_scanned.toLocaleString()} of ${mapData.matching_total.toLocaleString()} matching retained records scanned. This is not jurisdictional source coverage.`;
}
async function load() {
  entityRequestId++; candidateRequestId++; parcelRequestId++;
  relatedIds = new Set(); parcelOverlay = [];
  const id = ++requestId;
  const scope = JSON.stringify([mode, kind, query, county]);
  const shouldFit = scope !== lastLoadedScope;
  controller?.abort(); controller = new AbortController(); snapshot = null; footprint = null; timeline = null; selected = null;
  $("error").hidden = true; $("status").textContent = "Reading stored data…";
  resetPulse("Reading…");
  $("records").innerHTML = '<p class="empty">Loading…</p>'; $("detail").innerHTML = '<p class="empty">Select a record to inspect its evidence.</p>';
  $("timeline-list").innerHTML = '<p class="empty">Loading retained historical milestones…</p>'; $("timeline-count").textContent = "Reading…";
  $("previous").disabled = true; $("next").disabled = true; $("visible").textContent = ""; $("page-count").textContent = ""; renderMap();
  const parameters = new URLSearchParams({limit: LIMIT, offset});
  if (mode === "records") { parameters.set("kind", kind); parameters.set("q", query); parameters.set("county", county); }
  try {
    const requests = [fetch((mode === "records" ? "/api/snapshot?" : "/api/workflows?") + parameters, {signal: controller.signal})];
    if (mode === "records") {
      const mapParameters = new URLSearchParams({kind, q: query, county});
      requests.push(fetch("/api/footprint?" + mapParameters, {signal: controller.signal}));
      requests.push(fetch("/api/timeline?" + mapParameters, {signal: controller.signal}));
    }
    const responses = await Promise.all(requests);
    const payloads = await Promise.all(responses.map(response => response.json()));
    if (!responses[0].ok) throw Error(payloads[0].error || "Unable to read stored data.");
    if (responses[1] && !responses[1].ok) throw Error(payloads[1].error || "Unable to read geographic footprint.");
    if (responses[2] && !responses[2].ok) throw Error(payloads[2].error || "Unable to read historical milestones.");
    const data = payloads[0];
    if (id !== requestId) return;
    snapshot = data;
    footprint = payloads[1] || null;
    timeline = payloads[2] || null;
    lastLoadedScope = scope;
    if (mode === "records" && footprint) renderPulse(data, footprint);
    if (mode === "records") renderTimeline();
    $("visible").textContent = data.total + " matching";
    $("page-count").textContent = data.returned ? `${offset + 1}–${offset + data.returned} of ${data.total}` : `0 of ${data.total}`;
    $("previous").disabled = offset === 0; $("next").disabled = !data.has_more;
    $("status").textContent = mode === "records" ? `${data.returned} source records on this page · ${data.mapped_on_page} mapped · ${data.returned - data.mapped_on_page} unmapped. Records and historical status do not establish qualified leads or current construction activity.` : `${data.returned} workflows on this page. Status and scores are retained values; external actions remain unavailable.`;
    renderList();
    if (pendingSelection) {
      const target = pendingSelection;
      pendingSelection = null;
      if (rows().some(row => rowId(row) === target)) selectRecord(target);
    }
    if (shouldFit) fitMap(); else renderMap();
  } catch (error) {
    if (id !== requestId || error.name === "AbortError") return;
    $("error").textContent = error.message; $("error").hidden = false; $("status").textContent = "Data unavailable.";
    lastLoadedScope = null; resetPulse("Unavailable");
    $("timeline-count").textContent = "Unavailable"; $("timeline-list").textContent = "Historical milestones could not be read.";
    $("records").innerHTML = '<p class="empty">Check the selected database, then refresh.</p>';
  }
}
function renderTimeline() {
  if (!timeline) {
    $("timeline-count").textContent = "No retained events";
    $("timeline-list").innerHTML = '<p class="empty">No dated source milestones recorded.</p>';
    return;
  }
  const mismatch = !snapshot || snapshot.total !== timeline.matching_total ||
    (footprint && footprint.matching_total !== timeline.matching_total);
  const incomplete = timeline.source_scan_truncated || timeline.event_result_truncated;
  $("timeline-count").textContent = timeline.returned_events.toLocaleString() +
    " shown / " + timeline.milestones_in_scan.toLocaleString() + " dated events in scan";
  $("timeline-warning").textContent = mismatch
    ? "The list, map, and historical reads disagree. Refresh before navigating these events."
    : timeline.source_scan_truncated
      ? "Only the first " + timeline.records_scanned + " of " + timeline.matching_total +
        " matching records were scanned; newer dates may exist beyond that scope."
      : timeline.event_result_truncated
        ? "Showing only the latest " + timeline.returned_events + " of " +
          timeline.milestones_in_scan + " retained events in the scanned records."
        : "All " + timeline.matching_total +
          " matching source records were scanned. Dates are historical source claims, not current activity.";
  const names = {
    ceqa_received: "CEQA received", ceqa_posted: "CEQA posted",
    permit_applied: "Permit applied", permit_issued: "Permit issued",
    permit_finaled: "Permit finalized"
  };
  $("timeline-list").innerHTML = timeline.events.map((item, index) =>
    '<button type="button" class="timeline-row" data-timeline-index="' + index + '"' +
    (mismatch ? " disabled" : "") + '><time datetime="' + esc(item.recorded_date) + '">' +
    esc(item.recorded_date) + '</time><span><strong>' + esc(item.title) +
    '</strong><small>' + esc(names[item.event_kind] || "Unrecognized source event") +
    ' · ' + esc(item.record_kind) + ' · ' + esc(item.county || "County unknown") +
    (item.source_date_order_conflict ? ' · Contradictory date sequence: review required' : '') +
    '</small></span></button>'
  ).join("") || '<p class="empty">No dated source milestones recorded within the scan.</p>';
  if (incomplete && !mismatch) $("timeline-list").setAttribute("data-incomplete", "true");
  else $("timeline-list").removeAttribute("data-incomplete");
  $("timeline-list").querySelectorAll("button[data-timeline-index]").forEach(button => {
    button.onclick = () => {
      const event = timeline?.events[Number(button.dataset.timelineIndex)];
      if (!event || mismatch) return;
      const identity = rowId(event);
      if (rows().some(row => rowId(row) === identity)) selectRecord(identity);
      else {
        pendingSelection = identity;
        offset = Math.floor(event.ordinal / LIMIT) * LIMIT;
        load();
      }
    };
  });
}
async function inspectParcels() {
  if (mode !== "records" || !selected) return;
  const row = rows().find(item => rowId(item) === selected);
  const target = $("parcel-candidates");
  if (!row || !target) return;
  const token = ++parcelRequestId, sourceSelection = selected;
  parcelOverlay = [];
  renderMap();
  target.textContent = "Inspecting retained APN and county source claims…";
  try {
    const parameters = new URLSearchParams({
      kind: row.record_kind, record_id: row.record_id
    });
    const response = await fetch("/api/parcel-candidates?" + parameters);
    const data = await response.json();
    if (token !== parcelRequestId || selected !== sourceSelection || mode !== "records") return;
    if (!response.ok) throw Error(data.error || "Parcel observations are unavailable.");
    if (data.source_kind !== row.record_kind ||
        data.source_record_id !== row.record_id ||
        data.source_apn !== row.apn ||
        data.source_county !== row.county) {
      throw Error("Source record and parcel inspection identity disagree. Refresh.");
    }
    parcelOverlay = data.matches.filter(candidate => candidate.point);
    const summary = data.truncated
      ? "Showing the first " + data.returned + " of " + data.matching_total +
        " stored APN/county candidate records; other claims may exist."
      : data.matching_total + " stored APN/county candidate records.";
    const candidates = data.matches.map(parcel =>
      '<article class="parcel-claim"><b>' + esc(parcel.apn) + '</b> · ' +
      esc(parcel.county) +
      '<div class="detail-grid">' +
      datum("Source", parcel.source_key) +
      datum("Source record ID", parcel.source_record_id) +
      datum("Parcel record identity", parcel.parcel_record_id) +
      datum("Address claim", parcel.address) +
      datum("Zoning claim", parcel.zoning) +
      datum("Land-use claim", parcel.land_use) +
      datum("Source updated", parcel.source_updated_at) +
      datum("Geometry kind", parcel.geometry_kind) +
      datum("Coordinate reference", parcel.spatial_reference) + '</div>' +
      '<p>' + esc(parcel.map_reason) + '</p>' +
      '<h4>Retained limitations</h4>' + bullets(parcel.limitations) + '</article>'
    ).join("");
    target.innerHTML =
      '<p class="entity-warning">Exact normalized APN and county co-occurrence only. ' +
      'No parcel-to-project relationship, boundary, current activity, or authority is verified.</p>' +
      '<p>' + esc(summary) + ' ' +
      esc(parcelOverlay.length) + ' candidates have displayable source-claimed centroids.</p>' +
      (parcelOverlay.length ?
        '<button type="button" id="fit-parcel-candidates">Fit candidate centroids</button>' : '') +
      (candidates || '<p class="empty">No retained parcel claims matched this record.</p>') +
      '<h4>Inspection limitations</h4>' + bullets(data.limitations);
    const fitButton = $("fit-parcel-candidates");
    if (fitButton) fitButton.onclick = () => fitMap(false, true);
    renderMap();
  } catch (error) {
    if (token !== parcelRequestId || selected !== sourceSelection || mode !== "records") return;
    parcelOverlay = [];
    target.textContent = error.message || "Unable to inspect retained parcel claims.";
    renderMap();
  }
}
async function inspectCandidate() {
  if (mode !== "records" || !selected) return;
  const row = rows().find(item => rowId(item) === selected);
  const target = $("candidate-preview");
  if (!row || !target) return;
  const token = ++candidateRequestId, sourceSelection = selected;
  target.textContent = "Checking exact retained source for review gaps…";
  try {
    const parameters = new URLSearchParams({
      kind: row.record_kind, record_id: row.record_id
    });
    const response = await fetch("/api/candidate-preview?" + parameters);
    const result = await response.json();
    if (token !== candidateRequestId || selected !== sourceSelection || mode !== "records") return;
    if (!response.ok) throw Error(result.error || "Candidate review preview unavailable.");
    if (rowId(result.source_record) !== sourceSelection) throw Error("Source identity mismatch.");
    if (JSON.stringify(result.source_record) !== JSON.stringify(row)) {
      throw Error("The source record changed since this page was loaded. Refresh before reviewing.");
    }
    const checks = result.checks.map(check =>
      '<li><b>' + esc(check.key.replaceAll("_", " ")) + '</b> · ' +
      esc(check.state.replaceAll("_", " ")) + ': ' + esc(check.detail) + '</li>'
    ).join("");
    target.innerHTML =
      '<p class="entity-warning">Read-only preview. No lead, score, approval, deduplication, outreach or bid has been created or authorized.</p>' +
      '<div class="detail-grid">' +
      datum("Review state", result.state) +
      datum("Candidate review key", result.candidate_key) +
      datum("Normalized stored-source SHA-256", result.normalized_source_sha256) + '</div>' +
      '<h3>Required verification and review</h3><ul>' + checks +
      '</ul><h3>Candidate limitations</h3>' + bullets(result.limitations);
  } catch (error) {
    if (token !== candidateRequestId || selected !== sourceSelection || mode !== "records") return;
    target.textContent = error.message || "Candidate review preview unavailable.";
  }
}
async function inspectEntity(entityKey) {
  if (mode !== "records" || !entityKey) return;
  const target = $("entity-related");
  if (!target) return;
  const token = ++entityRequestId, sourceSelection = selected;
  const kindSelection = kind, countySelection = county;
  target.textContent = "Scanning retained source records for exact stored entity-key co-occurrence…";
  relatedIds = new Set(); renderMap();
  try {
    const parameters = new URLSearchParams({
      entity_key: entityKey, kind: kindSelection, county: countySelection
    });
    const historyParameters = new URLSearchParams({
      entity_key: entityKey, kind: kindSelection, county: countySelection
    });
    const [response, historyResponse] = await Promise.all([
      fetch("/api/entity-neighborhood?" + parameters),
      fetch("/api/timeline?" + historyParameters)
    ]);
    const [data, history] = await Promise.all([response.json(), historyResponse.json()]);
    if (token !== entityRequestId || selected !== sourceSelection || mode !== "records") return;
    if (!response.ok) throw Error(data.error || "Unable to inspect recorded entity co-occurrence.");
    if (!historyResponse.ok) throw Error(history.error || "Unable to inspect recorded entity history.");
    if (history.entity_key !== entityKey ||
        history.matching_total !== data.total_source_records ||
        history.records_scanned !== data.scanned_source_records) {
      throw Error("Entity history and relationship scans disagree. Refresh to inspect again.");
    }
    relatedIds = new Set(data.records.map(rowId));
    const scope = data.source_scan_truncated
      ? `Only the first ${data.scanned_source_records} of ${data.total_source_records} source records were scanned; additional matches may exist.`
      : `All ${data.total_source_records} matching-scope source records were scanned.`;
    const cap = data.matching_records_truncated
      ? `Only the first ${data.returned} of ${data.matching_records_in_scan} key matches are listed.`
      : `${data.matching_records_in_scan} exact-key matches in the scanned records.`;
    const mapped = points().filter(point => relatedIds.has(rowId(point))).length;
    const results = data.records.map(record =>
      '<li><b>' + esc(record.title) + '</b> · ' + esc(record.record_kind) +
      ' · ' + esc(record.county || "County unknown") + ' · ' +
      esc(record.record_id) + (record.point ? ' · source coordinates recorded' : ' · unmapped') +
      '</li>'
    ).join("");
    const eventLabels = {
      ceqa_received: "CEQA received", ceqa_posted: "CEQA posted",
      permit_applied: "Permit applied", permit_issued: "Permit issued",
      permit_finaled: "Permit finalized"
    };
    const historicalItems = history.events.map(event =>
      '<li><time datetime="' + esc(event.recorded_date) + '">' +
      esc(event.recorded_date) + '</time> · ' +
      esc(eventLabels[event.event_kind] || "Unrecognized source event") +
      ' · ' + esc(event.title) + ' · ' + esc(event.record_kind) +
      (event.source_date_order_conflict ? ' · Contradictory date sequence' : '') +
      '</li>'
    ).join("");
    const historicalScope = history.source_scan_truncated
      ? "Historical scan covered only the first " + history.records_scanned +
        " of " + history.matching_total + " source records. Newer dates may be outside this scan."
      : history.event_result_truncated
        ? "Only " + history.returned_events + " of " + history.milestones_in_scan +
          " source events for this exact key are displayed."
        : "All source records in this county and family scope were scanned for this exact key.";
    target.innerHTML =
      '<h3>Recorded shared entity key</h3><p class="entity-warning">These are exact stored-key co-occurrences, not proof that names identify the same real-world party. No projects are deduplicated or qualified.</p>' +
      '<p>' + esc(scope) + ' ' + esc(cap) + ' ' +
      esc(mapped) + ' matching mapped records appear in the current footprint.</p>' +
      (mapped ? '<button type="button" id="fit-related">Fit visible related locations</button>' : '') +
      (results ? '<ul class="entity-records">' + results + '</ul>' : '<p class="empty">No matching records were found within the scanned scope.</p>') +
      '<h3>Historical source events for this exact key</h3>' +
      '<p class="entity-warning">' + esc(historicalScope) + ' ' +
      esc(history.matching_entity_records_in_scan) +
      ' records share this key within the scan. Recorded dates do not establish current site activity or independently verified entity identity.</p>' +
      (historicalItems ? '<ol class="entity-records">' + historicalItems + '</ol>' :
        '<p class="empty">No dated events for this key within the scanned source records.</p>');
    const fitButton = $("fit-related");
    if (fitButton) fitButton.onclick = () => fitMap(true);
    renderMap();
  } catch (error) {
    if (token !== entityRequestId || selected !== sourceSelection || mode !== "records") return;
    relatedIds = new Set();
    target.textContent = error.message || "Unable to inspect recorded entity co-occurrence.";
    renderMap();
  }
}
function switchMode(next) {
  mode = next; offset = 0;
  $("filters").hidden = mode !== "records"; $("map-card").hidden = mode !== "records"; $("timeline-card").hidden = mode !== "records"; $("pulse").hidden = mode !== "records";
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
const points = () => mode === "records" && footprint ? footprint.points : [];
function selectMapPoint(id) {
  const row = rows().find(item => rowId(item) === id);
  if (row) { selectRecord(id); return; }
  const point = points().find(item => rowId(item) === id);
  if (!point) return;
  pendingSelection = id;
  offset = Math.floor(point.ordinal / LIMIT) * LIMIT;
  load();
}
function fitMap(onlyRelated = false, onlyParcels = false) {
  const available = onlyParcels ? parcelOverlay
    : onlyRelated === true ? points().filter(point => relatedIds.has(rowId(point))) : points();
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
    content += `<circle class="pin ${selected === rowId(row) ? 'selected' : relatedIds.has(rowId(row)) ? 'related' : ''}" cx="${x}" cy="${y}" r="7" tabindex="0" role="button" aria-label="${esc(row.title)}" data-id="${esc(rowId(row))}"><title>${esc(row.title)} · ${esc(row.record_kind)} source-claimed location</title></circle>`;
  }
  for (const parcel of parcelOverlay) {
    const [x, y] = xy(parcel.point.latitude, parcel.point.longitude);
    if (x < 0 || x > width || y < 0 || y > height) continue;
    content += '<circle class="parcel-pin" cx="' + x + '" cy="' + y +
      '" r="10"><title>' + esc(parcel.apn) + ' · ' +
      esc(parcel.source_key) +
      ' · unverified source-claimed parcel centroid; not a boundary</title></circle>';
  }
  svg.innerHTML = content;
  svg.querySelectorAll(".pin").forEach(el => { el.onclick = () => selectMapPoint(el.dataset.id); el.onkeydown = e => { if (["Enter"," "].includes(e.key)) { e.preventDefault(); selectMapPoint(el.dataset.id); } }; });
  $("map-empty").hidden = points().length > 0 || parcelOverlay.length > 0;
  const coverage = footprint?.truncated ? `first ${footprint.records_scanned} of ${footprint.matching_total} matching records scanned` : `${footprint?.matching_total || 0} matching records fully scanned`;
  $("map-count").textContent = `${inView} in view / ${points().length} mapped · ${coverage}` +
    (parcelOverlay.length ? ` · ${parcelOverlay.length} inspected parcel centroids` : "");
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
$("refresh").onclick = () => { lastLoadedScope = null; load(); };
$("previous").onclick = () => { offset = Math.max(0, offset - LIMIT); load(); };
$("next").onclick = () => { offset += LIMIT; load(); };
load();
