'use strict';

// Existing source/parcel projections only; never converts an observation into a lead.
async function renderRetainedSources(box) {
  if (!box.isConnected || activePage !== 'Sources & Collection') return;
  const root = document.createElement('section');
  root.className = 'retained-source-inspection';
  root.innerHTML = '<h3>Government source registry & retained review</h3><p role="status">Reading existing source records locally…</p>';
  box.append(root);
  let registry, revision, watches;
  try {
    [registry, revision, watches] = await Promise.all([
      api('/api/source-registry'),
      api('/api/source-revision'),
      api('/api/source-watchlist')
    ]);
  } catch (error) {
    if (root.isConnected) root.innerHTML =
      '<h3>Government source registry & retained review</h3><p role="alert">' +
      esc(error.message) + '</p>';
    return;
  }
  if (!root.isConnected || activePage !== 'Sources & Collection') return;
  if (!registry.available || !revision.available) {
    root.innerHTML = '<h3>Government source registry & retained review</h3>' +
      '<p role="status">An existing operator source database has not been connected. ' +
      'The SMARTS capture above remains separate. Launch with an explicit ' +
      '<code>--operator-database</code> path to inspect legacy retained records; ' +
      'nothing is acquired or created by this view.</p>';
    return;
  }
  const entries = registry.entries || [];
  const familyRows = Object.entries(revision.source_families || {});
  root.innerHTML = '<h3>Government source registry & retained review</h3>' +
    '<p>Read-only historical source metadata; neither a verification grant nor proof of an active jobsite. ' +
    'Configured sources: ' + esc(registry.total) + '; displayed: ' + esc(Math.min(50, entries.length)) +
    (registry.truncated || entries.length > 50 ? ' (bounded)' : '') +
    '. <button id="retained-registry-export">Export full returned registry JSON</button></p>' +
    table(['Registered source', 'County', 'Verification', 'Last checked', 'Adapter', 'Attributed records'],
      entries.slice(0, 50).map((r, i) => [
        '<button data-registry-index="' + i + '">' + esc(r.source_name) + '</button>',
        esc(r.county),
        esc(r.verification_status),
        esc(r.latest_verification_checked_at || r.last_checked_date),
        esc(r.adapter_status),
        esc(r.attributed_records_in_scan)
      ])) +
    '<p class="source-caution">' + esc((registry.limitations || []).join(' ')) + '</p>' +
    '<h3>Local source revisions</h3><p>' + esc(revision.meaning) +
    ' · Digest: <code>' + esc(revision.revision_identity) + '</code></p>' +
    table(['Family', 'Retained records', 'Last local update', 'Highest row'],
      familyRows.map(([name, r]) => [
        esc(name), esc(r.record_count), esc(r.latest_updated_at), esc(r.highest_row_id)
      ])) +
    '<h3>Source-specific watchlist</h3><p>Distinct from the commercial lead watchlist. ' +
    'Changes in retained source records can trigger existing watches; this display does not poll sources or notify anyone.</p>' +
    '<div id="retained-source-watchlist" aria-live="polite"></div>' +
    '<h3>Source observation review queue</h3>' +
    '<p>Exact retained CEQA/permit observations. Review does not merge investigations, authorize bids or send outreach.</p>' +
    '<form id="retained-source-filters" class="source-toolbar">' +
    '<label>Family <select name="kind"><option value="all">All</option><option value="ceqa">CEQA</option><option value="permit">Permit</option></select></label>' +
    '<label>County <select name="county"><option value="">Both counties</option><option>San Bernardino</option><option>Riverside</option></select></label>' +
    '<label>Search <input name="q" maxlength="200" aria-label="Search retained source records"></label>' +
    '<button type="submit">Inspect</button></form>' +
    '<div id="retained-source-queue" aria-live="polite"></div>' +
    '<div id="retained-capture-inbox" aria-live="polite"></div>' +
    '<div id="retained-smarts-history" aria-live="polite"></div>' +
    '<div id="retained-history-inspection"></div>';
  const watchPanel = root.querySelector('#retained-source-watchlist');
  async function changeSourceWatch(action, kind, recordId) {
    const updated = await api('/api/source-watchlist-action', {
      action, kind, record_id: recordId
    });
    if (!root.isConnected || activePage !== 'Sources & Collection') return;
    showSourceWatches(updated);
  }
  function showSourceWatches(state) {
    const items = (state.items || []).slice(0, 100);
    watchPanel.innerHTML = table(
      ['Source', 'Family', 'County', 'Watch status', 'Changed', 'Action'],
      items.map((w, i) => [
        esc(w.title || w.record_id), esc(w.record_kind), esc(w.county),
        esc(w.status), w.change_pending ? 'Retained change pending review' : '—',
        '<button data-source-unwatch="' + i + '">Archive watch</button>'
      ])
    ) + '<p>' + esc(state.total) + ' active source watches; ' +
      'remote source polling: ' + (state.remote_source_polling_enabled ? 'enabled' : 'disabled') +
      '. Watches do not authorize contacts, bids or notifications.</p>';
    watchPanel.querySelectorAll('[data-source-unwatch]').forEach(button => {
      button.onclick = () => perform(async () => {
        const w = items[Number(button.dataset.sourceUnwatch)];
        await changeSourceWatch('archive', w.record_kind, w.record_id);
      });
    });
  }
  showSourceWatches(watches);
  root.querySelector('#retained-registry-export').onclick = () =>
    download('retained-source-registry.json', registry);
  root.querySelectorAll('[data-registry-index]').forEach(button => {
    button.onclick = () => modal(
      'Registered source: ' + entries[Number(button.dataset.registryIndex)].source_name,
      '<p>Retained source metadata only; not current network authorization.</p><pre>' +
      esc(JSON.stringify(entries[Number(button.dataset.registryIndex)], null, 2)) + '</pre>'
    );
  });
  let offset = 0;
  const filters = root.querySelector('#retained-source-filters');
  const queue = root.querySelector('#retained-source-queue');
  async function loadPage() {
    const requestOffset = offset;
    const params = new URLSearchParams({kind: filters.elements.kind.value,
      county: filters.elements.county.value, q: filters.elements.q.value,
      limit: '10', offset: String(offset)});
    queue.textContent = 'Loading retained observations…';
    try {
      const page = await api('/api/source-review-queue?' + params);
      if (!root.isConnected || activePage !== 'Sources & Collection' ||
          requestOffset !== offset) return;
      if (!page.available) {
        queue.textContent = 'Source review is unavailable until an operator database is selected.';
        return;
      }
      queue.innerHTML = '<p>' + esc(page.total_source_records) +
        ' retained source observations match; page offset ' + esc(page.offset) +
        '. Not verified current construction or distinct opportunities.</p>' +
        table(['Record', 'Family', 'County', 'Review state', 'Inspection'],
          (page.items || []).map((r, i) => [
            esc(r.title), esc(r.record_kind), esc(r.county), esc(r.state),
            '<button data-source-preview="' + i + '">Source evidence</button> ' +
            '<button data-parcel-review="' + i + '">Parcel candidates</button> ' +
            '<button data-source-watch="' + i + '">Watch source</button> ' +
            '<button data-source-reconcile="' + i + '">Native evidence reconciliation</button>'
          ])) +
        '<div class="source-toolbar"><button id="retained-source-previous"' +
        (offset === 0 ? ' disabled' : '') + '>Previous</button>' +
        '<button id="retained-source-next"' +
        (page.has_more ? '' : ' disabled') + '>Next</button></div>';
      queue.querySelector('#retained-source-previous').onclick =
        () => { offset = Math.max(0, offset - 10); perform(loadPage); };
      queue.querySelector('#retained-source-next').onclick =
        () => { offset += 10; perform(loadPage); };
      queue.querySelectorAll('[data-source-reconcile]').forEach(button => {
        button.onclick = () => perform(async () => {
          const record = page.items[Number(button.dataset.sourceReconcile)];
          const inspection = await api('/api/source-reconciliation?' +
            new URLSearchParams({
              kind: record.record_kind, record_id: record.record_id
            }));
          if (!root.isConnected || activePage !== 'Sources & Collection') return;
          const needsReplay = inspection.replay_eligible === true;
          modal('Exact original → native investigation reconciliation',
            '<p>Exact original source evidence compared with the existing canonical ' +
            'investigation store. An unmatched source is NOT an independently ' +
            'verified project. Queuing retained evidence does not merge or authorize ' +
            'outreach, a bid, or a commercial lead.</p><pre>' +
            esc(JSON.stringify(inspection, null, 2)) + '</pre>' +
            (needsReplay ?
              '<p>To hand off only this exact snapshot to the common investigation ' +
              'worker, provide a human review reason and explicitly confirm.</p>' +
              '<label>Review reason <textarea id="source-reconcile-reason" ' +
              'maxlength="2000" rows="3" required></textarea></label>' +
              '<label><input id="source-reconcile-confirm" type="checkbox"> ' +
              'I reviewed this specific retained source evidence; replay only.</label>' +
              '<button id="source-reconcile-queue">Queue verified retained snapshot</button>' :
              '<p>No replay allowed. Existing or conflicting native evidence ' +
              'must be inspected through the canonical dossier and review workflow.</p>'));
          const queueButton = document.querySelector('#source-reconcile-queue');
          if (!queueButton) return;
          queueButton.onclick = () => perform(async () => {
            const reason = document.querySelector('#source-reconcile-reason')?.value.trim();
            const confirmed = document.querySelector('#source-reconcile-confirm')?.checked;
            if (!confirmed || !reason || reason.length < 10) {
              throw Error('Enter a reason of at least 10 characters and confirm the exact replay.');
            }
            queueButton.disabled = true;
            try {
              const receipt = await api('/api/source-reconciliation-queue', {
                kind: record.record_kind,
                record_id: record.record_id,
                expected_source_sha256: inspection.original_source.source_sha256,
                expected_native_evidence_id: inspection.native_evidence_id,
                caller_confirmation: true, review_reason: reason
              });
              if (!root.isConnected || activePage !== 'Sources & Collection') return;
              modal('Retained source accepted by investigation worker queue',
                '<p>Queued, not necessarily processed. No verified project identity ' +
                'or commercial authority is implied. The native worker must commit ' +
                'the evidence before it appears in canonical dossiers and the graph.</p>' +
                '<pre>' + esc(JSON.stringify(receipt, null, 2)) + '</pre>');
            } finally {
              if (queueButton.isConnected) queueButton.disabled = false;
            }
          });
        });
      });
      queue.querySelectorAll('[data-source-watch]').forEach(button => {
        button.onclick = () => perform(async () => {
          const record = page.items[Number(button.dataset.sourceWatch)];
          await changeSourceWatch('add', record.record_kind, record.record_id);
        });
      });
      for (const [attribute, endpoint] of [
        ['data-source-preview', '/api/candidate-preview'],
        ['data-parcel-review', '/api/parcel-candidates']
      ]) {
        queue.querySelectorAll('[' + attribute + ']').forEach(button => {
          button.onclick = () => perform(async () => {
            const record = page.items[Number(button.getAttribute(attribute))];
            const details = await api(endpoint + '?' + new URLSearchParams({
              kind: record.record_kind, record_id: record.record_id
            }));
            if (!root.isConnected || activePage !== 'Sources & Collection') return;
            modal(endpoint.endsWith('parcel-candidates') ? 'Retained parcel candidates' :
              'Exact source observation', '<p>Read-only source claims. Independent ' +
              'verification and operator approval are still required.</p><pre>' +
              esc(JSON.stringify(details, null, 2)) + '</pre>');
          });
        });
      }
    } catch (error) {
      if (queue.isConnected) queue.innerHTML =
        '<p role="alert">Retained source queue unavailable: ' + esc(error.message) + '</p>';
    }
  }
  filters.onsubmit = event => {
    event.preventDefault();
    offset = 0;
    perform(loadPage);
  };
  await loadPage();
  await Promise.all([
    renderRetainedCaptureInbox(root.querySelector('#retained-capture-inbox')),
    renderRetainedSmartsHistory(root.querySelector('#retained-smarts-history')),
    renderRetainedHistory(root.querySelector('#retained-history-inspection'))
  ]);
}

 


