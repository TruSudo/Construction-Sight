# Local operator application

Run the read-only application against an **existing, initialized** ConstructionSight
SQLite database:

```bash
constructionsight-operator --database /absolute/path/to/constructionsight.sqlite3
```

For a source checkout whose package entry points have not yet been installed:

```bash
PYTHONPATH=src python -m constructionsight.operator_web --database /absolute/path/to/constructionsight.sqlite3
```

Open `http://127.0.0.1:8765`. An optional `--port` selects another loopback port.
A missing database produces an explicit startup error. The operator does not
create a database, run migrations, repair records, or authorize data acquisition.
Populate the database through existing governed intake/persistence commands.

## Connected behavior

- Project records read the typed CEQA and permit domain tables, including embedded
  site, named-party, and provenance records. They do not guess project information
  from workflow or enrichment payloads, or join unrelated sites by position.
- The default **All source records** view reads both CEQA and permit families
  in stable order (CEQA by persisted ID, then permits by persisted ID). Source
  type is retained on every record; records with equal IDs across families
  remain separate. Source-specific views are also available. No cross-source
  deduplication or identity resolution is implied by combining the list.
- Search and county filtering apply to both families before pagination.
  Matching totals cover the entire filtered query across the selected families;
  returned and page-mapped counts describe only the current list page. The GUI
  uses 50 records per page. The API accepts 1–500 and explicit offsets.
- The separate geographic-footprint read scans up to 5,000 matching source
  records in stable combined order and maps every supported coordinate in that
  scan. It reports the whole-query total, records scanned, mapped count, cap and
  truncation flag. When the total exceeds the cap, the GUI expressly labels the
  map incomplete. Map identities retain source family and record ID; selecting
  a point outside the current list page navigates to its stable query page.
  Combining points does not deduplicate or assert that two source records are
  one real-world project.
- The detail panel exposes exact record identity, recorded status/document type,
  address/APN, named parties and their stated roles, source URLs, evidence text,
  capture dates where recorded, location evidence, and limitations.
- CEQA received/posted and permit applied/issued/finaled dates are displayed as
  individual, source-claimed historical milestones when recorded. Each single
  record's dates are sorted chronologically; contradictory source event order
  receives an explicit limitation, and missing dates are never manufactured.
  Dates and status do not prove actual construction start or present phase, nor
  do coincident dates prove records concern the same project. Original record
  provenance remains available in the evidence panel.
- An operator may inspect the exact stored `entity_key` of a named party across
  CEQA and permit source records. The read scans at most 5,000 records in the
  selected source-family/county scope and lists up to 100 exact-key matches.
  Returned metadata separately discloses total source records, scanned records,
  matches within the scan, displayed matches, and whether either cap was reached.
  Repeated names with different entity keys are not joined. Equal record IDs in
  different source families remain distinct. An equal stored entity key is only
  a co-occurrence of stored source assertions, **not** independent verification
  that the named real-world party is the same. The selected key can highlight
  related markers already present in the current footprint and fit those visible
  markers; records outside the footprint/search or either scan cap are not
  represented as mapped relations. No new map coordinates or confidence claims
  are generated.
- The offline coordinate map uses a common Web Mercator scale for both axes, a
  geographic graticule, pan/zoom, fit-to-page, keyboard controls, and selectable
  source locations. It has **no street basemap, county boundaries, parcel polygons,
  automatic geocoding, or crime data**. It does not fetch map tiles or other assets.
  Unmapped records remain searchable and inspectable.
- Coordinates require a complete finite geographic pair and site provenance.
  Unsupported ranges, missing evidence, and conflicting record/site counties
  produce an explicit unmapped reason. Even displayed coordinates remain
  `source_claimed`; a stored provenance verification flag is not promoted into
  independent verification of location or current construction activity.
- The exact-record read-only `/api/candidate-preview?kind=ceqa|permit&record_id=...`
  bridge derives a deterministic source-family-specific candidate key and a
  revision-specific SHA-256 digest of the stored normalized record, including
  its complete typed CEQA/permit source snapshot and nested site evidence. The digest
  is **not** a hash of original raw source bytes. It retains the full normalized
  source evidence in the typed preview, separates provenance, scope, site,
  named-party, current-activity, deduplication and commercial-review checks,
  and marks absent provenance, unknown/out-of-scope county, or contradictory
  record/site county as hold. All other previews are review-required, NEVER
  outreach-ready. It performs no source reinspection, score fabrication, network
  access, persistence, lead conversion, approval or external action. A separate
  explicitly authorized persistence/review workflow is still required.
