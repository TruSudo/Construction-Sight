'use strict';

async function openRetainedSourceNotice(notice) {
  const openingTicket = modalTicket;
  const selection = {kind: notice.record_kind, record_id: notice.record_id};
  const [source, reconciliation] = await Promise.all([
    api('/api/candidate-preview?' + new URLSearchParams(selection)),
    api('/api/source-reconciliation?' + new URLSearchParams(selection))
  ]);
  if (openingTicket !== modalTicket) return;
  modal('Watched retained source change',
    '<p>This is a retained source change requiring review. It does not establish ' +
    'current construction, verified project identity or commercial readiness. ' +
    'Reading this notice does not approve a source revision.</p>' +
    '<button id="source-notice-sources">Review in Sources & Collection</button>' +
    (reconciliation.canonical_investigation_id ?
      '<button id="source-notice-dossier">Open current shared investigation</button>' : '') +
    '<h3>Exact retained source</h3><pre>' + esc(JSON.stringify(source, null, 2)) +
    '</pre><h3>Current shared-engine comparison</h3><pre>' +
    esc(JSON.stringify(reconciliation, null, 2)) + '</pre>');
  $('source-notice-sources').onclick = () => {
    $('action-dialog').close();
    modalTicket++;
    perform(() => openWorkspace('Sources & Collection'));
  };
  const dossier = $('source-notice-dossier');
  if (dossier) dossier.onclick = () => perform(() =>
    openInvestigationDossier(reconciliation.canonical_investigation_id));
}

async function reviewRetainedParcelInEngine(parcelId) {
  const state = await api('/api/source-parcel-reconciliation?' +
    new URLSearchParams({parcel_record_id: parcelId}));
  const canRetain = state.replay_eligible || state.revision_replay_eligible;
  const ticket = modal('Original parcel · exact shared investigation review',
    '<p>This is an unverified retained parcel observation. A matching APN or ' +
    'centroid does not establish a construction project, site ownership, parcel ' +
    'boundary or commercial authority. An approved handoff uses the existing ' +
    'audited investigation worker; no network collection is started.</p>' +
    '<pre>' + esc(JSON.stringify(state,null,2)) + '</pre>' +
    (canRetain ? '<label>Original parcel evidence review reason ' +
      '<textarea id="parcel-replay-reason" rows="3" maxlength="2000" required></textarea>' +
      '</label><label><input type="checkbox" id="parcel-replay-confirm">' +
      ' I reviewed this exact retained parcel source and current shared ' +
      'evidence.</label><button id="parcel-replay-queue">Queue exact reviewed ' +
      (state.revision_replay_eligible ? 'revision' : 'observation') + '</button>' :
      '<p>No missing or current revised evidence can be queued. No action taken.</p>'));
  const queue = document.querySelector('#parcel-replay-queue');
  if (!queue) return;
  queue.onclick = () => perform(async () => {
    if (ticket !== modalTicket || !$('action-dialog').open) return;
    const reason = document.querySelector('#parcel-replay-reason').value.trim();
    if (reason.length < 10 || !document.querySelector('#parcel-replay-confirm').checked)
      throw Error('Review this exact parcel, enter at least ten characters and confirm.');
    queue.disabled = true;
    try {
      const receipt = await api('/api/source-parcel-reconciliation-queue', {
        parcel_record_id: parcelId,
        expected_source_sha256: state.original_source.source_sha256,
        expected_native_evidence_id: state.native_evidence_id,
        action: state.revision_replay_eligible ? 'retain_revision' : 'retain_missing',
        caller_confirmation: true, review_reason: reason
      });
      modal('Exact original parcel queued for common investigation worker',
        '<p>The existing worker must still process this immutable audited source ' +
        'observation. No parcel-to-project relationship, contact or bid authority ' +
        'has been granted.</p><button id="parcel-replay-audit">Inspect approval ' +
        'and worker job</button><pre>' +
        esc(JSON.stringify(receipt,null,2)) + '</pre>');
      document.querySelector('#parcel-replay-audit').onclick = () => perform(async () => {
        const audit = await api('/api/source-reconciliation-audit?' +
          new URLSearchParams({job: receipt.job_id}));
        modal('Original parcel approval and worker audit',
          '<pre>'+esc(JSON.stringify(audit,null,2))+'</pre>');
      });
    } finally {if (queue.isConnected) queue.disabled = false;}
  });
}