// Reuse original bounded immutable capture and ingestion evidence without authorizing ingestion.
async function renderRetainedCaptureInbox(box) {
  if (!box || !box.isConnected || activePage !== 'Sources & Collection') return;
  box.innerHTML = '<h3>Original CEQA capture & ingestion</h3>' +
    '<p role="status">Checking configured retained artifacts…</p>';
  try {
    const projections = await Promise.all([
      api('/api/source-capture-queue'), api('/api/source-ingestion-inbox')
    ]);
    if (!box.isConnected || activePage !== 'Sources & Collection') return;
    const categories = ['Exact SCH capture review', 'Listing / review-queue reconciliation'];
    box.innerHTML = '<h3>Original CEQA capture & ingestion</h3>' +
      '<p>Original read-only capture planning and inbox reconciliation. No source ' +
      'is fetched and no CEQA record is persisted, verified or promoted into a lead.</p>';
    projections.forEach((projection, index) => {
      const container = document.createElement('div');
      box.append(container);
      if (!projection.available || !projection.configured) {
        container.innerHTML = '<h3>' + esc(categories[index]) + '</h3>' +
          '<p>Not configured. Select the existing bounded artifacts at server launch. ' +
          'Absence is not an empty jurisdictional inbox.</p>';
        return;
      }
      const candidates = projection.candidates || [];
      container.innerHTML = '<h3>' + esc(categories[index]) + '</h3>' +
        '<p>' + esc(projection.candidate_count) + ' retained candidates; ' +
        'showing up to ' + esc(Math.min(50, candidates.length)) +
        ' of the returned projection. ' +
        esc((projection.limitations || []).join(' ')) + '</p>' +
        table(['Exact SCH / source claim', 'County / status', 'Evidence'], 
          candidates.slice(0, 50).map((entry, i) => [
            esc(entry.sch_number || entry.source_record_id || entry.candidate_key ||
              entry.source_claimed_title || 'Retained CEQA observation'),
            esc(entry.source_claimed_county || entry.county || entry.review_state ||
              entry.status || 'Unverified'),
            '<button data-capture-candidate="' + i + '">Inspect</button>'
          ])) +
        '<button data-capture-export>Export entire retained projection</button>';
      container.querySelector('[data-capture-export]').onclick = () =>
        download(index ? 'original-ceqa-ingestion-inbox.json' :
          'original-ceqa-capture-queue.json', projection);
      container.querySelectorAll('[data-capture-candidate]').forEach(button => {
        button.onclick = () => modal('Original retained capture evidence',
          '<p>Candidate only; human review and source authorization remain required.</p><pre>' +
          esc(JSON.stringify(candidates[Number(button.dataset.captureCandidate)], null, 2)) +
          '</pre>');
      });
    });
  } catch (error) {
    if (box.isConnected && activePage === 'Sources & Collection') box.innerHTML =
      '<h3>Original CEQA capture & ingestion</h3><p role="alert">' +
      esc(error.message) + '</p>';
  }
}


