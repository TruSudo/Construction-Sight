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
    table(['Source', 'Family', 'County', 'Watch status', 'Changed'],
      (watches.items || []).slice(0, 100).map(w => [
        esc(w.title || w.record_id), esc(w.record_kind), esc(w.county),
        esc(w.status), w.change_pending ? 'Retained change pending review' : '—'
      ])) +
    '<p>' + esc(watches.total || 0) + ' active source watches; ' +
    'source monitoring: ' + (watches.source_monitoring_enabled ? 'enabled' : 'not enabled') +
    '. Existing archive/add actions remain in the preserved operator system.</p>' +
    '<h3>Source observation review queue</h3>' +
    '<p>Exact retained CEQA/permit observations. Review does not merge investigations, authorize bids or send outreach.</p>' +
    '<form id="retained-source-filters" class="source-toolbar">' +
    '<label>Family <select name="kind"><option value="all">All</option><option value="ceqa">CEQA</option><option value="permit">Permit</option></select></label>' +
    '<label>County <select name="county"><option value="">Both counties</option><option>San Bernardino</option><option>Riverside</option></select></label>' +
    '<label>Search <input name="q" maxlength="200" aria-label="Search retained source records"></label>' +
    '<button type="submit">Inspect</button></form>' +
    '<div id="retained-source-queue" aria-live="polite"></div>';
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
            '<button data-parcel-review="' + i + '">Parcel candidates</button>'
          ])) +
        '<div class="source-toolbar"><button id="retained-source-previous"' +
        (offset === 0 ? ' disabled' : '') + '>Previous</button>' +
        '<button id="retained-source-next"' +
        (page.has_more ? '' : ' disabled') + '>Next</button></div>';
      queue.querySelector('#retained-source-previous').onclick =
        () => { offset = Math.max(0, offset - 10); perform(loadPage); };
      queue.querySelector('#retained-source-next').onclick =
        () => { offset += 10; perform(loadPage); };
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
  } catch (error) {
    if (root.isConnected && activePage === category)
      root.innerHTML = '<h3>Preserved workflow / outcome records</h3>' +
        '<p role="alert">' + esc(error.message) + '</p>';
  }
}
