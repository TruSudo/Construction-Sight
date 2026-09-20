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

The new typed HTTP dispatch and bounded entity-neighborhood regression cases have
been committed but have **not** been executed against the current head; no CI
or type-check success is claimed for the new integration commits. The graphical map still requires real-browser visual verification. Tests of the
read model and HTTP service alone do not establish visual quality or browser
interaction correctness. Packaging must include `operator_ui.html`,
`operator_ui.js`, and `operator_ui.css`.

The next product increments remain source-to-opportunity conversion through the
existing scoring/review controls, governed operator actions, actual county/parcel
layers, relationship/history views, and the established commercial workflow.
This slice does not complete those requirements or the private operational release.

PR #119 remains stacked on draft PR #117. The 73 inherited active defect
records (`CS-SR-001` through `CS-SR-073`) and the separate missing Native
Maximum Assurance report remain outstanding; the September 18 hardening-branch
CI reported 74 certification findings at its own exact head. Local integration results are
not assurance artifacts, owner acceptance, authenticated CI evidence, or permission
to merge. The inherited canonical CI workflow only runs automatically for pull
requests targeting `main`; this stacked PR does not have an automatic run. Its
hashed workflow is deliberately unchanged by this integration slice.