// Original SMARTS snapshot ledger, not current bid readiness or an identity join.
async function renderRetainedSmartsHistory(box) {
  if (!box || !box.isConnected || activePage !== 'Sources & Collection') return;
  box.innerHTML = '<h3>Original SMARTS snapshot change review</h3>' +
    '<p role="status">Checking private evidence history…</p>';
  let status;
  try {
    status = await api('/api/source-smarts-status');
  } catch (error) {
    if (box.isConnected) box.innerHTML = '<h3>Original SMARTS snapshot change review</h3>' +
      '<p role="alert">' + esc(error.message) + '</p>';
    return;
  }
  if (!box.isConnected || activePage !== 'Sources & Collection') return;
  if (!status.available || !status.csv_snapshot_history_configured) {
    box.innerHTML = '<h3>Original SMARTS snapshot change review</h3>' +
      '<p>No private SMARTS snapshot history is connected. Use ' +
      '<code>--operator-smarts-history</code> to inspect existing retained CSV evidence. ' +
      'This does not indicate that no jurisdictional changes exist.</p>';
    return;
  }
  box.innerHTML = '<h3>Original SMARTS snapshot change review</h3>' +
    '<p>Verified private snapshot history: ' + esc(status.csv_snapshots) +
    ' captures and ' + esc(status.csv_change_candidates) +
    ' candidate changes. Neither a source event nor a parcel candidate is a verified ' +
    'project association; no remote collection or commercial action is performed here.</p>' +
    '<form id="source-smarts-filters" class="source-toolbar">' +
    '<label>County <select name="county"><option value="">Both</option>' +
    '<option>San Bernardino</option><option>Riverside</option></select></label>' +
    '<button type="submit">Inspect history</button></form>' +
    '<div id="source-smarts-change-results" aria-live="polite"></div>';
  const form = box.querySelector('#source-smarts-filters');
  const results = box.querySelector('#source-smarts-change-results');
  let offset = 0, serial = 0;
  async function load() {
    const request = ++serial, pageOffset = offset;
    results.textContent = 'Inspecting verified SMARTS change history…';
    try {
      const page = await api('/api/source-smarts-changes?' + new URLSearchParams({
        county: form.elements.county.value, limit: '10', offset: String(offset)
      }));
      if (!box.isConnected || activePage !== 'Sources & Collection' ||
          request !== serial || pageOffset !== offset) return;
      if (!page.available) {
        results.textContent = 'The private SMARTS evidence history is unavailable.';
        return;
      }
      const events = page.items || [];
      results.innerHTML = '<p>' + esc(page.total) + ' retained change observations; ' +
        'offset ' + esc(page.offset) + '. “Missing from new” is not proof of deletion.</p>' +
        table(['Source', 'County', 'Event', 'Capture', 'Exact review'], events.map((item, i) => [
          esc(item.source_key), esc(item.county), esc(item.outcome),
          esc(item.captured_at),
          '<button data-smarts-parcel="' + i + '">Parcel candidates</button>'
        ])) +
        '<div class="source-toolbar"><button id="source-smarts-prev"' +
        (offset ? '' : ' disabled') + '>Previous</button>' +
        '<button id="source-smarts-next"' + (page.has_more ? '' : ' disabled') +
        '>Next</button>' +
        '<button id="source-smarts-export">Export reviewed page JSON</button></div>';
      results.querySelector('#source-smarts-prev').onclick = () => {
        offset = Math.max(0, offset - 10);
        perform(load);
      };
      results.querySelector('#source-smarts-next').onclick = () => {
        offset += 10;
        perform(load);
      };
      results.querySelector('#source-smarts-export').onclick = () =>
        download('original-smarts-changes.json', page);
      results.querySelectorAll('[data-smarts-parcel]').forEach(button => {
        button.onclick = () => perform(async () => {
          const item = events[Number(button.dataset.smartsParcel)];
          const details = await api('/api/source-smarts-parcel-candidates?' +
            new URLSearchParams({
              snapshot_id: String(item.snapshot_id), source_key: item.source_key
            }));
          if (!box.isConnected || activePage !== 'Sources & Collection') return;
          modal('Original SMARTS parcel evidence',
            '<p>Candidate-only matching on a retained exact source event. ' +
            'No parcel identity, construction activity, investigation association ' +
            'or bid authority is established.</p><pre>' +
            esc(JSON.stringify(details, null, 2)) + '</pre>');
        });
      });
    } catch (error) {
      if (results.isConnected && request === serial) results.innerHTML =
        '<p role="alert">' + esc(error.message) + '</p>';
    }
  }
  form.onsubmit = event => {
    event.preventDefault();
    offset = 0;
    perform(load);
  };
  await load();
}