- The record detail panel exposes an explicit **Inspect review gaps** button. It
  requests the exact selected source-family/key pair and renders the review
  state, digest, observations and unresolved checks. Responses from superseded
  selections are ignored, and the preview is suppressed if its complete
  currently projected source record differs from the already displayed record.
  Changes to normalized source fields not included in the display are still
  separately bound to the preview's source digest; the read-only UI does not
  attempt to certify those field histories. All supplied source text is HTML-escaped. The
  button is read-only: it does not persist a lead, authorize commercial action,
  or claim browser acceptance before actual browser verification.
- Lead workflow reads persisted workflow records and the exact `package_id` each
  workflow references. It does not substitute the newest review for the same
  candidate. Missing exact reviews remain visible as limitations; contradictory
  identities fail the request. Workflows have separate pagination.
- Both views are read-only. Source records are not deduplicated projects or
  qualified leads. No source record is silently promoted to an outreach-ready
  opportunity, and an old document/permit status is not a current phase assertion.

## Local boundary

The SQLite connection uses `mode=ro`. HTTP binds only to `127.0.0.1`, accepts exact
loopback Host values and same-origin browser requests, and exposes GET-only views.
The GUI loads its JavaScript/CSS locally, escapes displayed source strings, limits
source links to HTTP(S), and uses a CSP without inline scripts. Database read or
schema errors return a generic 503 instead of leaking paths or returning a false
empty success. Refresh explicitly reloads the current stored-data query; it does
not run live collection.

## Verification and remaining integration

`tests/test_operator_dashboard.py` exercises the existing authorized CEQAnet
preview/write-plan/persistence path through real SQLite and loopback HTTP, plus
permit/site/entity evidence, search beyond the first page, exact review joins,
unmapped cases, rejected requests, and database immutability. Its records are
**synthetic fixtures**, not live discoveries or commercial opportunities.

The typed HTTP dispatch, bounded entity-neighborhood, source-history, exact
candidate-preview, and operator read models have synthetic test coverage.
At historical exact-head commit `76473db5542d328623c7afa1c8bdfb45b8a564f3`,
GitHub Actions run 35528627344 passed 1,542 pytest cases in **each** supported
Python runtime, strict mypy, compilation and 115/115 focused mutation checks.
That predecessor CI run also reported eight Ruff import issues; they were
corrected in a subsequent development commit. The full repository certification
remains blocked by active defects and the missing Native Maximum Assurance
artifact. Historical results must not be reused to claim a newer source tree
passed its exact-head checks.

The graphical map and the new staging CLI still require real operator/browser
acceptance against appropriately sourced populated local data. Synthetic read
models, HTTP tests and CLI fixtures do not establish visual quality, reliable
live-source operation or production fitness. Packaging must include
`operator_ui.html`, `operator_ui.js`, and `operator_ui.css`.

The next product increments remain source-to-opportunity conversion through the
existing scoring/review controls, governed operator actions, actual county/parcel
layers, relationship/history views, and the established commercial workflow.
This slice does not complete those requirements or the private operational release.

PR #119 remains stacked on draft PR #117. The inherited active ledger now
contains 74 records (`CS-SR-001` through `CS-SR-074`) plus the separate missing
Native Maximum Assurance report, which prevents certification. The historical
September 18 hardening-branch CI reported 74 findings at its earlier exact head
(73 active defects plus the missing assurance report), not this current tree.
The September 20 integration CI originally identified active AnyIO advisories
in both locks. A reviewed fixed-wheel candidate was propagated from PR #117;
fresh exact-head isolated vulnerability audits passed in both supported runtimes,
but that is not defect closure or full assurance certification. Local integration results are
not assurance artifacts, owner acceptance, authenticated CI evidence, or permission
to merge. The inherited canonical CI workflow only runs automatically for pull
requests targeting `main`; this stacked PR does not have an automatic run. Its
hashed workflow is deliberately unchanged by this integration slice.


## Explicit unapproved source-review docket (local CLI)

The operator HTTP application intentionally remains **GET-only**. To retain a
source-review snapshot, first preview the exact persisted record:

```bash
constructionsight-candidate-docket preview --database /absolute/path/to/constructionsight.sqlite3 --kind ceqa --record-id '<exact ceqa_key>'
```

Use the returned `preview_id` and `normalized_source_sha256` in a separate
explicitly confirmed local staging request:

```bash
constructionsight-candidate-docket stage --database /absolute/path/to/constructionsight.sqlite3 --kind ceqa --record-id '<exact ceqa_key>' --expected-preview-id '<exact preview_id>' --expected-source-sha256 '<exact normalized_source_sha256>' --reason 'Retain for further review' --operator-id 'operator:local' --confirm
```