// Retained parcel/GIS source profiles are registered evidence, not live permits,
// surveyed parcel boundaries or authorized ArcGIS acquisition.
async function renderParcelSourceReadiness(box) {
  if (!box.isConnected || activePage !== 'Sources & Collection') return;
  const root = document.createElement('section');
  root.className = 'feature-card';
  root.dataset.parcelSourceReadiness = 'true';
  root.innerHTML = '<h3>Parcel source verification & mapping</h3>' +
    '<p role="status">Reading existing county source evidence locally…</p>';
  box.append(root);
  try {
    const data = await api('/api/parcel-source-readiness');
    if (!root.isConnected || activePage !== 'Sources & Collection') return;
    const sources = data.sources || [];
    root.innerHTML = '<h3>Parcel source verification & mapping</h3>' +
      '<p>Existing registered parcel/GIS sources, official retained evidence and ' +
      'expected field mappings. These are historical observations, not live data ' +
      'or permission to collect; no parcel or project has been verified. ' +
      'No requests, imports, identity merges or commercial actions run here. ' +
      '<button data-parcel-source-export>Export original parcel readiness evidence</button></p>' +
      table(['Registered source','County','Access boundary','Coverage','Expected schema','Inspect'],
        sources.map((r,i) => [
          esc(r.source_name), esc(r.county), esc(r.access_boundary),
          esc(r.coverage_status),
          esc(data.schemas[r.source_key]?.status || 'Unavailable'),
          '<button data-parcel-source-inspect="'+i+'">Review existing source evidence</button>' +
          (data.profiles.some(p => p.source_key === r.source_key) ?
            ' <button data-parcel-sample-preview="'+i+'">Preview sample rows</button>' :
            ' Preview requires a verified county source')
        ])) +
      '<p>Original countywide coverage and ArcGIS acquisition readiness remain ' +
      'subject to recorded evidence gaps. A prepared schema is not an imported ' +
      'parcel, verified address, complete county coverage or authorized probe.</p>' +
      '<form id="original-parcel-exact-review" class="form-grid">' +
      '<h3>Review an existing retained parcel by exact record ID</h3>' +
      '<p>Uses the original operator database when configured. This is not a ' +
      'parcel search, live GIS request, construction-site verification or ' +
      'commercial lead qualification.</p>' +
      '<label>Original parcel record ID <input name="parcel_record_id" ' +
      'maxlength="255" required autocomplete="off"></label>' +
      '<button type="submit">Compare with current investigation evidence</button>' +
      '</form>' +
      '<h3>Offline ArcGIS proof handoff to the shared investigation store</h3>' +
      '<div data-native-arcgis-proof role="status">Checking configured proof…</div>' +
      '<h3>Persisted original ArcGIS bounded-proof history</h3>' +
      '<div data-retained-parcel-proofs role="status">Checking explicitly configured ' +
      'original source database for validated retained proof bundles…</div>';
    root.querySelector('[data-parcel-source-export]').onclick = () =>
      download('parcel-source-readiness.json', data);
    const exactReview = root.querySelector('#original-parcel-exact-review');
    exactReview.onsubmit = event => {
      event.preventDefault();
      const parcelId = exactReview.elements.namedItem('parcel_record_id').value.trim();
      if (!parcelId) { showError(Error('Enter an exact original parcel record ID')); return; }
      const button = exactReview.querySelector('button[type="submit"]');
      button.disabled = true;
      perform(() => reviewRetainedParcelInEngine(parcelId)).finally(() => {
        if (button.isConnected) button.disabled = false;
      });
    };
    const nativeProofBox = root.querySelector('[data-native-arcgis-proof]');
    try {
      const [review, inventory] = await Promise.all([
        api('/api/parcel-arcgis-proof'), api('/api/native-parcel-proofs')
      ]);
      if (!root.isConnected || activePage !== 'Sources & Collection') return;
      const retained = inventory.available ? inventory.total + ' validated bundle(s)' :
        'No existing native investigation store';
      nativeProofBox.innerHTML =
        '<p>Native retained ArcGIS proofs: '+esc(retained)+
        '. Offline evidence audit only: no parcel import, project match, '+
        'live GIS acquisition, map point or commercial approval.</p>'+
        (review.configured ?
          '<p>Verified bundle: '+esc(review.source_key)+' · '+esc(review.county)+
          ' · '+esc(review.assessment_status)+' · SHA-256 <code>'+
          esc(review.bundle_sha256)+'</code></p>'+
          '<button data-native-proof-review>Inspect and retain exact verified proof</button>' :
          '<p>No offline proof configured. Launch with an existing '+
          '<code>--operator-arcgis-proof-bundle</code> JSON file to review it.</p>');
      const inspect = nativeProofBox.querySelector('[data-native-proof-review]');
      if (inspect) inspect.onclick = () => {
        const ticket = modal('Original ArcGIS bounded proof · offline review',
          '<p>The original verifier recomputed this proof. Retention writes its '+
          'evidence chain to the existing private investigation store, not a '+
          'parcel/project identity. No network, outreach, bids or bulk acquisition.</p>'+
          '<pre>'+esc(JSON.stringify(review.verification,null,2))+'</pre>'+
          '<label>Reason for retaining this exact proof '+
          '<textarea id="native-proof-reason" maxlength="2000" rows="3"></textarea></label>'+
          '<label><input type="checkbox" id="native-proof-confirm"> '+
          'I reviewed this SHA-256-bound proof and authorize local retention only.</label>'+
          '<button id="native-proof-commit">Retain verified proof</button>');
        const commit = document.querySelector('#native-proof-commit');
        commit.onclick = () => perform(async () => {
          if (ticket !== modalTicket || !$('action-dialog').open) return;
          const reason = document.querySelector('#native-proof-reason').value.trim();
          if (reason.length < 10 ||
              !document.querySelector('#native-proof-confirm').checked)
            throw Error('Enter at least ten characters and confirm offline retention.');
          commit.disabled = true;
          try {
            const receipt = await api('/api/parcel-arcgis-proof-persist', {
              expected_bundle_id:review.bundle_id,
              expected_bundle_sha256:review.bundle_sha256,
              review_reason:reason, caller_confirmation:true
            });
            if (ticket !== modalTicket || !$('action-dialog').open) return;
            modal('Verified ArcGIS proof retained locally',
              '<p>The original proof chain was verified in the native store. '+
              'Parcel import, project association and commercial readiness '+
              'still require independent evidence and review.</p>'+
              '<pre>'+esc(JSON.stringify(receipt,null,2))+'</pre>');
          } finally {if (commit.isConnected) commit.disabled = false;}
        });
      };
    } catch (error) {
      if (nativeProofBox.isConnected && activePage === 'Sources & Collection')
        nativeProofBox.innerHTML = '<p role="alert">Offline ArcGIS proof review '+
          'unavailable: '+esc(error.message)+'</p>';
    }
    const proofBox = root.querySelector('[data-retained-parcel-proofs]');
    try {
      const proofState = await api('/api/source-parcel-proofs');
      if (!root.isConnected || activePage !== 'Sources & Collection') return;
      if (!proofState.available) {
        proofBox.textContent = 'Original source database not configured. Supply an ' +
          'existing --operator-database at launch; no proof inventory was assumed.';
      } else {
        const bundles = proofState.bundles || [];
        proofBox.innerHTML = '<p>' + esc(proofState.total) +
          ' original persisted bundles were verified against their complete source ' +
          'chain; no source requests or parcel imports run here. ' +
          '<button data-retained-proofs-export>Export validated proof inventory</button></p>' +
          table(['County','Source','Bounded proof status','Proof'],
            bundles.map((item,i) => [
              esc(item.county), esc(item.source_key), esc(item.assessment?.status),
              '<button data-original-parcel-proof="'+i+'">Inspect original bundle</button>'
            ]));
        proofBox.querySelector('[data-retained-proofs-export]').onclick = () =>
          download('original-arcgis-proof-inventory.json', proofState);
        proofBox.querySelectorAll('[data-original-parcel-proof]').forEach(button => {
          button.onclick = () => {
            const item = bundles[Number(button.dataset.originalParcelProof)];
            modal('Validated retained ArcGIS proof · '+item.source_key,
              '<p>Original stored, integrity-checked bounded proof, not a parcel ' +
              'import or construction-site verification. No bulk collection, ' +
              'project relationship, map point or commercial action is authorized.</p>' +
              '<button id="export-original-parcel-proof">Export original proof JSON</button>' +
              '<pre>'+esc(JSON.stringify(item,null,2))+'</pre>');
            document.querySelector('#export-original-parcel-proof').onclick = () =>
              download('original-arcgis-proof.json',item);
          };
        });
      }
    } catch(error) {
      if (proofBox.isConnected && activePage === 'Sources & Collection') {
        proofBox.innerHTML = '<p role="alert">Original ArcGIS proof verification ' +
          'unavailable: '+esc(error.message)+'</p>';
      }
    }
    root.querySelectorAll('[data-parcel-sample-preview]').forEach(button => {
      button.onclick = () => {
        const source = sources[Number(button.dataset.parcelSamplePreview)];
        modal('Original parcel row preview · '+source.source_name,
          '<p>Paste 1–20 JSON objects keyed by fields in the registered expected ' +
          'schema. This is a manual, unverified sample only. The original row ' +
          'preview does not collect remote data, retain a parcel, verify an address, ' +
          'create an investigation or authorize outreach.</p>' +
          '<label>JSON array of source sample rows ' +
          '<textarea id="parcel-row-json" rows="7" ' +
          'placeholder=\'[{"ParcelNumber":"123-456-789"}]\'></textarea></label>' +
          '<button id="parcel-run-row-preview">Preview without saving</button>');
        document.querySelector('#parcel-run-row-preview').onclick = () => perform(async () => {
          const rows = JSON.parse(document.querySelector('#parcel-row-json').value);
          const result = await api('/api/parcel-source-row-preview', {
            source_key: source.source_key, rows
          });
          modal('Original parcel row preview result · '+source.source_name,
            '<p>Unretained manual sample. Even a usable row is not source-proof, ' +
            'an associated construction project or a mapped site.</p>' +
            '<button id="parcel-row-export">Export exact row preview</button>' +
            '<pre>'+esc(JSON.stringify(result,null,2))+'</pre>');
          document.querySelector('#parcel-row-export').onclick = () =>
            download('parcel-row-preview.json', result);
        });
      };
    });
    root.querySelectorAll('[data-parcel-source-inspect]').forEach(button => {
      button.onclick = () => {
        const r = sources[Number(button.dataset.parcelSourceInspect)];
        const profile = data.profiles.filter(x => x.source_key === r.source_key);
        const evidence = data.evidence.filter(x => x.source_key === r.source_key);
        const acquisition = data.acquisition_assessments.filter(x =>
          x.source_key === r.source_key);
        modal('Existing parcel/GIS evidence: '+r.source_name,
          '<p>Read-only original operator services. Historical field/schema ' +
          'observations are not current live verification, land title, permission ' +
          'to use licensed data, surveyed boundaries or construction evidence.</p>' +
          '<h3>Original expected-field schema preview</h3><pre>' +
          esc(JSON.stringify(data.schemas[r.source_key], null, 2)) + '</pre>' +
          '<h3>Evidence-bound source profile</h3><pre>' +
          esc(JSON.stringify(profile, null, 2)) + '</pre>' +
          '<h3>Retained official evidence</h3><pre>' +
          esc(JSON.stringify(evidence, null, 2)) + '</pre>' +
          '<h3>Bounded ArcGIS acquisition readiness (not execution)</h3><pre>' +
          esc(JSON.stringify(acquisition, null, 2)) + '</pre>');
      };
    });
  } catch (error) {
    if (root.isConnected && activePage === 'Sources & Collection') {
      root.innerHTML = '<h3>Parcel source verification & mapping</h3>' +
        '<p role="alert">'+esc(error.message)+'</p>';
    }
  }
}

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
    '. <button id="retained-registry-export">Export full returned registry JSON</button> ' +
    '<button id="retained-original-source-audit">Original offline source audit</button> ' +
    '<button id="retained-original-external-intelligence">' +
    'Original Shovels/Regrid capability audit</button></p>' +
    table(['Registered source', 'County', 'Verification', 'Last checked', 'Adapter', 'Attributed records'],
      entries.slice(0, 50).map((r, i) => [
        '<button data-registry-index="' + i + '">' + esc(r.source_name) + '</button>',
        esc(r.county),
        esc(r.verification_status),
        esc(r.latest_verification_checked_at || r.last_checked_date),
        esc(r.adapter_status),
        esc(r.attributed_records_in_scan)
      ])) +
    '<p>Original source attribution aliases: ' +
    (registry.source_aliases_configured ? esc(registry.source_alias_mapping_count) +
      ' retained mappings · applied: ' + (registry.source_aliases_applied ? 'yes' : 'no') +
      ' · artifact SHA-256: <code>' + esc(registry.source_alias_artifact_sha256) + '</code>' :
      'not configured') + '. Source-name attribution does not verify project identity or access authority.</p>' +
    '<p class="source-caution">' + esc((registry.limitations || []).join(' ')) + '</p>' +
    '<h3>Local source revisions</h3><p>' + esc(revision.meaning) +
    ' · Digest: <code>' + esc(revision.revision_identity) + '</code></p>' +
    table(['Family', 'Retained records', 'Last local update', 'Highest row'],
      familyRows.map(([name, r]) => [
        esc(name), esc(r.record_count), esc(r.latest_updated_at), esc(r.highest_row_id)
      ])) +
    '<h3>Source-specific watchlist</h3><p>Distinct from the commercial lead watchlist. ' +
    'Changes in retained source records can trigger existing watches; material changes appear in local Notifications. No external messages are sent.</p>' +
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
    '<div id="retained-ceqanet-export" aria-live="polite"></div>' +
    '<div id="retained-smarts-source-review" aria-live="polite"></div>' +
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
      '. Local change notices do not authorize contacts, bids or external delivery.</p>';
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
  root.querySelector('#retained-original-external-intelligence').onclick =
    () => perform(async () => {
      const report = await api('/api/source-external-intelligence');
      if (!root.isConnected || activePage !== 'Sources & Collection') return;
      modal('Original external source capability and gap evidence',
        '<p>Historical Shovels/Regrid reference research only. It does not ' +
        'claim current vendor access, subscription, data coverage or live ' +
        'permission, and does not create an ingestion task or commercial action.</p>' +
        '<h3>Original capability matrix</h3><pre>' +
        esc(JSON.stringify(report.original_capability_matrix,null,2))+'</pre>' +
        '<h3>Original capability-gap summary</h3><pre>' +
        esc(JSON.stringify(report.original_capability_gap_report,null,2))+'</pre>' +
        '<h3>Original research gaps and alignment roadmap</h3><pre>' +
        esc(JSON.stringify(report.original_research_gap_matrix,null,2))+'\n' +
        esc(JSON.stringify(report.original_alignment_report,null,2))+'\n' +
        esc(JSON.stringify(report.original_implementation_roadmap,null,2))+'</pre>' +
        '<button id="export-original-external-intelligence">' +
        'Export original capability evidence JSON</button>');
      document.querySelector('#export-original-external-intelligence').onclick =
        () => download('original-source-capability-gap-report.json',report);
    });
  root.querySelector('#retained-original-source-audit').onclick = () => perform(async () => {
    const audit = await api('/api/source-offline-audit');
    if (!audit.available) throw Error('Original source registry has not been configured');
    modal('Original source registry · offline verification evidence',
      '<p>Reuses the original source status and evidence services against the ' +
      'retained original registry. All HTTP checks are off. Previously reported ' +
      'source status is not new verification, commercial authorization or ' +
      'permission to access a portal.</p>' +
      '<p>Audited original source records: '+esc(audit.source_count)+'. ' +
      '<button id="export-original-source-audit">Export original audit JSON</button></p>' +
      '<h3>Original source and adapter status report</h3><pre>' +
      esc(JSON.stringify(audit.original_status_report,null,2))+'</pre>' +
      '<h3>Original source verification-evidence package</h3><pre>' +
      esc(JSON.stringify(audit.original_evidence_package,null,2))+'</pre>' +
      '<h3>Original manual source verification checklist</h3>' +
      '<p>Original offline checklist only. Query, results, detail, access barriers ' +
      'and terms require independent lawful operator observations. ' +
      'No verification is inferred from retained registry labels.</p><pre>' +
      esc(JSON.stringify(audit.original_manual_checklist,null,2))+'</pre>' +
      '<h3>Original source promotion dry-run</h3><pre>' +
      esc(JSON.stringify(audit.original_promotion_plan,null,2))+'</pre>' +
      '<h3>Original registry update dry-run</h3><pre>' +
      esc(JSON.stringify(audit.original_registry_update_plan,null,2))+'</pre>' +
      '<p>Both original plans are offline previews; no registry status or ' +
      'source authorization changes.</p>' +
      '<p><button id="export-original-source-plans">Export original planning JSON</button></p>' +
      '<p><button id="export-original-observation-templates">' +
      'Export blank original source observation templates</button> ' +
      'Templates are not completed observations or source promotion.</p>');
    document.querySelector('#export-original-source-audit').onclick =
      () => download('original-source-offline-audit.json',audit);
    document.querySelector('#export-original-source-plans').onclick =
      () => download('original-source-registry-plans.json', {
        source_count: audit.source_count,
        original_promotion_plan: audit.original_promotion_plan,
        original_registry_update_plan: audit.original_registry_update_plan,
        network_executed: false, source_promotion_authorized: false
      });
    document.querySelector('#export-original-observation-templates').onclick =
      () => download('original-source-observation-templates.json',
        audit.original_observation_templates);
  });
  root.querySelectorAll('[data-registry-index]').forEach(button => {
    button.onclick = () => {
      const entry = entries[Number(button.dataset.registryIndex)];
      modal('Registered source: ' + entry.source_name,
        '<p>Retained original source metadata only. No current reachability or ' +
        'access authority has been inferred.</p><pre>' +
        esc(JSON.stringify(entry, null, 2)) + '</pre>' +
        '<button id="review-exact-original-source-http">Review original manual ' +
        'HTTP readiness check</button> ' +
        '<button id="review-original-manual-checklist">Review original ' +
        'manual source checklist</button>');
      document.querySelector('#review-original-manual-checklist').onclick =
        () => perform(async () => {
          const reviewed = await api('/api/source-checklist-preview?' +
            new URLSearchParams({
              source_name: entry.source_name, public_url: entry.public_url
            }));
          const flags = [
            ['public_entry_observed', 'Public entry page'],
            ['query_behavior_observed', 'Search/query behavior'],
            ['result_list_observed', 'Result list'],
            ['detail_page_observed', 'Detail page'],
            ['access_barrier_observed', 'Access barrier present'],
            ['terms_review_observed', 'Terms reviewed']
          ];
          const ticket = modal('Exact original source · manual verification checklist',
            '<p>Operator-supplied observations only, not independent source ' +
            'verification. No network access, status changes or promotion. ' +
            'Use Unknown for anything not personally checked and provide ' +
            'evidence references for positive observations.</p>' +
            '<pre>'+esc(JSON.stringify(reviewed.original_observation_template,null,2))+'</pre>' +
            flags.map(([key, title]) =>
              '<label>'+esc(title)+' <select data-manual-source-flag="'+key+'">' +
              '<option value="">Unknown</option><option value="true">Yes</option>' +
              '<option value="false">No</option></select></label>').join('') +
            '<label>Evidence references (one per line) ' +
            '<textarea id="manual-source-refs" rows="3"></textarea></label>' +
            '<label>Observation notes ' +
            '<textarea id="manual-source-notes" maxlength="2000" rows="3"></textarea></label>' +
            '<label>Reason for this exact manual review ' +
            '<textarea id="manual-source-reason" maxlength="2000" rows="3"></textarea></label>' +
            '<label><input type="checkbox" id="manual-source-confirm">' +
            ' I confirm these observations represent my actual manual review.</label>' +
            '<button id="manual-source-run">Build original manual checklist</button>');
          document.querySelector('#manual-source-run').onclick = () =>
            perform(async () => {
              if (ticket !== modalTicket || !$('action-dialog').open) return;
              const reason = document.querySelector('#manual-source-reason').value.trim();
              if (reason.length < 10 ||
                  !document.querySelector('#manual-source-confirm').checked)
                throw Error('A review reason and explicit confirmation are required.');
              const observation = {
                source_key: reviewed.source_key, source_name: reviewed.source_name,
                notes: document.querySelector('#manual-source-notes').value.trim() || null,
                evidence_refs: document.querySelector('#manual-source-refs').value
                  .split('\n').map(value => value.trim()).filter(Boolean)
              };
              document.querySelectorAll('[data-manual-source-flag]').forEach(item => {
                observation[item.dataset.manualSourceFlag] =
                  item.value === '' ? null : item.value === 'true';
              });
              const reviewPayload = {
                source_name: reviewed.source_name, public_url: reviewed.public_url,
                expected_source_sha256: reviewed.expected_source_sha256,
                review_reason: reason, caller_confirmation: true, observation
              };
              const result = await api('/api/source-checklist-review',reviewPayload);
              const proposed = result.original_registry_update_plan;
              const applyTicket = modal('Original manual source checklist · reviewed result',
                '<p>Manual observations are not independent source verification. ' +
                'Reviewing this report has not changed source status or granted ' +
                'network, collection, or commercial authority.</p><pre>' +
                esc(JSON.stringify(result,null,2))+'</pre>' +
                '<button id="export-reviewed-original-checklist">Export reviewed checklist JSON</button> ' +
                '<button id="retain-reviewed-original-checklist">Retain original checklist evidence</button> ' +
                '<button id="export-reviewed-original-source-plans">Export original dry-run plans</button>' +
                (proposed.update_count === 1 ?
                  '<h3>Apply one reviewed registry status change</h3>' +
                  '<p>Changes only verification_status for this exact source. ' +
                  'A second authorization is required and the source is rechecked under ' +
                  'the database writer lock. The original source database must have ' +
                  'owner-only permissions. This does not authorize collecting data or ' +
                  'contacting anyone.</p><p>Proposed status: <strong>' +
                  esc(proposed.rows[0].proposed_verification_status) +
                  '</strong>. Approved plan: <code>'+esc(proposed.plan_digest)+'</code></p>' +
                  '<label>Reason for applying this exact source status ' +
                  '<textarea id="source-registry-apply-reason" maxlength="2000" rows="3"></textarea></label>' +
                  '<label><input type="checkbox" id="source-registry-apply-confirm">' +
                  ' I reviewed this exact plan, source and evidence and approve ' +
                  'the original registry status change.</label>' +
                  '<button id="source-registry-apply-run">Apply reviewed source status</button>' :
                  '<p>No original registry status change is proposed.</p>'));
              document.querySelector('#export-reviewed-original-checklist').onclick =
                () => download('original-manual-checklist-review.json', result);
              $('retain-reviewed-original-checklist').onclick = () => perform(async () => {
                if (applyTicket !== modalTicket || !$('action-dialog').open) return;
                const preview = await api(
                  '/api/source-checklist-retention-preview',reviewPayload
                );
                const retainTicket = modal('Original source · permanent evidence receipt',
                  '<p>Review an exact private create-only evidence snapshot. It ' +
                  'preserves the original manual checklist and dry-run plans; ' +
                  'manual observations never establish independent verification, ' +
                  'remote source permission, source promotion or commercial authority.</p>' +
                  '<pre>'+esc(JSON.stringify(preview,null,2))+'</pre>' +
                  (preview.may_request_approval ?
                    '<label>Specific reason for retaining this evidence ' +
                    '<textarea id="source-checklist-retain-reason" rows="3" maxlength="2000"></textarea></label>' +
                    '<label><input type="checkbox" id="source-checklist-retain-confirm"> ' +
                    'I approve permanent retention of this exact reviewed proof.</label>' +
                    '<button id="source-checklist-retain-apply">Retain reviewed proof</button>' :
                    '<p>This exact review is already retained or unavailable.</p>'));
                const action = $('source-checklist-retain-apply');
                if (!action) return;
                action.onclick = () => perform(async () => {
                  if (retainTicket !== modalTicket || !$('action-dialog').open) return;
                  const retainReason = $('source-checklist-retain-reason').value.trim();
                  if (retainReason.length < 10 || !$('source-checklist-retain-confirm').checked)
                    throw Error('Specific retention reason and confirmation required.');
                  action.disabled = true;
                  try {
                    const receipt = await api('/api/source-checklist-retention',{
                      ...reviewPayload,
                      expected_review_digest: preview.expected_review_digest,
                      retention_reason: retainReason,
                      retention_confirmation: true
                    });
                    modal('Original source · retained immutable checklist',
                      '<p>Reviewed checklist permanently retained in private source ' +
                      'evidence. Registry and source policy remain unchanged.</p>' +
                      '<pre>'+esc(JSON.stringify(receipt,null,2))+'</pre>' +
                      '<button id="export-source-checklist-retention-receipt">Export receipt</button>');
                    $('export-source-checklist-retention-receipt').onclick =
                      () => download('original-source-checklist-retention.json',receipt);
                  } finally { if (action.isConnected) action.disabled = false; }
                });
              });
              document.querySelector('#export-reviewed-original-source-plans').onclick =
                () => download('original-reviewed-source-plans.json', {
                  source_name: result.source_name,
                  reviewed_source_sha256: result.reviewed_source_sha256,
                  original_promotion_plan: result.original_promotion_plan,
                  original_registry_update_plan: result.original_registry_update_plan,
                  original_registry_mutated: false, source_promoted: false
                });
              const approveButton = document.querySelector('#source-registry-apply-run');
              if (approveButton) approveButton.onclick = () => perform(async () => {
                if (applyTicket !== modalTicket || !$('action-dialog').open) return;
                const applyReason = $('source-registry-apply-reason').value.trim();
                if (applyReason.length < 10 || !$('source-registry-apply-confirm').checked)
                  throw Error('Enter a reason and explicitly approve the exact registry change.');
                approveButton.disabled = true;
                try {
                  const applied = await api('/api/source-registry-reviewed-apply', {
                    source_name: reviewed.source_name,
                    public_url: reviewed.public_url,
                    expected_source_sha256: reviewed.expected_source_sha256,
                    review_reason: reason,
                    caller_confirmation: true,
                    observation,
                    expected_plan_digest: proposed.plan_digest,
                    apply_reason: applyReason,
                    apply_confirmation: true
                  });
                  modal('Original source registry · approved status receipt',
                    '<p>Only the approved source verification status was changed. ' +
                    'No source acquisition, outreach or commercial action was authorized.</p>' +
                    '<pre>'+esc(JSON.stringify(applied,null,2))+'</pre>' +
                    '<button id="export-applied-original-registry">Export authorization receipt</button>');
                  document.querySelector('#export-applied-original-registry').onclick =
                    () => download('original-source-registry-status-receipt.json', applied);
                  root.remove();
                  await renderRetainedSources(box);
                } finally {
                  if (approveButton.isConnected) approveButton.disabled = false;
                }
              });
            });
        });
      document.querySelector('#review-exact-original-source-http').onclick =
        () => perform(async () => {
          const reviewed = await api('/api/source-http-check-preview?' +
            new URLSearchParams({
              source_name: entry.source_name, public_url: entry.public_url
            }));
          const ticket = modal('Exact original source · authorized reachability review',
            '<p>Runs the ORIGINAL authorized source readiness service only after ' +
            'your explicit confirmation. One bounded public HEAD request with GET ' +
            'only after HTTP 405. No redirects, documents, credentials, source ' +
            'registry promotion, recurring collection or commercial authorization. ' +
            'Source permissions must have been independently reviewed.</p>' +
            '<pre>'+esc(JSON.stringify(reviewed,null,2))+'</pre>' +
            '<label>Reason this exact public check is authorized ' +
            '<textarea id="exact-http-check-reason" maxlength="2000" rows="3" ' +
            'required></textarea></label>' +
            '<label><input type="checkbox" id="exact-http-check-confirm">' +
            ' I reviewed this exact source and have authority to perform this ' +
            'bounded public request.</label>' +
            '<button id="exact-http-check-run" ' +
            (reviewed.can_execute_manual_check ? '' : 'disabled ') +
            '>Execute reviewed original reachability check</button>' +
            (!reviewed.can_execute_manual_check ?
              '<p role="alert">This source is blocked by the original governed ' +
              'URL allowlist or its retained source-blocked status. No HTTP ' +
              'request is permitted from this action.</p>' : ''));
          document.querySelector('#exact-http-check-run').onclick = () =>
            perform(async () => {
              if (ticket !== modalTicket || !$('action-dialog').open) return;
              const reason = document.querySelector(
                '#exact-http-check-reason').value.trim();
              if (reason.length < 10 ||
                  !document.querySelector('#exact-http-check-confirm').checked)
                throw Error('Confirm source access authority and give a review reason.');
              const action = document.querySelector('#exact-http-check-run');
              action.disabled = true;
              try {
                const result = await api('/api/source-http-check', {
                  source_name: reviewed.source_name,
                  public_url: reviewed.public_url,
                  expected_source_sha256: reviewed.expected_source_sha256,
                  review_reason: reason,
                  caller_confirmation: true
                });
                modal('Original bounded HTTP reachability evidence',
                  '<p>Original public-source evidence only. No source registry ' +
                  'status, permission or commercial authority has changed.</p>' +
                  '<button id="export-original-http-result">Export retained ' +
                  'source check report</button><pre>' +
                  esc(JSON.stringify(result,null,2)) + '</pre>');
                document.querySelector('#export-original-http-result').onclick =
                  () => download('original-source-http-review.json',result);
              } finally {if (action.isConnected) action.disabled = false;}
            });
        });
    };
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
            '<button data-source-reconcile="' + i + '">Native evidence reconciliation</button> ' +
            '<button data-source-lineage="' + i + '">Original workflow lineage</button>'
          ])) +
        '<div class="source-toolbar"><button id="retained-source-previous"' +
        (offset === 0 ? ' disabled' : '') + '>Previous</button>' +
        '<button id="retained-source-next"' +
        (page.has_more ? '' : ' disabled') + '>Next</button>' +
        '<button id="retained-source-scope-review">Review page for shared investigations</button></div>';
      queue.querySelector('#retained-source-scope-review').onclick = () =>
        perform(() => reviewRetainedSourcePage(params.toString(), root));
      queue.querySelector('#retained-source-previous').onclick =
        () => { offset = Math.max(0, offset - 10); perform(loadPage); };
      queue.querySelector('#retained-source-next').onclick =
        () => { offset += 10; perform(loadPage); };
      queue.querySelectorAll('[data-source-lineage]').forEach(button => {
        button.onclick = () => perform(async () => {
          const record = page.items[Number(button.dataset.sourceLineage)];
          let originalOffset = 0;
          async function showLineage() {
            const lineage = await api('/api/source-commercial-lineage?' +
              new URLSearchParams({
                kind: record.record_kind, record_id: record.record_id,
                offset: String(originalOffset), limit: '20'
              }));
            if (!root.isConnected || activePage !== 'Sources & Collection') return;
            modal('Original commercial workflow candidate lineage',
              '<p>Exact original candidate-key equality only. Historical status, ' +
              'result revision counts and a shared source do not establish ' +
              'independent project identity, royalty entitlement, payment or ' +
              'permission to contact or bid.</p>' +
              '<pre>' + esc(JSON.stringify(lineage, null, 2)) + '</pre>' +
              '<div class="source-toolbar"><button id="original-lineage-prev"' +
              (originalOffset ? '' : ' disabled') + '>Previous</button>' +
              '<button id="original-lineage-next"' +
              (lineage.has_more ? '' : ' disabled') + '>Next</button></div>');
            document.querySelector('#original-lineage-prev').onclick = () => {
              originalOffset = Math.max(0, originalOffset - 20);
              perform(showLineage);
            };
            document.querySelector('#original-lineage-next').onclick = () => {
              originalOffset += 20;
              perform(showLineage);
            };
          }
          await showLineage();
        });
      });
      queue.querySelectorAll('[data-source-reconcile]').forEach(button => {
        button.onclick = () => perform(async () => {
          const record = page.items[Number(button.dataset.sourceReconcile)];
          const inspection = await api('/api/source-reconciliation?' +
            new URLSearchParams({
              kind: record.record_kind, record_id: record.record_id
            }));
          if (!root.isConnected || activePage !== 'Sources & Collection') return;
          const needsReplay = inspection.replay_eligible === true;
          const needsRevision = inspection.revision_replay_eligible === true;
          const reconciliationTicket = modal('Exact original → native investigation reconciliation',
            '<p>Exact original source evidence compared with the existing canonical ' +
            'investigation store. An unmatched source is NOT an independently ' +
            'verified project. Queuing retained evidence does not merge or authorize ' +
            'outreach, a bid, or a commercial lead.</p><pre>' +
            esc(JSON.stringify(inspection, null, 2)) + '</pre>' +
            (needsReplay || needsRevision ?
              '<p>To hand off only this exact snapshot to the common investigation ' +
              'worker, provide a human review reason and explicitly confirm. ' +
              (needsRevision ? 'This retains a revision of this same source. Earlier evidence ' +
                'remains preserved; existing relationship decisions may require reassessment. ' +
                'The worker rejects this review if the current evidence changes.' : '') + '</p>' +
              '<label>Review reason <textarea id="source-reconcile-reason" ' +
              'maxlength="2000" rows="3" required></textarea></label>' +
              '<label><input id="source-reconcile-confirm" type="checkbox"> ' +
              (needsRevision ? 'I reviewed the original revision and the current native evidence; ' +
                'retain this source revision only.' :
                'I reviewed this specific retained source evidence; replay only.') + '</label>' +
              '<button id="source-reconcile-queue">' +
              (needsRevision ? 'Queue reviewed source revision' : 'Queue verified retained snapshot') +
              '</button>' :
              '<p>No replay allowed. Exact retained or older historical evidence cannot replace ' +
              'the current observation.</p>') +
            (inspection.canonical_investigation_id ?
              '<button id="source-reconcile-open-current">Inspect current shared investigation</button>' : ''));
          const currentButton = document.querySelector('#source-reconcile-open-current');
          if (currentButton) currentButton.onclick = () => perform(() =>
            openInvestigationDossier(inspection.canonical_investigation_id));
          const queueButton = document.querySelector('#source-reconcile-queue');
          if (!queueButton) return;
          queueButton.onclick = () => perform(async () => {
            if (reconciliationTicket !== modalTicket || !$('action-dialog').open) return;
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
                action: needsRevision ? 'retain_revision' : 'retain_missing',
                caller_confirmation: true, review_reason: reason
              });
              if (!root.isConnected || activePage !== 'Sources & Collection' ||
                  reconciliationTicket !== modalTicket || !$('action-dialog').open) return;
              const receiptTicket = modal('Retained source accepted by investigation worker queue',
                '<p>Queued, not necessarily processed. The confirmed human review ' +
                'reason and exact source identity were durably committed as an ' +
                'approval audit alongside the worker job. No project identity or ' +
                'commercial authority is granted.</p>' +
                '<button id="source-reconcile-audit">Inspect immutable approval ' +
                'and current job status</button><pre>' +
                esc(JSON.stringify(receipt, null, 2)) + '</pre>');
              const auditButton = document.querySelector('#source-reconcile-audit');
              auditButton.onclick = () => perform(async () => {
                const audit = await api('/api/source-reconciliation-audit?' +
                  new URLSearchParams({ job: receipt.job_id }));
                if (!root.isConnected || activePage !== 'Sources & Collection' ||
                    receiptTicket !== modalTicket || !$('action-dialog').open) return;
                modal('Retained exact-source replay approval audit',
                  '<p>Verified record of review and present worker status. Neither ' +
                  'completion nor approval establishes a verified construction ' +
                  'project, contact authority or bid readiness.</p><pre>' +
                  esc(JSON.stringify(audit, null, 2)) + '</pre>');
              });
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
            const isParcel = endpoint.endsWith('parcel-candidates');
            modal(isParcel ? 'Retained parcel candidates' : 'Exact source observation',
              '<p>Read-only source claims. An exact APN and county co-occurrence ' +
              'does not establish a common construction project; independent ' +
              'verification and explicit approval are still required.</p><pre>' +
              esc(JSON.stringify(details, null, 2)) + '</pre>' +
              (isParcel ? '<h3>Reviewed handoff to shared investigation evidence</h3>' +
                table(['Retained parcel','Existing worker review'],
                  (details.matches || []).map((item,i) => [
                    esc(item.parcel_record_id)+' · '+esc(item.source_key),
                    '<button data-retained-parcel-review="'+i+'">Compare exact source</button>'
                  ])) : '<p><button id="review-original-source-docket">' +
                'Review original append-only source docket</button></p>'));
            if (!isParcel) {
              const docketButton = document.querySelector('#review-original-source-docket');
              docketButton.onclick = () => perform(async () => {
                const plan = await api('/api/source-review-docket?' + new URLSearchParams({
                  kind: record.record_kind, record_id: record.record_id
                }));
                if (!root.isConnected || activePage !== 'Sources & Collection') return;
                const docketTicket = modal('Original source candidate review docket',
                  '<p>Exact normalized original record, staged-history integrity, and ' +
                  'source SHA-256. An append-only docket is not a verified project, ' +
                  'commercial lead, contact, outreach or bid authority.</p>' +
                  '<pre>' + esc(JSON.stringify(plan,null,2)) + '</pre>' +
                  (plan.may_request_staging ?
                    '<label>Reason for staging this exact unapproved source snapshot ' +
                    '<textarea id="docket-stage-reason" rows="3" maxlength="1000"></textarea></label>' +
                    '<label><input id="docket-stage-confirm" type="checkbox" />' +
                    ' I reviewed this exact normalized source record and authorize ' +
                    'one append-only review snapshot, not lead qualification.</label>' +
                    '<button id="docket-stage-approve">Stage reviewed source snapshot</button>' :
                    '<p>Original source docket table is not initialized. The native ' +
                    'interface will not create or migrate an original database.</p>'));
                const stage = $('docket-stage-approve');
                if (!stage) return;
                stage.onclick = () => perform(async () => {
                  if (docketTicket !== modalTicket || !$('action-dialog').open) return;
                  const reason = $('docket-stage-reason').value.trim();
                  if (reason.length < 10 || !$('docket-stage-confirm').checked)
                    throw Error('Review the exact source and confirm a staging reason.');
                  stage.disabled = true;
                  try {
                    const original = plan.original_source_preview;
                    const receipt = await api('/api/source-review-docket-stage', {
                      kind: record.record_kind,
                      record_id: record.record_id,
                      expected_preview_id: original.preview_id,
                      expected_source_sha256: original.normalized_source_sha256,
                      review_reason: reason,
                      caller_confirmation: true
                    });
                    modal('Original source docket · append-only review receipt',
                      '<p>Unapproved normalized source snapshot retained; no ' +
                      'record promotion, commercial lead, outbound contact or bid.</p>' +
                      '<pre>' + esc(JSON.stringify(receipt,null,2)) + '</pre>' +
                      '<button id="export-original-docket-stage">Export original docket receipt</button>');
                    $('export-original-docket-stage').onclick =
                      () => download('original-unapproved-source-docket.json',receipt);
                  } finally {
                    if (stage.isConnected) stage.disabled = false;
                  }
                });
              });
            }
            if (isParcel) {
              document.querySelectorAll('[data-retained-parcel-review]').forEach(button => {
                button.onclick = () => perform(() => {
                  const item = details.matches[Number(button.dataset.retainedParcelReview)];
                  return reviewRetainedParcelInEngine(item.parcel_record_id);
                });
              });
            }
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
    renderRetainedCeqanetExport(root.querySelector('#retained-ceqanet-export')),
    renderRetainedSmartsHistory(root.querySelector('#retained-smarts-history')),
    renderRetainedSmartsSourceReview(root.querySelector('#retained-smarts-source-review')),
    renderRetainedHistory(root.querySelector('#retained-history-inspection'))
  ]);
}

async function reviewRetainedSourcePage(query, root) {
  const openingTicket = modalTicket;
  const plan = await api('/api/source-reconciliation-scope?' + query);
  if (!root.isConnected || activePage !== 'Sources & Collection' || openingTicket !== modalTicket) return;
  const ticket = modal('Review retained source page → shared investigations',
    '<p>Review every source and digest below. This approves only missing retained ' +
    'snapshots on this bounded page for the existing worker. It does not verify ' +
    'project identity, overwrite conflicting evidence, or authorize commercial activity.</p>' +
    '<p>Scope: ' + esc(JSON.stringify(plan.scope)) + ' · total matching originals: ' +
    esc(plan.total_source_records) + ' · missing: ' + esc(plan.eligible_count) +
    ' · already retained: ' + esc(plan.already_retained_count) + ' · held for individual review: ' +
    esc(plan.requires_review_count) + '. ' + esc(plan.meaning) + '</p>' +
    table(['Source', 'Family / record', 'Original SHA-256', 'Native state'], plan.items.map(item => [
      esc(item.title), esc(item.original_source.kind + ' / ' + item.original_source.record_id),
      '<code>' + esc(item.original_source.source_sha256) + '</code>', esc(item.native_state)
    ])) + '<p>Exact page digest: <code>' + esc(plan.plan_sha256) + '</code></p>' +
    '<button id="source-scope-export">Export reviewed page JSON</button>' +
    (plan.eligible_count ? '<label>Review reason <textarea id="source-scope-reason" ' +
      'maxlength="2000" rows="3"></textarea></label><label><input type="checkbox" ' +
      'id="source-scope-confirm"> I reviewed this exact page and its source digests; ' +
      'queue missing snapshots only.</label><button id="source-scope-queue">Queue ' +
      esc(plan.eligible_count) + ' missing snapshots</button>' :
      '<p>No missing snapshots can be queued from this page. Conflicts require individual review.</p>'));
  $('source-scope-export').onclick = () => download('reviewed-original-source-page.json', plan);
  const button = $('source-scope-queue');
  if (!button) return;
  button.onclick = () => perform(async () => {
    if (ticket !== modalTicket || !$('action-dialog').open) return;
    const reason = $('source-scope-reason').value.trim();
    if (!$('source-scope-confirm').checked || reason.length < 10)
      throw Error('Review the exact page, confirm it, and enter a reason of at least 10 characters.');
    button.disabled = true;
    try {
      const receipt = await api('/api/source-reconciliation-scope-queue', {
        scope: plan.scope, expected_plan_sha256: plan.plan_sha256,
        caller_confirmation: true, review_reason: reason
      });
      if (ticket !== modalTicket || !$('action-dialog').open) return;
      const receiptTicket = modal('Retained source page queued for shared investigation',
        '<p>' + esc(receipt.queued_count) + ' exact snapshots queued atomically with ' +
        'their approval audits. Processing is pending until the existing worker commits. ' +
        'Original data and held conflicts remain unchanged. No identity or commercial authority.</p>' +
        '<p>Batch approval: <code>' + esc(receipt.batch_approval_audit_event_id) + '</code>. ' +
        (receipt.has_more ? 'More original records remain; review the next source page.' :
          'End of this source scan; rescan to verify worker results and any source changes.') + '</p>' +
        table(['Original source', 'Job', 'Current status'], receipt.jobs.map((job, index) => [
          esc(job.original_source.kind + ' / ' + job.original_source.record_id),
          esc(job.job_id), '<button data-scoped-replay-audit="' + index + '">Inspect worker status</button>'
        ])));
      document.querySelectorAll('[data-scoped-replay-audit]').forEach(auditButton => {
        auditButton.onclick = () => perform(async () => {
          const job = receipt.jobs[Number(auditButton.dataset.scopedReplayAudit)];
          const audit = await api('/api/source-reconciliation-audit?' + new URLSearchParams({job: job.job_id}));
          if (receiptTicket !== modalTicket || !$('action-dialog').open) return;
          modal('Original source approval and current worker state', '<pre>' + esc(JSON.stringify(audit, null, 2)) + '</pre>');
        });
      });
    } finally { if (button.isConnected) button.disabled = false; }
  });
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
    const discovery = document.createElement('section');
    discovery.className = 'original-ceqanet-discovery';
    discovery.innerHTML = '<h3>Original CEQAnet public-search discovery</h3>' +
      '<p>One-shot original CS-NET-001 public search-surface check only; ' +
      'no automatic request, ingestion, source activation or commercial authority.</p>' +
      '<button id="preview-ceqanet-discovery">Review bounded discovery</button>';
    box.append(discovery);
    const detail = document.createElement('section');
    detail.className = 'original-ceqanet-detail';
    detail.innerHTML = '<h3>Original CEQAnet detail-page read</h3>' +
      '<p>Original CS-NET-006 one-shot bounded public GET. All lawful-access ' +
      'restriction facts must be reviewed with an immutable evidence/review SHA-256. ' +
      'Unknown restrictions block execution. No automatic network request.</p>' +
      '<button id="review-ceqanet-detail">Review exact detail and access facts</button>';
    box.append(detail);
    detail.querySelector('#review-ceqanet-detail').onclick = () => perform(async () => {
      const fields = [
        ['requires_login', 'Source requires login'],
        ['has_captcha', 'Source presents CAPTCHA'],
        ['robots_disallows_collection', 'Robots disallow intended request'],
        ['terms_disallow_collection', 'Terms disallow intended request'],
        ['paywalled', 'Source is paywalled']
      ];
      const ticket = modal('Original CEQAnet detail · lawful-access preflight',
        '<p>Fill every restriction from independently reviewed evidence. ' +
        'Unknown or restricted facts prevent authorization. Do not guess.</p>' +
        '<label>Exact official CEQAnet detail URL ' +
        '<input id="original-ceqanet-detail-url" type="url" maxlength="2048" ' +
        'placeholder="https://ceqanet.lci.ca.gov/Project/..." /></label>' +
        fields.map(([key, label]) =>
          '<label>'+esc(label)+'<select data-ceqanet-detail-fact="'+esc(key)+'">' +
          '<option value="">Unknown (deny)</option>' +
          '<option value="false">No — reviewed evidence</option>' +
          '<option value="true">Yes — restriction present</option>' +
          '</select></label>').join('') +
        '<label>Immutable reviewed access evidence identity ' +
        '<input id="original-ceqanet-detail-basis" maxlength="80" ' +
        'placeholder="review:64-hex-sha256 or evidence:64-hex-sha256" /></label>' +
        '<button id="preview-reviewed-ceqanet-detail">Review exact bounded plan</button>');
      document.querySelector('#preview-reviewed-ceqanet-detail').onclick = () =>
        perform(async () => {
          if (ticket !== modalTicket || !$('action-dialog').open) return;
          const accessReview = {
            access_fact_basis:
              document.querySelector('#original-ceqanet-detail-basis').value.trim() || null
          };
          document.querySelectorAll('[data-ceqanet-detail-fact]').forEach(field => {
            accessReview[field.dataset.ceqanetDetailFact] =
              field.value === '' ? null : field.value === 'true';
          });
          const request = {
            detail_url: document.querySelector('#original-ceqanet-detail-url').value.trim(),
            access_review: accessReview
          };
          const preview = await api('/api/source-ceqanet-detail-preview', request);
          const reviewTicket = modal('Original CEQAnet detail · exact preview',
            '<p>No live request has been made. Access policy: <strong>' +
            esc(preview.access_decision)+'</strong>. '+esc(preview.access_reason)+'</p>' +
            '<pre>'+esc(JSON.stringify(preview,null,2))+'</pre>' +
            (preview.may_request_approval ?
              '<label>Reason for this exact bounded read ' +
              '<textarea id="original-ceqanet-detail-reason" maxlength="2000" rows="3"></textarea></label>' +
              '<label><input type="checkbox" id="original-ceqanet-detail-confirm">' +
              ' I reviewed this exact URL, the access evidence, and authorize one GET.</label>' +
              '<button id="execute-reviewed-ceqanet-detail">Execute reviewed detail read</button>' :
              '<p>Execution blocked until lawful-access facts are established.</p>'));
          const executeButton = document.querySelector('#execute-reviewed-ceqanet-detail');
          if (!executeButton) return;
          executeButton.onclick = () => perform(async () => {
            if (reviewTicket !== modalTicket || !$('action-dialog').open) return;
            const reason = document.querySelector('#original-ceqanet-detail-reason').value.trim();
            if (reason.length < 10 ||
                !document.querySelector('#original-ceqanet-detail-confirm').checked)
              throw Error('Enter a reason and explicitly confirm this one bounded read.');
            executeButton.disabled = true;
            try {
              const result = await api('/api/source-ceqanet-detail', {
                ...request,
                expected_preview_digest: preview.expected_preview_digest,
                review_reason: reason,
                caller_confirmation: true
              });
              modal('Original CEQAnet detail · governed result',
                '<p>Only one bounded detail-page request was authorized. ' +
                'No verification, registry mutation, recurrence, or commercial ' +
                'action was authorized.</p>' +
                '<pre>'+esc(JSON.stringify(result,null,2))+'</pre>' +
                '<button id="export-original-ceqanet-detail">Export result JSON</button>');
              document.querySelector('#export-original-ceqanet-detail').onclick =
                () => download('original-ceqanet-detail-result.json',result);
            } finally { if (executeButton.isConnected) executeButton.disabled = false; }
          });
        });
    });
    const acquisition = document.createElement('section');
    acquisition.className = 'original-ceqanet-acquisition';
    acquisition.innerHTML = '<h3>Original CEQAnet listing and CSV acquisition</h3>' +
      '<p>Offline plans first. Exact request and lawful-access evidence must be ' +
      'reviewed before separately authorizing a bounded read. No automatic ' +
      'collection, registry mutation or commercial activity.</p>' +
      '<button id="review-ceqanet-listing">Review bounded listing</button> ' +
      '<button id="review-ceqanet-csv">Review exact CSV evidence</button> ' +
      '<button id="review-ceqanet-maturity">Audit retained CSV maturity</button> ' +
      '<button id="review-ceqanet-policy">Audit original CSV access policy</button> ' +
      '<button id="review-ceqanet-series">Audit original CSV evidence series</button> ' +
      '<button id="request-ceqanet-series-evidence">Review policy-bound CSV request</button> ' +
      '<button id="append-ceqanet-series-evidence">Review retained series append</button> ' +
      '<button id="audit-ceqanet-recurring">Audit original recurring-run window</button> ' +
      '<button id="review-ceqanet-recurring-attempt">Review exact recurring attempt</button>';
    box.append(acquisition);
    const accessMarkup = () => [
      ['requires_login', 'Source requires login'],
      ['has_captcha', 'Source presents CAPTCHA'],
      ['robots_disallows_collection', 'Robots disallow the request'],
      ['terms_disallow_collection', 'Source terms disallow collection'],
      ['paywalled', 'Source is paywalled']
    ].map(([key, label]) =>
      '<label>'+esc(label)+'<select data-ceqanet-acq-fact="'+key+'">' +
      '<option value="">Unknown (deny)</option>' +
      '<option value="false">No — independently reviewed</option>' +
      '<option value="true">Yes — restriction present</option>' +
      '</select></label>').join('') +
      '<label>Immutable access evidence / review identity ' +
      '<input id="ceqanet-acq-basis" maxlength="80" ' +
      'placeholder="review:64-hex-sha256 or evidence:64-hex-sha256" /></label>';
    const accessValues = () => {
      const review = {
        access_fact_basis: $('ceqanet-acq-basis').value.trim() || null
      };
      document.querySelectorAll('[data-ceqanet-acq-fact]').forEach(element => {
        review[element.dataset.ceqanetAcqFact] =
          element.value === '' ? null : element.value === 'true';
      });
      return review;
    };
    const smartsCatalog = document.createElement('section');
    smartsCatalog.className = 'original-smarts-catalog-review';
    smartsCatalog.innerHTML = '<h3>Original SMARTS public resource catalog</h3>' +
      '<p>One fixed public CKAN package metadata request, after a complete ' +
      'independent lawful-access review. Not a dataset download, automated ' +
      'collection, schedule, source promotion or commercial action.</p>' +
      '<button id="review-original-smarts-catalog">Review exact catalog request</button> ' +
      '<button id="audit-original-smarts-roster">Audit exact SMARTS roster</button> ' +
      '<button id="review-original-smarts-roster-collection">Review roster collection</button>';
    box.append(smartsCatalog);
    smartsCatalog.querySelector('#review-original-smarts-catalog').onclick =
      () => perform(async () => {
        const ticket = modal('Original SMARTS catalog · public access evidence',
          '<p>Review all restrictions for the fixed official CKAN metadata path. ' +
          'Unknown means no request is authorized. Provide the hash of actual ' +
          'retained access-policy review evidence.</p>' +
          accessMarkup() +
          '<button id="preview-original-smarts-catalog">Preview one metadata GET</button>');
        $('preview-original-smarts-catalog').onclick = () => perform(async () => {
          if (ticket !== modalTicket || !$('action-dialog').open) return;
          const accessReview = accessValues();
          const preview = await api('/api/source-smarts-catalog-preview', {
            access_review: accessReview
          });
          const approvedTicket = modal('Original SMARTS catalog · exact metadata plan',
            '<p>No network request has occurred. Catalog observations cannot ' +
            'verify active construction or authorize regulator data collection.</p>' +
            '<pre>' + esc(JSON.stringify(preview,null,2)) + '</pre>' +
            (preview.may_request_approval ?
              '<label>Reason for this exact single public metadata read ' +
              '<textarea id="smarts-catalog-reason" rows="3" maxlength="1000"></textarea></label>' +
              '<label><input id="smarts-catalog-confirm" type="checkbox" />' +
              ' I reviewed the exact metadata endpoint, source restrictions and ' +
              'evidence and approve one bounded request.</label>' +
              '<button id="execute-original-smarts-catalog">Execute reviewed catalog read</button>' :
              '<p>Access facts are blocked or incomplete. No live request permitted.</p>'));
          const execute = $('execute-original-smarts-catalog');
          if (!execute) return;
          execute.onclick = () => perform(async () => {
            if (approvedTicket !== modalTicket || !$('action-dialog').open) return;
            const reason = $('smarts-catalog-reason').value.trim();
            if (reason.length < 10 || !$('smarts-catalog-confirm').checked)
              throw Error('Confirm the exact source evidence and enter a specific reason.');
            execute.disabled = true;
            try {
              const result = await api('/api/source-smarts-catalog', {
                access_review: accessReview,
                expected_review_digest: preview.expected_review_digest,
                review_reason: reason,
                caller_confirmation: true
              });
              modal('Original SMARTS catalog · metadata evidence',
                '<p>One source metadata observation only. No facility CSV, inspection ' +
                'or enforcement data downloaded; no source verification or lead action.</p>' +
                '<pre>'+esc(JSON.stringify(result,null,2))+'</pre>' +
                '<button id="export-original-smarts-catalog">Export metadata evidence JSON</button>');
              $('export-original-smarts-catalog').onclick =
                () => download('original-smarts-catalog-observation.json',result);
            } finally {
              if (execute.isConnected) execute.disabled = false;
            }
          });
        });
      });
    const confirmAcquisition = async (kind, request) => {
      const preview = await api('/api/source-ceqanet-'+kind+'-preview', request);
      const ticket = modal('Original CEQAnet '+kind+' · exact authority review',
        '<p>No live source request has been made. The original access policy ' +
        'denies unknown restriction facts and unreviewed evidence.</p>' +
        '<pre>'+esc(JSON.stringify(preview,null,2))+'</pre>' +
        (preview.may_request_approval ?
          '<label>Specific reason for this exact approved request ' +
          '<textarea id="ceqanet-acq-reason" rows="3" maxlength="2000"></textarea></label>' +
          '<label><input type="checkbox" id="ceqanet-acq-confirm" />' +
          ' I reviewed the complete source restrictions, evidence and bounded ' +
          'request and authorize one operation.</label>' +
          '<button id="execute-reviewed-acquisition">Execute reviewed '+esc(kind)+'</button>'
          : '<p>This access review cannot authorize execution.</p>'));
      const button = document.querySelector('#execute-reviewed-acquisition');
      if (!button) return;
      button.onclick = () => perform(async () => {
        if (ticket !== modalTicket || !$('action-dialog').open) return;
        const reason = $('ceqanet-acq-reason').value.trim();
        if (reason.length < 10 || !$('ceqanet-acq-confirm').checked)
          throw Error('Enter a reason and approve this exact source request.');
        button.disabled = true;
        try {
          const result = await api('/api/source-ceqanet-'+kind, {
            ...request, expected_preview_digest: preview.expected_preview_digest,
            review_reason: reason, caller_confirmation: true
          });
          const summary = kind === 'csv' ? {
            schema_version: result.schema_version,
            request: result.original_execution.request,
            status_code: result.original_execution.status_code,
            execution_digest: result.original_execution.execution_digest,
            reviewed_preview_digest: result.reviewed_preview_digest,
            original_verification: result.original_verification,
            original_authorization: result.original_authorization,
            persistence_mutated: result.persistence_mutated
          } : result;
          modal('Original CEQAnet '+kind+' · source-evidence result',
            '<p>Original bounded request or durable replay only. No source ' +
            'promotion, ongoing collection, outreach or commercial action.</p>' +
            '<pre>'+esc(JSON.stringify(summary,null,2))+'</pre>' +
            '<button id="export-original-ceqanet-acq">Export original evidence JSON</button>');
          $('export-original-ceqanet-acq').onclick =
            () => download('original-ceqanet-'+kind+'-evidence.json',result);
        } finally {
          if (button.isConnected) button.disabled = false;
        }
      });
    };
    smartsCatalog.querySelector('#review-original-smarts-roster-collection').onclick =
      () => perform(async () => {
        const ticket = modal('Original SMARTS · exact bounded facility sweep',
          '<p>One manually authorized, bounded source-only sweep. Uses the ' +
          'original exact roster, immutable journal, resumable checkpoint, ' +
          'and only 1–25 county-scoped facility requests. No background schedule, ' +
          'lead promotion, outreach or bid.</p>' +
          '<label>Exact run ID <input id="smarts-roster-run" maxlength="64" ' +
          'autocomplete="off"></label>' +
          '<label>Maximum requests (1–25) <input id="smarts-roster-budget" ' +
          'type="number" min="1" max="25" value="1"></label>' +
          accessMarkup() +
          '<button id="preview-smarts-roster-source">Review exact source plan</button>');
        $('preview-smarts-roster-source').onclick = () => perform(async () => {
          if (ticket !== modalTicket || !$('action-dialog').open) return;
          const selected = {
            run_id: $('smarts-roster-run').value.trim(),
            max_requests: Number($('smarts-roster-budget').value),
            access_review: accessValues()
          };
          const preview = await api('/api/source-smarts-roster-preview',selected);
          const approvedTicket = modal('Original SMARTS · approved facility roster',
            '<p>No source request yet. Verify exact facilities, immutable roster ' +
            'digest, current access facts and journal/checkpoint identities ' +
            'before approving one bounded attempt. Failed targets may be ' +
            'resumed only by another explicit operator action.</p>' +
            '<pre>'+esc(JSON.stringify(preview,null,2))+'</pre>' +
            (preview.may_request_approval ?
              '<label>Specific reason for one original roster sweep ' +
              '<textarea id="smarts-roster-reason" rows="3" maxlength="2000"></textarea></label>' +
              '<label><input id="smarts-roster-confirm" type="checkbox"> ' +
              'I reviewed exact IDs, lawful access, budget, permanent ' +
              'evidence retention and checkpoint recovery and approve one sweep.</label>' +
              '<button id="execute-smarts-roster-source">Execute approved sweep</button>' :
              '<p>Unknown source access or incomplete roster/journal/checkpoint ' +
              'configuration prevents collection.</p>'));
          const button = $('execute-smarts-roster-source');
          if (!button) return;
          button.onclick = () => perform(async () => {
            if (approvedTicket !== modalTicket || !$('action-dialog').open) return;
            const reason = $('smarts-roster-reason').value.trim();
            if (reason.length < 10 || !$('smarts-roster-confirm').checked)
              throw Error('Explicitly approve this exact roster and reason.');
            button.disabled = true;
            try {
              const receipt = await api('/api/source-smarts-roster-collect', {
                ...selected, expected_preview_digest: preview.expected_preview_digest,
                review_reason: reason, caller_confirmation: true
              });
              modal('Original SMARTS · retained roster result',
                '<p>Original source journal and checkpoint were updated by ' +
                'the original collector. No recurring timer or commercial action.</p>' +
                '<pre>'+esc(JSON.stringify(receipt,null,2))+'</pre>' +
                '<button id="export-smarts-roster-receipt">Export source receipt</button>');
              $('export-smarts-roster-receipt').onclick =
                () => download('original-smarts-roster-collection-receipt.json',receipt);
            } finally { if (button.isConnected) button.disabled = false; }
          });
        });
      });
    smartsCatalog.querySelector('#audit-original-smarts-roster').onclick = () =>
      perform(async () => {
        const result = await api('/api/source-smarts-roster-audit');
        const available = result.available === true;
        modal('Original SMARTS · exact facility roster audit',
          '<p>Only an explicitly retained 1–25 facility roster. Original ' +
          'APP_ID/WDID identities and county scoping, with optional existing ' +
          'source-journal verification. No facility requests, collection, ' +
          'checkpoint initialization, scheduling, promotion or commercial action.</p>' +
          '<pre>'+esc(JSON.stringify(result,null,2))+'</pre>' +
          (available ? '<button id="export-original-smarts-roster">' +
            'Export bounded roster audit</button>' : ''));
        if (available) {
          document.querySelector('#export-original-smarts-roster').onclick =
            () => download('original-smarts-roster-audit.json',result);
        }
      });
    acquisition.querySelector('#review-ceqanet-recurring-attempt').onclick = () =>
      perform(async () => {
        const ticket = modal('Original CEQAnet · manual exact-window attempt',
          '<p>One manual attempt only, never a schedule. Original registry, ' +
          'checklist, definition and manifest must all match. Review current ' +
          'source restrictions independently; the original durable per-attempt ' +
          'allowance will be consumed if executed.</p>' +
          '<label>Attempt sequence (1–1000) <input id="original-recurring-sequence" ' +
          'type="number" min="1" max="1000" value="1"></label>' +
          accessMarkup() +
          '<button id="preview-original-recurring-attempt">Review exact attempt</button>');
        $('preview-original-recurring-attempt').onclick = () => perform(async () => {
          if (ticket !== modalTicket || !$('action-dialog').open) return;
          const selected = {
            attempt_sequence: Number($('original-recurring-sequence').value),
            access_review: accessValues()
          };
          const preview = await api(
            '/api/source-ceqanet-recurring-attempt-preview',selected
          );
          const approvalTicket = modal('Original CEQAnet · foreground authorization',
            '<p>Readiness is not permission for automatic execution. Approve ' +
            'only this fixed manifest, window, evidence and attempt number. ' +
            'No background scheduling, retries, source promotion or outreach.</p>' +
            '<pre>'+esc(JSON.stringify(preview,null,2))+'</pre>' +
            (preview.may_request_approval ?
              '<label>Specific reason for one exact attempt ' +
              '<textarea id="original-recurring-reason" rows="3" maxlength="2000"></textarea></label>' +
              '<label><input id="original-recurring-confirm" type="checkbox"> ' +
              'I reviewed the current lawful source evidence and explicitly ' +
              'authorize one foreground attempt with durable replay controls.</label>' +
              '<button id="execute-original-recurring-attempt">Execute approved attempt</button>' :
              '<p>Source evidence or manifest is unavailable, restricted or ' +
              'incomplete. No live attempt is permitted.</p>'));
          const button = $('execute-original-recurring-attempt');
          if (!button) return;
          button.onclick = () => perform(async () => {
            if (approvalTicket !== modalTicket || !$('action-dialog').open) return;
            const reason = $('original-recurring-reason').value.trim();
            if (reason.length < 10 || !$('original-recurring-confirm').checked)
              throw Error('Confirm this exact reviewed source evidence and reason.');
            button.disabled = true;
            try {
              const receipt = await api('/api/source-ceqanet-recurring-attempt', {
                ...selected, expected_preview_digest: preview.expected_preview_digest,
                review_reason: reason, caller_confirmation: true
              });
              modal('Original CEQAnet · retained one-shot attempt',
                '<p>Original separately authorized execution; evidence retained ' +
                'locally, no background schedule, retry, registry promotion, ' +
                'contact or bid.</p>' +
                '<pre>'+esc(JSON.stringify(receipt,null,2))+'</pre>' +
                '<button id="export-original-recurring-receipt">Export receipt JSON</button>');
              $('export-original-recurring-receipt').onclick =
                () => download('original-recurring-attempt-receipt.json',receipt);
            } finally { if (button.isConnected) button.disabled = false; }
          });
        });
      });
    acquisition.querySelector('#audit-ceqanet-recurring').onclick = () =>
      perform(async () => {
        const result = await api('/api/source-ceqanet-recurring-audit');
        const available = result.available === true;
        modal('Original CEQAnet · exact recurring-run audit',
          '<p>Verifies the retained original definition, checklist, current ' +
          'registry and exact-window manifest. A run definition is not a ' +
          'schedule or new authorization. No background run or source request.</p>' +
          '<pre>'+esc(JSON.stringify(result,null,2))+'</pre>' +
          (available ? '<button id="export-original-ceqanet-recurring">' +
          'Export exact-window review JSON</button>' : ''));
        if (available) {
          document.querySelector('#export-original-ceqanet-recurring').onclick =
            () => download('original-ceqanet-recurring-window-audit.json',result);
        }
      });
    acquisition.querySelector('#append-ceqanet-series-evidence').onclick = () =>
      perform(async () => {
        const ticket = modal('Original CEQAnet · append retained series evidence',
          '<p>Only an already-retained original evidence execution. No new ' +
          'source request. Review a new immutable successor ledger and manifest ' +
          'without changing the original series or source registry.</p>' +
          '<label>Retained execution filename <input id="series-append-filename" ' +
          'maxlength="160" autocomplete="off" ' +
          'placeholder="ceqanet-csv-evidence-YYYY-MM-DD-SCH-project.json"></label>' +
          '<button id="preview-original-series-append">Review ledger transition</button>');
        $('preview-original-series-append').onclick = () => perform(async () => {
          if (ticket !== modalTicket || !$('action-dialog').open) return;
          const retained_execution_file = $('series-append-filename').value.trim();
          const preview = await api('/api/source-ceqanet-series-append-preview', {
            retained_execution_file
          });
          const ticket2 = modal('Original CEQAnet · exact immutable ledger append',
            '<p>No remote request. The original builder independently checks ' +
            'the candidate, policy and predecessor ledger before publishing ' +
            'new immutable series/manifest artifacts. On restart the new ' +
            'manifest path must be selected.</p>' +
            '<pre>'+esc(JSON.stringify(preview,null,2))+'</pre>' +
            (preview.may_request_approval ?
              '<label>Reason to append this retained observation ' +
              '<textarea id="series-append-reason" rows="3" maxlength="2000"></textarea></label>' +
              '<label><input id="series-append-confirm" type="checkbox" /> ' +
              'I approve this exact evidence-bound immutable ledger transition.</label>' +
              '<button id="apply-original-series-append">Publish reviewed ledger</button>' :
              '<p>Required original evidence series is not configured.</p>'));
          const button = $('apply-original-series-append');
          if (!button) return;
          button.onclick = () => perform(async () => {
            if (ticket2 !== modalTicket || !$('action-dialog').open) return;
            const reason = $('series-append-reason').value.trim();
            if (reason.length < 10 || !$('series-append-confirm').checked)
              throw Error('Approve the exact retained ledger transition and reason.');
            button.disabled = true;
            try {
              const result = await api('/api/source-ceqanet-series-append', {
                retained_execution_file,
                expected_preview_digest: preview.expected_preview_digest,
                review_reason: reason,
                caller_confirmation: true
              });
              modal('Original CEQAnet · immutable series handoff',
                '<p>Next original ledger/manifest selected in this running ' +
                'Command Center. The receipt identifies the exact manifest ' +
                'to select at next startup. No live request, source promotion, ' +
                'recurring collection, outreach or bid.</p>' +
                '<pre>'+esc(JSON.stringify(result,null,2))+'</pre>');
            } finally { if (button.isConnected) button.disabled = false; }
          });
        });
      });
    acquisition.querySelector('#request-ceqanet-series-evidence').onclick = () =>
      perform(async () => {
        const ticket = modal('CEQAnet evidence series · original policy-bound request',
          '<p>This is a separate, explicit one-shot original evidence request. ' +
          'The existing policy must be current, the retained series verified, ' +
          'and present lawful source access independently reviewed. The original ' +
          'execution consumes a durable daily allowance and retains a private ' +
          'execution file; it never advances the ledger automatically.</p>' +
          '<label>Exact 10-digit SCH number <input id="series-csv-sch" ' +
          'maxlength="10" inputmode="numeric" /></label>' +
          '<label>Document ID (empty for project CSV) <input id="series-csv-doc" ' +
          'type="number" min="1" max="2147483647" /></label>' +
          accessMarkup() +
          '<button id="preview-series-csv-execution">Review original request</button>');
        $('preview-series-csv-execution').onclick = () => perform(async () => {
          if (ticket !== modalTicket || !$('action-dialog').open) return;
          const sch = $('series-csv-sch').value.trim();
          const doc = $('series-csv-doc').value.trim();
          const review = {
            export: {sch_number: sch, document_id: doc ? Number(doc) : null},
            access_review: accessValues()
          };
          const preview = await api('/api/source-ceqanet-series-execution-preview',review);
          const approvedTicket = modal('Original CEQAnet series · exact execution proof',
            '<p>No source request yet. Original policy/series verification, UTC ' +
            'allowance, retained output and current access review must all pass. ' +
            'A recorded policy is not proof of present legal permission.</p>' +
            '<pre>'+esc(JSON.stringify(preview,null,2))+'</pre>' +
            (preview.may_request_approval ?
              '<label>Specific reason for exactly one bounded request ' +
              '<textarea id="series-csv-reason" rows="3" maxlength="2000"></textarea></label>' +
              '<label><input type="checkbox" id="series-csv-confirm" /> ' +
              'I confirm current lawful source access, exact request, policy ' +
              'limits, permanent daily allowance and private retained evidence.</label>' +
              '<button id="execute-original-series-csv">Execute approved request</button>' :
              '<p>Original policy, evidence series, date window or source access ' +
              'review is denied. No live request is available.</p>'));
          const button = $('execute-original-series-csv');
          if (!button) return;
          button.onclick = () => perform(async () => {
            if (approvedTicket !== modalTicket || !$('action-dialog').open) return;
            const reason = $('series-csv-reason').value.trim();
            if (reason.length < 10 || !$('series-csv-confirm').checked)
              throw Error('Enter specific reasons and explicitly confirm exact scope.');
            button.disabled = true;
            try {
              const result = await api('/api/source-ceqanet-series-execution', {
                ...review, expected_preview_digest: preview.expected_preview_digest,
                review_reason: reason, caller_confirmation: true
              });
              modal('Original CEQAnet series · retained execution receipt',
                '<p>Original single-request outcome retained locally. No series ' +
                'append, recurring schedule, source promotion, outreach or bid.</p>' +
                '<pre>'+esc(JSON.stringify(result,null,2))+'</pre>' +
                '<button id="export-original-series-csv-receipt">Export receipt JSON</button>');
              $('export-original-series-csv-receipt').onclick =
                () => download('original-series-csv-receipt.json',result);
            } finally { if (button.isConnected) button.disabled = false; }
          });
        });
      });
    acquisition.querySelector('#review-ceqanet-series').onclick = () =>
      perform(async () => {
        const result = await api('/api/source-ceqanet-series-audit');
        const available = result.available === true;
        modal('Original CEQAnet CSV · governed evidence-series audit',
          '<p>Offline independent verification of original policy-bound ' +
          'observations only. This cannot fetch, resume or schedule a source, ' +
          'promote status, or grant commercial authority.</p>' +
          '<pre>'+esc(JSON.stringify(result,null,2))+'</pre>' +
          (available ? '<button id="export-original-ceqanet-series">' +
            'Export verified series summary</button>' : ''));
        if (available) {
          document.querySelector('#export-original-ceqanet-series').onclick =
            () => download('original-ceqanet-evidence-series-audit.json',result);
        }
      });
    acquisition.querySelector('#review-ceqanet-policy').onclick = () =>
      perform(async () => {
        const result = await api('/api/source-ceqanet-policy-audit');
        const available = result.available === true;
        modal('Original CEQAnet CSV · historical access-policy audit',
          '<p>Original exact evidence, registry and expiry verification only. ' +
          'Even a date-window-current policy does not grant present legal source ' +
          'access, automate collection, promote a source or authorize outreach.</p>' +
          '<pre>'+esc(JSON.stringify(result,null,2))+'</pre>' +
          (available ? '<button id="export-original-ceqanet-policy">' +
            'Export access-policy audit JSON</button>' : ''));
        if (available) {
          document.querySelector('#export-original-ceqanet-policy').onclick =
            () => download('original-ceqanet-access-policy-audit.json',result);
        }
      });
    acquisition.querySelector('#review-ceqanet-maturity').onclick = () =>
      perform(async () => {
        const result = await api('/api/source-ceqanet-maturity-audit');
        const available = result.available === true;
        modal('Original CEQAnet CSV · offline source maturity',
          '<p>Independent original replay and keep-partial maturity verification ' +
          'of one retained source response. No network, registry promotion, ' +
          'new recurring collection authority or commercial action.</p>' +
          '<pre>'+esc(JSON.stringify(result,null,2))+'</pre>' +
          (available ? '<button id="export-original-ceqanet-maturity">' +
            'Export verified maturity evidence JSON</button>' : ''));
        if (available) {
          document.querySelector('#export-original-ceqanet-maturity').onclick =
            () => download('original-ceqanet-maturity-audit.json', result);
        }
      });
    acquisition.querySelector('#review-ceqanet-listing').onclick = () =>
      perform(async () => {
        const ticket = modal('Original CEQAnet listing · filters and access',
          '<p>At least one bounded filter is required. Text search is not ' +
          'supported by the original verified request contract.</p>' +
          '<label>Counties, comma-separated ' +
          '<input id="ceqanet-list-counties" value="Riverside, San Bernardino" /></label>' +
          '<label>Document types <input id="ceqanet-list-types" /></label>' +
          '<label>Lead agencies <input id="ceqanet-list-agencies" /></label>' +
          '<label>Received from <input id="ceqanet-list-received-from" type="date" /></label>' +
          '<label>Received to <input id="ceqanet-list-received-to" type="date" /></label>' +
          '<label>Posted from <input id="ceqanet-list-posted-from" type="date" /></label>' +
          '<label>Posted to <input id="ceqanet-list-posted-to" type="date" /></label>' +
          '<label><input type="checkbox" id="ceqanet-list-signal" /> High signal only</label>' +
          '<label>Page size (1–100) <input id="ceqanet-list-size" type="number" ' +
          'min="1" max="100" value="25" /></label>' +
          '<label>Maximum pages (1–10) <input id="ceqanet-list-pages" type="number" ' +
          'min="1" max="10" value="1" /></label>' +
          accessMarkup() +
          '<button id="preview-ceqanet-listing">Preview original bounded listing</button>');
        $('preview-ceqanet-listing').onclick = () => perform(async () => {
          if (ticket !== modalTicket || !$('action-dialog').open) return;
          const value = key => $(key).value;
          const names = key => value(key).split(',').map(s => s.trim()).filter(Boolean);
          const day = key => value(key) || null;
          await confirmAcquisition('listing', {
            query: {
              counties: names('ceqanet-list-counties'),
              document_types: names('ceqanet-list-types'),
              lead_agencies: names('ceqanet-list-agencies'),
              received_from: day('ceqanet-list-received-from'),
              received_to: day('ceqanet-list-received-to'),
              posted_from: day('ceqanet-list-posted-from'),
              posted_to: day('ceqanet-list-posted-to'),
              high_signal_only: $('ceqanet-list-signal').checked,
              page_size: Number(value('ceqanet-list-size')),
              max_pages: Number(value('ceqanet-list-pages'))
            },
            access_review: accessValues()
          });
        });
      });
    acquisition.querySelector('#review-ceqanet-csv').onclick = () =>
      perform(async () => {
        const ticket = modal('Original CEQAnet CSV · source evidence',
          '<p>One official CSV evidence request only. This does not persist ' +
          'the source or authorize automatic document ingestion.</p>' +
          '<label>Exact ten-digit SCH number ' +
          '<input id="ceqanet-csv-sch" maxlength="10" /></label>' +
          '<label>Optional document ID (blank means project CSV) ' +
          '<input id="ceqanet-csv-doc" type="number" min="1" /></label>' +
          accessMarkup() +
          '<button id="preview-ceqanet-csv">Preview official CSV request</button>');
        $('preview-ceqanet-csv').onclick = () => perform(async () => {
          if (ticket !== modalTicket || !$('action-dialog').open) return;
          const doc = $('ceqanet-csv-doc').value.trim();
          await confirmAcquisition('csv', {
            export: {
              sch_number: $('ceqanet-csv-sch').value.trim(),
              document_id: doc ? Number(doc) : null
            },
            access_review: accessValues()
          });
        });
      });
    const retainedCsv = document.createElement('section');
    retainedCsv.className = 'original-ceqanet-retained-import';
    retainedCsv.innerHTML = '<h3>Original retained CSV · governed database import</h3>' +
      '<p>Independently replay one configured original CSV evidence artifact and ' +
      'review its exact write plan before a separately approved atomic import. ' +
      'The source database is never created or migrated by this action. ' +
      'Imported source claims remain unassessed.</p>' +
      '<button id="review-original-retained-csv">Review retained CSV write plan</button>';
    box.append(retainedCsv);
    retainedCsv.querySelector('#review-original-retained-csv').onclick =
      () => perform(async () => {
        const preview = await api('/api/source-ceqanet-retained-import');
        if (!preview.available) {
          modal('Original retained CSV import · not configured',
            '<p>No original evidence import is configured. Select one existing ' +
            'private CSV execution artifact using the ' +
            '<code>--operator-ceqanet-csv-evidence</code> launch option and ' +
            'the existing operator database. No database or source was changed.</p>' +
            '<pre>'+esc(JSON.stringify(preview,null,2))+'</pre>');
          return;
        }
        const ticket = modal('Original retained CSV · exact write plan',
          '<p>No database write has occurred. All observed rows remain unassessed. ' +
          'Compare each original operation, source digest, bound discovery ' +
          'lineage, and destination identity before authorization.</p>' +
          '<pre>'+esc(JSON.stringify(preview,null,2))+'</pre>' +
          '<label>Specific reason for this exact approved original import ' +
          '<textarea id="retained-csv-import-reason" maxlength="2000" rows="3"></textarea></label>' +
          '<label><input id="retained-csv-import-confirm" type="checkbox" />' +
          ' I reviewed every original write-plan operation and source evidence, ' +
          'and approve one atomic import into this exact existing database.</label>' +
          '<button id="apply-reviewed-retained-csv">Apply reviewed original import</button> ' +
          '<button id="export-reviewed-retained-csv">Export original write plan</button>');
        document.querySelector('#export-reviewed-retained-csv').onclick =
          () => download('original-ceqanet-retained-write-plan.json', preview);
        document.querySelector('#apply-reviewed-retained-csv').onclick =
          () => perform(async () => {
            if (ticket !== modalTicket || !$('action-dialog').open) return;
            const reason = $('retained-csv-import-reason').value.trim();
            if (reason.length < 10 || !$('retained-csv-import-confirm').checked)
              throw Error('Enter a specific reason and approve this exact import.');
            const button = $('apply-reviewed-retained-csv');
            button.disabled = true;
            try {
              const applied = await api('/api/source-ceqanet-retained-apply', {
                retained_artifact_sha256: preview.retained_artifact_sha256,
                source_sha256: preview.source_sha256,
                expected_write_plan_digest: preview.expected_write_plan_digest,
                expected_destination_identity: preview.expected_destination_identity,
                review_reason: reason,
                caller_confirmation: true
              });
              modal('Original retained CSV · verified database handoff',
                '<p>The imported observations remain unassessed. ' +
                'No contact, outreach, bid, source promotion or recurring ' +
                'collection was authorized.</p><pre>' +
                esc(JSON.stringify(applied,null,2))+'</pre>' +
                '<button id="export-retained-csv-import-receipt">Export import receipt</button>');
              $('export-retained-csv-import-receipt').onclick =
                () => download('original-ceqanet-retained-import-receipt.json',applied);
              await renderRetainedCaptureInbox(box);
            } finally {
              if (button.isConnected) button.disabled = false;
            }
          });
      });
    discovery.querySelector('#preview-ceqanet-discovery').onclick = () =>
      perform(async () => {
        const preview = await api('/api/source-ceqanet-discovery-preview');
        const ticket = modal('Original CEQAnet discovery · explicit authorization',
          '<p>Only after separate confirmation, this executes the original ' +
          'single bounded public GET for the exact URL below. No redirects, ' +
          'credentials, recurrence, registry changes or commercial actions. ' +
          'Review applicable access terms independently before authorizing.</p>' +
          '<pre>'+esc(JSON.stringify(preview,null,2))+'</pre>' +
          '<label>Reason this exact public discovery is authorized ' +
          '<textarea id="ceqanet-discovery-reason" maxlength="2000" rows="3"></textarea></label>' +
          '<label><input type="checkbox" id="ceqanet-discovery-confirm">' +
          ' I reviewed this exact public URL and authorize one bounded GET.</label>' +
          '<button id="ceqanet-discovery-run">Execute exact reviewed discovery</button>');
        document.querySelector('#ceqanet-discovery-run').onclick = () =>
          perform(async () => {
            if (ticket !== modalTicket || !$('action-dialog').open) return;
            const button = document.querySelector('#ceqanet-discovery-run');
            const reason = document.querySelector('#ceqanet-discovery-reason').value.trim();
            if (reason.length < 10 ||
                !document.querySelector('#ceqanet-discovery-confirm').checked)
              throw Error('Enter an authorization reason and explicitly approve this one GET.');
            button.disabled = true;
            try {
              const result = await api('/api/source-ceqanet-discovery', {
                policy_id: preview.policy_id,
                request_url: preview.request_url,
                expected_state_digest: preview.expected_state_digest,
                utc_date: preview.utc_date,
                review_reason: reason,
                caller_confirmation: true
              });
              modal('Original CEQAnet public-search discovery · bounded result',
                '<p>One-shot source-surface observation only. No CEQA records ' +
                'ingested, source verified, registry changed or contact authorized.</p>' +
                '<pre>'+esc(JSON.stringify(result,null,2))+'</pre>' +
                '<button id="export-original-ceqanet-discovery">Export result JSON</button>');
              document.querySelector('#export-original-ceqanet-discovery').onclick =
                () => download('original-ceqanet-discovery.json',result);
            } finally {
              if (button.isConnected) button.disabled = false;
            }
          });
      });
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


// Preserved original combined SMARTS facility/inspection/compliance corroboration review.
// The operator selects only the county; exact CSV file locations are startup-controlled.
async function renderRetainedSmartsSourceReview(box) {
  if (!box || !box.isConnected || activePage !== 'Sources & Collection') return;
  box.innerHTML = '<h3>Original SMARTS inspection and compliance source review</h3>' +
    '<p>Read only. Compares two retained facility CSV versions and, when provided, ' +
    'separately sourced inspections, violations and enforcement. ' +
    'No fresh download, verified construction claim, identity promotion or outreach.</p>' +
    '<label>County <select id="original-smarts-review-county">' +
    '<option>Riverside</option><option>San Bernardino</option></select></label> ' +
    '<button id="inspect-original-smarts-combined">Review exact retained SMARTS evidence</button>';
  box.querySelector('#inspect-original-smarts-combined').onclick = () =>
    perform(async () => {
      const county = box.querySelector('#original-smarts-review-county').value;
      const reviewed = await api('/api/source-smarts-original-source-review?' +
        new URLSearchParams({county}));
      if (!box.isConnected || activePage !== 'Sources & Collection') return;
      if (!reviewed.available) {
        modal('Original SMARTS offline review · no retained input configured',
          '<p>No original facility/inspection/compliance review manifest was ' +
          'selected. Use <code>--operator-smarts-review-manifest</code> with an ' +
          'existing private, exact-source input manifest at launch. ' +
          'An absent capture does not mean no regulatory changes exist.</p>' +
          '<pre>'+esc(JSON.stringify(reviewed,null,2))+'</pre>');
        return;
      }
      modal('Original SMARTS facility and regulatory source review',
        '<p>Every original retained-source SHA-256 is reported. Inspection, ' +
        'violation and enforcement records are source-scoped corroboration ' +
        'candidates only. No automatic database write, physical construction ' +
        'confirmation, contact authorization or sales readiness.</p>' +
        '<pre>'+esc(JSON.stringify(reviewed,null,2))+'</pre>' +
        '<button id="export-original-smarts-source-review">Export original review JSON</button>');
      document.querySelector('#export-original-smarts-source-review').onclick =
        () => download('original-smarts-combined-source-review.json',reviewed);
    });
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


// The original independently verified report / bundle / ZIP path; never source collection.
async function renderRetainedCeqanetExport(box) {
  if (!box || !box.isConnected || activePage !== 'Sources & Collection') return;
  box.innerHTML = '<h3>Original CEQAnet verified operator package</h3>' +
    '<p role="status">Checking exact configured report…</p>';
  try {
    const status = await api('/api/source-ceqanet-export-status');
    if (!box.isConnected || activePage !== 'Sources & Collection') return;
    if (!status.configured) {
      box.innerHTML = '<h3>Original CEQAnet verified operator package</h3>' +
        '<p>No original chain report is selected. Pass ' +
        '<code>--operator-ceqanet-chain-report</code> at launch to enable an ' +
        'explicit local ZIP export. No archive has been fabricated.</p>';
      return;
    }
    const sha = status.retained_report_sha256;
    box.innerHTML = '<h3>Original CEQAnet verified operator package</h3>' +
      '<p>Exact retained chain report SHA-256: <code>' + esc(sha) + '</code>. ' +
      'The original package, persistence/write previews, report, manifest and ' +
      'deterministic ZIP are checked before a download is offered. Exporting ' +
      'does not acquire records, contact prospects or authorize bids.</p>' +
      '<label><input id="original-export-confirm" type="checkbox"> ' +
      'I authorize only a local verified export of this exact retained report.</label>' +
      '<button id="original-export-generate">Build verified operator ZIP</button>' +
      '<div id="original-export-result" aria-live="polite"></div>';
    const generate = box.querySelector('#original-export-generate');
    generate.onclick = () => perform(async () => {
      if (!box.querySelector('#original-export-confirm').checked) {
        throw Error('Explicit local report export confirmation is required.');
      }
      generate.disabled = true;
      try {
        const receipt = await api('/api/source-ceqanet-export', {
          expected_report_sha256: sha, caller_confirmation: true
        });
        if (!box.isConnected || activePage !== 'Sources & Collection') return;
        if (!receipt.verification_passed || !receipt.archive_available) {
          throw Error('Original CEQAnet ZIP verification was not established.');
        }
        const output = box.querySelector('#original-export-result');
        output.innerHTML = '<p>Verified original operator ZIP is ready. ' +
          'No commercial action was authorized.</p><a id="original-export-download" ' +
          'href="' + esc(receipt.archive_url) +
          '" download="ceqanet-operator-export.zip">Download verified ZIP</a> · ' +
          '<a href="/api/source-ceqanet-report-download?sha256=' +
          encodeURIComponent(sha) +
          '" download="ceqanet-operator-report.md">Read verified report (.md)</a>' +
          '<p>Individual original verified artifacts: ' +
          ['operator-package.json', 'persistence-preview.json', 'write-plan.json',
           'operator-report.json', 'manifest.json'].map(name =>
            '<a href="/api/source-ceqanet-artifact-download?sha256=' +
            encodeURIComponent(sha) + '&artifact=' + encodeURIComponent(name) +
            '" download="' + name + '">' + esc(name) + '</a>'
          ).join(' · ') + '</p>' +
          '<details><summary>Verification receipt</summary><pre>' +
          esc(JSON.stringify(receipt, null, 2)) + '</pre></details>';
      } finally {
        if (generate.isConnected) generate.disabled = false;
      }
    });
  } catch (error) {
    if (box.isConnected && activePage === 'Sources & Collection') box.innerHTML =
      '<h3>Original CEQAnet verified operator package</h3>' +
      '<p role="alert">' + esc(error.message) + '</p>';
  }
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
  let offset = 0, pageRequest = 0;
  try {
    const summary = await api('/api/workflow-summary');
    if (!root.isConnected || activePage !== category) return;
    if (!summary.available) {
      root.innerHTML = '<h3>Preserved workflow / outcome records</h3>' +
        '<p>Not connected. Configure the existing operator source database to inspect ' +
        'the historical governed records without modifying them.</p>';
      return;
    }
    async function loadLegacyPage(nextOffset) {
      const ticket = ++pageRequest;
      root.innerHTML = '<h3>Preserved workflow / outcome records</h3>' +
        '<p role="status">Loading retained history at offset ' + esc(nextOffset) + '…</p>';
      try {
        const route = category === 'Bid Studio' ? '/api/workflows?' : '/api/results?';
        const page = await api(route + new URLSearchParams({
          limit: '25', offset: String(nextOffset)
        }));
        if (!root.isConnected || activePage !== category || ticket !== pageRequest) return;
        if (!page.available) {
          root.innerHTML = '<h3>Preserved workflow / outcome records</h3>' +
            '<p>Original operator history is not connected.</p>';
          return;
        }
        offset = nextOffset;
        const records = category === 'Bid Studio' ? page.leads || [] : page.results || [];
    root.innerHTML = '<h3>Preserved workflow / outcome records</h3>' +
      '<p>Legacy records are displayed separately from current native bids/royalties. ' +
      'They are not independently verified current jobs, payments, or permission to send. ' +
      'Persisted workflows: ' + esc(summary.total) + '; displayed records: ' +
      esc(records.length) + ' of ' + esc(page.total) +
      ' · page offset ' + esc(offset) +
      (page.has_more ? ' · more original records available' : '') + '.</p>' +
      table(['Retained identity', 'Status / evidence', 'Inspection'],
        records.map((r, i) => [
          esc(r.workflow_id || r.ledger_id || r.candidate_key || 'Retained outcome'),
          esc(r.status || r.current_status || r.summary || 'Stored historical fact'),
          '<button data-original-record="' + i + '">Inspect history</button> ' +
          (typeof r.workflow_id === 'string' ?
            '<button data-original-attribution="' + i +
            '">Trace exact source</button>' : '')
        ])) +
      '<p>' + esc((page.limitations || summary.limitations || []).join(' ')) + '</p>' +
      '<div class="source-toolbar"><button data-original-previous ' +
      (offset === 0 ? 'disabled' : '') + '>Previous historical records</button> ' +
      '<button data-original-next ' + (page.has_more ? '' : 'disabled') +
      '>Next historical records</button></div>' +
      '<button id="legacy-record-export">Export displayed retained JSON</button>';
    root.querySelector('[data-original-previous]').onclick = () =>
      perform(() => loadLegacyPage(Math.max(0, offset - 25)));
    root.querySelector('[data-original-next]').onclick = () =>
      perform(() => loadLegacyPage(offset + 25));
    root.querySelector('#legacy-record-export').onclick = () =>
      download(category === 'Bid Studio' ? 'original-workflows.json' :
        'original-results.json', page);
    root.querySelectorAll('[data-original-record]').forEach(button => {
      button.onclick = () => modal('Preserved authoritative record',
        '<p>Historical retained data, not a new commercial authorization.</p><pre>' +
        esc(JSON.stringify(records[Number(button.dataset.originalRecord)], null, 2)) +
        '</pre>');
    });
    root.querySelectorAll('[data-original-attribution]').forEach(button => {
      button.onclick = () => perform(async () => {
        const record = records[Number(button.dataset.originalAttribution)];
        const workflowId = record.workflow_id;
        if (typeof workflowId !== 'string' || !workflowId) {
          throw Error('This original record has no exact persisted workflow identity.');
        }
        modal('Trace original workflow to an exact source',
          '<p>Provide the original CEQA or permit record identity. The persisted ' +
          'workflow candidate key must exactly equal that source key. No address, ' +
          'project name, parcel or approximate matching is performed. This is ' +
          'read-only and does not verify payments or authorize sales.</p>' +
          '<p>Exact original workflow: <code>' + esc(workflowId) + '</code></p>' +
          '<form id="original-workflow-attribution-form" class="form-grid">' +
          '<label>Source family <select name="kind" required>' +
          '<option value="ceqa">CEQA</option><option value="permit">Permit</option>' +
          '</select></label>' +
          '<label>Exact original source record ID ' +
          '<input name="record_id" maxlength="255" required></label>' +
          '<button type="submit">Verify exact source lineage</button></form>' +
          '<div id="original-workflow-attribution-result" role="status"></div>');
        const form = document.querySelector('#original-workflow-attribution-form');
        const epoch = modalTicket;
        form.onsubmit = event => {
          event.preventDefault();
          perform(async () => {
            const submit = form.querySelector('[type=submit]');
            submit.disabled = true;
            const values = new FormData(form);
            try {
              const attribution = await api('/api/original-workflow-attribution?' +
                new URLSearchParams({
                  workflow: workflowId, kind: values.get('kind'),
                  record_id: String(values.get('record_id')).trim()
                }));
              if (epoch !== modalTicket || !form.isConnected) return;
              const linked = attribution.current_native_observation_matches_original &&
                typeof attribution.canonical_investigation_id === 'string';
              document.querySelector('#original-workflow-attribution-result').innerHTML =
                '<p>Exact original source candidate matched. The historical workflow, ' +
                'result revisions and calculated shares remain unverified commercial ' +
                'claims; there is no proof of entitlement or payment.</p>' +
                '<pre>' + esc(JSON.stringify(attribution, null, 2)) + '</pre>' +
                (linked ? '<button id="original-attribution-open-native">' +
                  'Open exact canonical investigation</button>' :
                  '<p>No current exact native source evidence is present. A ' +
                  'cross-investigation identity link has not been asserted.</p>') +
                '<button id="original-attribution-export">Export validated lineage</button>';
              document.querySelector('#original-attribution-export').onclick = () =>
                download('original-exact-workflow-source-attribution.json', attribution);
              const open = document.querySelector('#original-attribution-open-native');
              if (open) open.onclick = () => perform(() =>
                openInvestigationDossier(attribution.canonical_investigation_id));
            } catch (error) {
              if (epoch === modalTicket && form.isConnected) {
                document.querySelector('#original-workflow-attribution-result')
                  .textContent = 'Exact attribution rejected: ' + error.message +
                    '. No source identity or commercial authority was inferred.';
              }
            } finally {
              if (submit.isConnected) submit.disabled = false;
            }
          });
        };
      });
    });
        if (category === 'Bid Studio') renderRetainedCommercialPreviewTools(root, records);
      } catch (error) {
        if (root.isConnected && activePage === category && ticket === pageRequest)
          root.innerHTML = '<h3>Preserved workflow / outcome records</h3>' +
            '<p role="alert">Historical page could not be loaded: ' +
            esc(error.message) + '.</p><button data-original-retry>Retry page</button>';
        const retry = root.querySelector('[data-original-retry]');
        if (retry) retry.onclick = () => perform(() => loadLegacyPage(nextOffset));
      }
    }
    await loadLegacyPage(0);
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