// Original source-scoped investigation projections. Keys here are NOT native verified identities.
async function renderRetainedHistory(box) {
  if (!box || !box.isConnected || activePage !== 'Sources & Collection') return;
  box.innerHTML = '<h3>Historical source intelligence</h3>' +
    '<p>Inspect bounded original entity keys, dated source milestones, and geocoded ' +
    'source coverage. These are retained source claims, not canonical investigation ' +
    'membership or live construction evidence.</p>' +
    '<form id="retained-history-filters" class="source-toolbar">' +
    '<label>Family <select name="kind"><option value="all">All</option>' +
    '<option value="ceqa">CEQA</option><option value="permit">Permit</option></select></label>' +
    '<label>County <select name="county"><option value="">Both counties</option>' +
    '<option>San Bernardino</option><option>Riverside</option></select></label>' +
    '<label>Source search <input name="q" maxlength="200"></label>' +
    '<button type="button" data-history-mode="entities">Entity index</button>' +
    '<button type="button" data-history-mode="timeline">Dated events</button>' +
    '<button type="button" data-history-mode="footprint">Geo coverage</button></form>' +
    '<div id="retained-history-results" aria-live="polite"></div>';
  const form = box.querySelector('#retained-history-filters');
  const view = box.querySelector('#retained-history-results');
  let requestSerial = 0;
  async function inspectRecord(record) {
    const detail = await api('/api/candidate-preview?' + new URLSearchParams({
      kind: record.record_kind, record_id: record.record_id
    }));
    if (!box.isConnected || activePage !== 'Sources & Collection') return;
    modal('Original exact source observation',
      '<p>Preserved source details only; no inferred project identity.</p><pre>' +
      esc(JSON.stringify(detail, null, 2)) + '</pre>');
  }
  async function load(mode) {
    const serial = ++requestSerial;
    const params = new URLSearchParams({
      kind: form.elements.kind.value, county: form.elements.county.value
    });
    if (mode !== 'entities') params.set('q', form.elements.q.value);
    const routes = {entities: '/api/source-entity-index',
      timeline: '/api/source-timeline', footprint: '/api/source-footprint'};
    view.textContent = 'Inspecting retained original source data…';
    try {
      const result = await api(routes[mode] + '?' + params);
      if (serial !== requestSerial || !box.isConnected ||
          activePage !== 'Sources & Collection') return;
      if (!result.available) {
        view.textContent = 'Original operator database is not connected.';
        return;
      }
      const items = mode === 'entities' ? result.entries || [] :
        mode === 'timeline' ? result.events || [] : result.points || [];
      const headers = mode === 'entities' ?
        ['Exact source key', 'Claimed names', 'Claimed roles', 'Records', 'Investigation'] :
        mode === 'timeline' ?
          ['Recorded date', 'Source event', 'Source', 'Conflict', 'Evidence'] :
          ['Source record', 'County', 'Coordinates', 'Evidence'];
      const rows = items.slice(0, 100).map((item, i) => {
        if (mode === 'entities') return [
          esc(item.entity_key), esc((item.source_claimed_names || []).join(', ')),
          esc((item.source_claimed_roles || []).join(', ')),
          esc(item.matching_records_in_scan),
          '<button data-historical-entity="' + i + '">Inspect exact-key records</button>'
        ];
        if (mode === 'timeline') return [
          esc(item.recorded_date), esc(item.event_kind), esc(item.title),
          item.source_date_order_conflict ? 'Conflicting dates' : '—',
          '<button data-historical-record="' + i + '">Evidence</button>'
        ];
        return [
          esc(item.title), esc(item.county),
          esc(item.point?.latitude) + ', ' + esc(item.point?.longitude),
          '<button data-historical-record="' + i + '">Evidence</button>'
        ];
      });
      const total = mode === 'entities' ? result.distinct_keys_in_scan :
        mode === 'timeline' ? result.milestones_in_scan : result.mapped_in_scan;
      view.innerHTML = '<p>' + esc(total) + ' original ' +
        esc(mode === 'entities' ? 'keys' : mode === 'timeline' ? 'milestones' : 'mapped observations') +
        ' found in a bounded scan; showing ' + esc(Math.min(items.length, 100)) +
        '. Source scan truncated: ' + esc(Boolean(result.source_scan_truncated || result.truncated)) +
        '; result list truncated: ' + esc(Boolean(result.result_truncated ||
          result.event_result_truncated || items.length > 100)) +
        '. An exact location does not prove a current active project.</p>' +
        table(headers, rows) +
        '<button id="retained-history-export">Export original projection JSON</button>';
      view.querySelector('#retained-history-export').onclick = () =>
        download('original-source-' + mode + '.json', result);
      view.querySelectorAll('[data-historical-record]').forEach(button => {
        button.onclick = () => perform(() =>
          inspectRecord(items[Number(button.dataset.historicalRecord)]));
      });
      view.querySelectorAll('[data-historical-entity]').forEach(button => {
        button.onclick = () => perform(async () => {
          const entity = items[Number(button.dataset.historicalEntity)];
          const detail = await api('/api/source-entity-neighborhood?' +
            new URLSearchParams({kind: form.elements.kind.value,
              county: form.elements.county.value, entity_key: entity.entity_key}));
          if (!box.isConnected || activePage !== 'Sources & Collection') return;
          modal('Original source entity co-occurrences',
            '<p>Matching a retained source key does not verify common ownership, ' +
            'identity or active construction.</p><pre>' +
            esc(JSON.stringify(detail, null, 2)) + '</pre>');
        });
      });
    } catch (error) {
      if (serial === requestSerial && view.isConnected) view.innerHTML =
        '<p role="alert">' + esc(error.message) + '</p>';
    }
  }
  form.querySelectorAll('[data-history-mode]').forEach(button => {
    button.onclick = () => perform(() => load(button.dataset.historyMode));
  });
}