The append-only `source_candidate_review_docket` table is registered with
`constructionsight init-db --database-url 'sqlite+pysqlite:////absolute/path/to/constructionsight.sqlite3'`.
For a legacy database, run the existing explicit operator maintenance command
before staging; staging and GUI reads do not initialize or silently migrate
a database.

Under one SQLite `BEGIN IMMEDIATE` transaction, staging reloads the exact
source-family/key pair, recomputes the preview ID and normalized source digest,
rejects stale source revisions and inserts only a unique content-bound, unapproved
review snapshot. Existing exact previews are not overwritten or relabeled to another actor or
rationale; a separate operator attempting to stage an already-present exact
content identity must inspect its original docket entry. Changed source
content creates a separate revision and prior snapshots remain inspectable.
The preview retention limit is 1 MB of canonical UTF-8 JSON, verified before
local authorization and inside the protected transaction so an oversized
result cannot commit a stage then fail the separate effect-ledger retention.
The operator's exact bounded staging rationale is retained in the local docket,
its independent digest is rechecked on read and its text is bound to the row
integrity digest. Direct database edits remain outside this application's
threat model. A successful effect-ledger replay also verifies the exact staged database row
still exists and matches the retained result; it cannot silently claim a lost
or altered local docket entry is present.
Conflicting repeat staging attempts (including changes to the actor's rationale)
are reported as controlled CLI denials rather than uncaught Python tracebacks.
The application uses scope-bound local confirmation and the existing durable
effect-reservation ledger; neither these controls nor source hashes defeat
malicious direct SQLite file modification. Operator ID is an **audit label, not
authentication**. The docket is not an independently signed source artifact,
scored/qualified commercial lead, outreach authorization, bid or approval.

Read back retained revisions with
`constructionsight-candidate-docket list --database /absolute/path/to/constructionsight.sqlite3 --kind ceqa --record-id '<exact ceqa_key>'`.
Readback verifies the normalized-source digest, preview/payload identities and
a receipt digest over the staged row's source and operator audit metadata;
these unkeyed digests detect inconsistent stored data but are **not**
cryptographic evidence of who wrote a record or a substitute for independent
source verification. Readback
the list is bounded at 100. This increment does not promote records into the
separately governed commercial lead workflow or change the GUI's GET-only scope.

## Retained-source pulse and map viewport (draft)

The four summary cards report **matching retained source records** (not unique
construction projects or qualified leads), mapped and unmapped records **within
the bounded coordinate scan**, and whether that scan covered the entire
matching persisted query. An incomplete 5,000-record scan is expressly marked
as capped; no conclusion about coordinates or activity in unscanned records
is supported. A list/map total mismatch is marked as a read mismatch because
the two read-only requests are separate, not one transactional snapshot.
These counters are not a live regional activity feed or proof of source
coverage across San Bernardino or Riverside counties.

The coordinate map legend distinguishes ordinary source-record markers,
selected records, and records sharing an **exact stored entity key**; a
shared key is not independently established corporate/person identity.
Pagination retains the map center and zoom while search, county, record-family
or view-mode changes refit the corresponding footprint. Explicit Refresh
refits to the current query. The interface is still a loopback browser GUI,
not an installed PySide6 desktop shell, street basemap, or parcel/county
geographic layer. Browser visual and interaction acceptance remains required.

## Historical source-record timeline (draft)

The read-only \`/api/timeline\` endpoint scans at most 5,000 stored source
records in the same stable combined CEQA/permit ordering and current query,
family, and county filter as the main list. It displays at most 80 individual,
most-recent recorded CEQA received/posted and permit applied/issued/finaled
events in the **scanned** set. Missing dates remain absent; contradictory
intra-record date sequences remain visible and explicitly flagged. Source
family and exact record key prevent same-string CEQA and permit identifiers
from being conflated. The timeline retains the source record ordinal so its
event can navigate to the original source record even when the record has no
supported map coordinates or is outside the current 50-record page.

The response separately reports matched source records, scanned source
records, records with dates, total events in the scan, returned events, and
both the source-scan and event-result truncation flags. If the scanned source
records are truncated, more recent milestones **may exist outside the scan**:
the panel must not claim to show the globally latest events. The list, map,
and timeline use separate read-only requests, and a source-count mismatch
disables timeline navigation pending a refresh. Recorded dates, phases,
issuances, and finalizations do not establish actual physical commencement,
current site activity, independent entity identity, or qualified opportunities.
This is not a live-ingestion schedule, deduplicated project growth replay,
or a production-level authoritative project timeline.