// A separate historical commercial read model, never a substitute for native bid authority.
async function renderLegacyCommercial(box, category) {
  if (!box.isConnected || activePage !== category) return;
  const root = document.createElement('section');
  root.className = 'retained-source-inspection';
  root.innerHTML = '<h3>Preserved workflow / outcome records</h3><p role="status">Inspecting local records…</p>';
  box.append(root);
  try {
    const [summary, page] = await Promise.all([
      api('/api/workflow-summary'),
      api(category === 'Bid Studio' ? '/api/workflows?limit=25&offset=0' :
        '/api/results?limit=25&offset=0')
    ]);
    if (!root.isConnected || activePage !== category) return;
    if (!summary.available || !page.available) {
      root.innerHTML = '<h3>Preserved workflow / outcome records</h3>' +
        '<p>Not connected. Configure the existing operator source database to inspect ' +
        'the historical governed records without modifying them.</p>';
      return;
    }
    const records = category === 'Bid Studio' ? page.leads || [] : page.results || [];
    root.innerHTML = '<h3>Preserved workflow / outcome records</h3>' +
      '<p>Legacy records are displayed separately from current native bids/royalties. ' +
      'They are not independently verified current jobs, payments, or permission to send. ' +
      'Persisted workflows: ' + esc(summary.total) + '; displayed records: ' +
      esc(records.length) + ' of ' + esc(page.total) +
      (page.has_more ? ' (more exist; this view is bounded to 25)' : '') + '.</p>' +
      table(['Retained identity', 'Status / evidence', 'Inspection'],
        records.map((r, i) => [
          esc(r.workflow_id || r.ledger_id || r.candidate_key || 'Retained outcome'),
          esc(r.status || r.current_status || r.summary || 'Stored historical fact'),
          '<button data-original-record="' + i + '">Inspect history</button>'
        ])) +
      '<p>' + esc((page.limitations || summary.limitations || []).join(' ')) + '</p>' +
      '<button id="legacy-record-export">Export displayed retained JSON</button>';
    root.querySelector('#legacy-record-export').onclick = () =>
      download(category === 'Bid Studio' ? 'original-workflows.json' :
        'original-results.json', page);
    root.querySelectorAll('[data-original-record]').forEach(button => {
      button.onclick = () => modal('Preserved authoritative record',
        '<p>Historical retained data, not a new commercial authorization.</p><pre>' +
        esc(JSON.stringify(records[Number(button.dataset.originalRecord)], null, 2)) +
        '</pre>');
    });
    if (category === 'Bid Studio') renderRetainedCommercialPreviewTools(root, records);
  } catch (error) {
    if (root.isConnected && activePage === category)
      root.innerHTML = '<h3>Preserved workflow / outcome records</h3>' +
        '<p role="alert">' + esc(error.message) + '</p>';
  }
}


// Manual previews use the original persisted review and authorization services.
// A preview is not a send action, a commercial approval, or an offer to a customer.
function renderRetainedCommercialPreviewTools(root, records) {
  const host = document.createElement('section');
  host.className = 'retained-commercial-previews';
  root.append(host);
  const workflow = records.find(r => typeof r.workflow_id === 'string');
  if (!workflow) {
    host.innerHTML = '<h3>Original governed commercial previews</h3>' +
      '<p>No retained workflow is available to review. Previews cannot be generated ' +
      'from an invented lead or unverified source observation.</p>';
    return;
  }
  host.innerHTML = '<h3>Original governed commercial previews</h3>' +
    '<p>Manually inspect exact persisted, reviewed lead state. No outreach is sent, ' +
    'no pricing is approved, no customer-facing bid is authorized, and no draft is ' +
    'submitted. All previews are temporary until explicitly exported.</p>' +
    '<div class="source-toolbar">' +
    field('original-workflow', 'Exact preserved workflow ID', workflow.workflow_id, 'text', true) +
    options('original-status', ['ready', 'active'], 'ready', 'Current expected workflow status') +
    '</div>' +
    '<h3>Outreach preview · never sends</h3>' +
    '<form id="original-outreach-form" class="form-grid">' +
    options('channel', ['email', 'phone', 'procurement_portal', 'web_form', 'other'],
      'email', 'Contact channel') +
    field('destination', 'Exact reviewed contact destination', '', 'text', true) +
    field('business_role', 'Contact business role', '', 'text', true) +
    field('source_name', 'Contact evidence source', '', 'text', true) +
    field('source_reference', 'Evidence reference or official URL', '', 'text', true) +
    field('contact_review_basis', 'Reason this contact was reviewed', '', 'textarea', true) +
    field('subject', 'Subject', '', 'text', true) +
    field('body', 'Draft message', '', 'textarea', true) +
    '<button type="submit">Preview unsent outreach</button></form>' +
    '<h3>Prospect-requested bid · evidence first</h3>' +
    '<form id="original-request-form" class="form-grid">' +
    options('request_channel', ['email', 'phone', 'procurement_portal',
      'web_form', 'meeting', 'other'], 'email', 'Request channel') +
    field('requester_business_name', 'Requesting business', '', 'text', true) +
    field('requester_business_role', 'Requester role', '', 'text', true) +
    field('request_source_name', 'Original request evidence source', '', 'text', true) +
    field('request_source_reference', 'Exact request evidence reference', '', 'text', true) +
    field('request_review_basis', 'Basis for confirming an explicit bid request', '',
      'textarea', true) +
    field('request_observed_at', 'Observed ISO time including timezone', '', 'text', true) +
    field('request_text', 'Actual request text', '', 'textarea', true) +
    field('scope_summary', 'Requested security scope', '', 'textarea', true) +
    '<button type="submit">Validate requested-bid evidence</button></form>' +
    '<form id="original-pricing-form" class="form-grid" hidden>' +
    '<h3>Internal pricing · manual exact currency amounts</h3>' +
    '<p>Requires the validated bid-request evidence above; each line has a human-entered ' +
    'amount in dollars and cents, not an automatically inferred price.</p>' +
    '<div id="original-price-lines"></div>' +
    '<button type="button" id="original-price-add">Add pricing line</button>' +
    field('assumptions', 'Assumptions (one per line)', '', 'textarea') +
    field('exclusions', 'Exclusions (one per line)', '', 'textarea') +
    field('validity_note', 'Terms validity note', '', 'textarea', true) +
    '<button type="submit">Preview unapproved pricing</button></form>' +
    '<form id="original-proposal-form" class="form-grid" hidden>' +
    '<h3>Internal proposal draft · never submits</h3>' +
    field('proposal_title', 'Proposal title', '', 'text', true) +
    field('cover_note', 'Internal cover note', '', 'textarea', true) +
    field('additional_terms', 'Additional terms (one per line)', '', 'textarea') +
    '<button type="submit">Draft unapproved proposal</button></form>';
  const common = () => ({
    workflow_id: host.querySelector('[name="original-workflow"]').value.trim(),
    expected_current_status: host.querySelector('[name="original-status"]').value
  });
  const outreachForm = host.querySelector('#original-outreach-form');
  const requestForm = host.querySelector('#original-request-form');
  const priceForm = host.querySelector('#original-pricing-form');
  const proposalForm = host.querySelector('#original-proposal-form');
  const priceLines = host.querySelector('#original-price-lines');
  let requestEvidence = null, pricingEvidence = null;

  function showResult(operation, result) {
    modal('Original ' + operation + ' · reviewed preview',
      '<p>This preview grants no sending, pricing approval or submission authority. ' +
      'It is based on the persisted original workflow, not an unverified site claim.</p>' +
      '<button id="original-preview-export">Export exact preview JSON</button><pre>' +
      esc(JSON.stringify(result, null, 2)) + '</pre>');
    document.querySelector('#original-preview-export').onclick = () =>
      download('original-' + operation + '-preview.json', result);
  }
  function bindPreview(form, operation, prepare, onSuccess = () => {}) {
    form.onsubmit = event => {
      event.preventDefault();
      const button = form.querySelector('button[type="submit"]');
      if (button) button.disabled = true;
      perform(async () => {
        try {
          const result = await api('/api/source-commercial-preview', {
            operation, data: prepare(Object.fromEntries(new FormData(form)))
          });
          if (!root.isConnected || activePage !== 'Bid Studio') return;
          onSuccess(result.preview);
          showResult(operation, result);
        } finally {
          if (button?.isConnected) button.disabled = false;
        }
      });
    };
  }
  const lines = text => text.split('\n').map(s => s.trim()).filter(Boolean);
  function addPriceLine() {
    const row = document.createElement('div');
    row.className = 'original-price-line form-grid';
    row.innerHTML = field('line_key', 'Line key', '', 'text', true) +
      field('description', 'Line description', '', 'text', true) +
      field('pricing_basis', 'Manual pricing basis', '', 'text', true) +
      field('amount', 'Manual USD amount (e.g., 125.50)', '', 'text', true) +
      '<button type="button" data-remove-line>Remove line</button>';
    priceLines.append(row);
    row.querySelector('[data-remove-line]').onclick = () => {
      if (priceLines.children.length > 1) row.remove();
    };
  }
  host.querySelector('#original-price-add').onclick = addPriceLine;
  addPriceLine();
  const resetChain = () => {
    requestEvidence = null;
    pricingEvidence = null;
    priceForm.hidden = true;
    proposalForm.hidden = true;
  };
  host.querySelector('[name="original-workflow"]').oninput = resetChain;
  host.querySelector('[name="original-status"]').onchange = resetChain;
  bindPreview(outreachForm, 'outreach', fields => ({...common(), ...fields}));
  bindPreview(requestForm, 'bid_request', fields => ({...common(), ...fields}),
    evidence => {
      requestEvidence = evidence;
      pricingEvidence = null;
      priceForm.hidden = false;
      proposalForm.hidden = true;
    });
  bindPreview(priceForm, 'pricing', fields => {
    if (!requestEvidence) throw Error('Validate a current exact bid request first.');
    return {
      request_evidence: requestEvidence, currency_code: 'USD',
      line_items: Array.from(priceLines.querySelectorAll('.original-price-line'))
        .map(row => Object.fromEntries(
          Array.from(row.querySelectorAll('input[name]'))
            .map(input => [input.name, input.value])
        )),
      assumptions: lines(fields.assumptions),
      exclusions: lines(fields.exclusions),
      validity_note: fields.validity_note
    };
  }, evidence => {
    pricingEvidence = evidence;
    proposalForm.hidden = false;
  });
  bindPreview(proposalForm, 'proposal', fields => {
    if (!requestEvidence || !pricingEvidence) {
      throw Error('Validate current bid request and pricing evidence first.');
    }
    return {
      request_evidence: requestEvidence,
      pricing_preview: pricingEvidence,
      proposal_title: fields.proposal_title,
      cover_note: fields.cover_note,
      additional_terms: lines(fields.additional_terms)
    };
  });
}
