# SMARTS source integration — operator runbook (2026-10-12)

## Scope and evidence classification

The development implementation supports four distinct forms of evidence:

1. **Bounded public API lookup** of exact San Bernardino or Riverside construction
   facility identities, normalized to the existing source-neutral intake and
   site-resolution preview. No physical work or contract demand is inferred.
2. **Opt-in, private immutable local response journal** with semantic source-row
   versioning and a crash-recoverable 1–25 exact-identity roster collector.
3. **Offline comparison of two supplied construction-facility CSV exports**,
   emitting content-change candidates but no automatic deletion findings.
4. **Offline, source-scoped corroboration** against inspection, violation, and
   enforcement CSV exports, with direct APP_ID/WDID agreement and strict
   county/program scope. These outputs never certify a parcel/project match.

All four are development/review capabilities, not evidence of production
ingestion, guaranteed weekly coverage, active building work, lead maturity,
or a commercial opportunity. The work leaves the entity graph, approved GUI
and watchlist mutations unchanged.

## Official public source references

Publisher: California State Water Resources Control Board.
Dataset: https://publish.data.ca.gov/dataset/stormwater-regulatory-including-enforcement-actions-information-and-water-quality-results

| Role | Catalog resource ID | Implemented stage |
| --- | --- | --- |
| Construction facility information | `8a0ed456-ca69-4b29-9c5b-5de3958dc963` | Exact API preview, evidence journal, offline CSV diff |
| Inspections | `33047e47-7d44-46aa-9e0f-1a0f1b0cad66` | Offline source-ID joins only |
| Violations | `9b69a654-0c9a-4865-8d10-38c55b1b8c58` | Offline source-ID joins only |
| Enforcement actions | `9cf197f4-f1d5-4d43-b94b-ccb155ef14cf` | Offline source-ID joins only |

The same catalog contains construction-monitoring and industrial resources.
They are **not** automatically added to the construction-intelligence graph.
The source catalog listed a weekly update cadence and the files were last
updated on 2026-10-02 when checked on 2026-10-12. Dates and counts are
publisher metadata, not direct inspection of source file bytes.

The dataset-level rights statement reads "No Restrictions on Public Use";
individual resources also display "No License Provided". Attribution, terms
for redistribution/retention and any source-specific operational restrictions
must be confirmed in the approved access-governance record before automated
production harvest and resale-oriented use. Public access alone does not
turn source-personal contact fields into outreach authorization.

## Opt-in published-catalog freshness and schema observation

`python -m constructionsight.smarts_catalog_probe --execute-live` makes a
single, explicitly authorized, bounded read-only `package_show` request to
the fixed public California SMARTS dataset identifier. It validates that the
four approved resource IDs remain present and labeled CSV, then emits only
resource names, reported sizes, last-modified metadata and the complete
metadata-response SHA-256. The installed command alias is
`constructionsight-smarts-catalog --execute-live`. No dataset is downloaded,
no background polling is scheduled, no source rows or contacts are logged,
and no publication cadence or legal-use rights is automatically certified.

The metadata probe is a separate health *observation*; a newer
`last_modified` should prompt an operator to investigate a newly available
official export, not advance a completeness watermark. A failed/redirected/
non-JSON/missing-resource response must block source promotion.

## Private-source handling and manual reproducible workflow

Use an owner-controlled private folder **outside** the Git repository. Retain
original exports unchanged, along with official download URL, acquisition
timestamp, source resource ID, last-modified metadata if available and original
file hash. Do not commit, publish, email or log raw exports, whose records may
include names, phone numbers and addresses.

Acquire the exact Construction Discharge Facility Information, Inspections,
Violations and Enforcement Actions resource exports from the official catalog.
The offline review tools deliberately do not download them, and never request
credentials, bypass the original hosting controls, or scrape reports.

Use separate original facility exports from two genuinely different capture
dates for longitudinal differences:

```bash
python -m constructionsight.smarts_source_review_cli \
  --county Riverside \
  --previous /private/smarts/facilities-older.csv \
  --current /private/smarts/facilities-newer.csv \
  --inspections /private/smarts/inspections.csv \
  --violations /private/smarts/violations.csv \
  --enforcement /private/smarts/enforcement.csv
```

To review San Bernardino separately, change the county and use the same
retained full-source files as inputs. The implementation accepts only exact
spellings `San Bernardino` and `Riverside`. The reviewed construction-facility
rows are scoped by `SITE_COUNTY`; other datasets by `PLACE_COUNTY`.

If only the source changes need review, omit `--inspections`, `--violations`
and `--enforcement`. Individual entry points are
`constructionsight-smarts-snapshot-diff`,
`constructionsight-smarts-inspections`,
`constructionsight-smarts-compliance`, and
`constructionsight-smarts-source-review` after package installation.

Every output includes original file SHA-256 digests. The output is a bounded
**non-contact review preview**: preview lists are not complete change ledgers.
Regulatory observations, even when linked with exact source identifiers, do
not independently certify project commencement, safety/security needs or
an authorized customer bid request.

## Fail-closed behavior and known limits

- Retained CSV source files are capped at 128 MiB and 250,000 rows apiece,
  matching the current published facility/inspection/compliance file scale,
  but this is not guaranteed for later publications. Reject oversized files.
- Duplicate source identities or source alias drift invalidate a facility
  snapshot. Unmatched inspection/compliance records are counted, not assumed
  to reference a project; conflicting aliases never create positive links.
- Only rows whose `PERMIT_TYPE` begins with `Construction` (case-insensitive) pass
  the inspection/compliance program gate. Different/unknown vocabulary is
  *not* inferred as construction and requires manual schema review.
- Regulatory dates are source-reported. Unparseable/missing dates are retained
  as unverified, not fabricated.
- A missing source identity from a later file is
  `missing_from_new` **not** deletion, expiration or physical completion.
- CSV cell values are strings; their canonical hashes are intentionally
  not treated as identical to the typed CKAN JSON semantic hashes.
- Differences do not prove completeness, freshness, stable pagination,
  licensing conditions, or change-feed monotonicity.
- No source records or personal contact fields are persisted by these
  offline commands, and no new source-specific application schema is created.
  The owner-controlled raw CSV files are retained externally.
- Summaries cannot authorize outreach, source maturity promotion, watchlist
  alerts, graph/parcel joins, price quotes, proposals or bids.

## Quality and deployment boundaries

The SMARTS development-specific GitHub workflow
`.github/workflows/smarts-dev-ci.yml` runs focused SMARTS regression tests,
repository Ruff checks, strict Mypy, and the full regression suite on Python
3.11 and 3.12. Evaluate each run at its **exact SHA**, never infer a later
head is certified by an earlier passing check.

Remaining promotion gates:

1. Retain and hash actual official source files from separate publication
   periods, with acquisition timestamps and source-use governance clearance.
2. Verify published schema and filter vocabulary against real-world records,
   explicitly quantify missing/ambiguous records and county coverage.
3. Implement a reviewed, versioned, atomic source snapshot store with
   checkpoint/backups, completeness reconciliation and crash recovery.
4. Design non-mutating links to official assessor parcels, city planning,
   building permits/inspections, CEQA and contractors, with accepted/rejected
   evidence and reproducible human-review state.
5. Wire a **read-only reviewed** source-health/candidate projection into the
   approved desktop GUI without changing its layout or enabling network polling,
   lead promotion, automatic outreach or bids.
6. Obtain a new production-specific assurance/certification pass and
   separately authorize rollout. The development PR does not merge itself.


## Local operator: read-only SMARTS evidence status

An explicit SMARTS evidence journal can now be inspected from the existing
**Sources & Collection** desktop view. This adds a distinct observation
inventory, not a third construction-permit family or a merged project row.
It does not change the approved desktop layout.

Start with an existing ConstructionSight operator database and an existing
owner-only SMARTS evidence journal outside the source checkout:

```bash
constructionsight-operator \
  --database /private/constructionsight.sqlite3 \
  --smarts-journal /private/smarts/evidence.sqlite3
```

The optional same-origin loopback endpoint `GET /api/smarts-status` returns
only aggregate counts of captured observations, source-scoped identities and
semantic version events. The journal verifier runs inside a noncreating,
SQLite read-only transaction; it checks retained response bytes, semantic
hashes, event transitions, schema and immutability triggers. A missing,
incompatible, or altered journal returns a generic unavailable response
without making repairs, copying raw records or leaking private contact fields.
Without `--smarts-journal`, the panel explicitly shows *unconfigured*
and zero observations.

The dashboard never opens public SMARTS APIs, schedules collection, alters
the evidence journal or promotes its rows into the ConstructionSight project
database. It cannot claim publication freshness, two-county completeness,
parcel correctness, verified active construction, lead suitability, outreach
or bidding authority. The journal must first be populated through separately
authorized `constructionsight-smarts-collect` or exact-record capture. No
new background ingest or production permission is implied.


The same Sources & Collection panel now separately accepts the complete offline
facility-history ledger. To show **both** independent sources of verified
private evidence, pass both optional paths when opening the operator:

```bash
constructionsight-operator --database /private/constructionsight.sqlite3 \
  --smarts-journal /private/smarts/evidence.sqlite3 \
  --smarts-snapshot-history /private/smarts/facility-history.sqlite3
```

The local-only `GET /api/smarts-status` reads both stores without creating or
mutating either. A missing, altered, insecure, or incompatible configured
store fails closed. The screen shows source identity/observation/version counts
for exact API records separately from CSV snapshot/source-row/change-candidate
counts. Neither count indicates complete public coverage, confirmed
construction activity, matching to a specific parcel, or eligibility for
outreach or bidding. This is a read-only status link, not ingestion into the
main product database.

**Operational release remains gated** on independently checked publisher
rights, real live fixture replay, full dataset snapshot reconciliation,
a permitted recurring collection strategy, complete versioned storage and
reviewed cross-source parcel/project identity connections.

## Append-only offline SMARTS CSV snapshot history (development integration)

`constructionsight-smarts-snapshot-history` now stores source-provided
**original facility CSV bytes** alongside all selected-county source identities,
source-row SHA-256 digests and deterministic candidate-change events in one
separate, owner-only SQLite ledger. This is independent of the exact-record
SMARTS API journal, and neither database is the project/permit database.

First, manually acquire the **complete original official facility CSV** through
an approved source process and place it outside the Git checkout. Restrict the
original file and its parent directory to the owner (mode `0600` file and
`0700` directory), then explicitly capture one county:

```bash
constructionsight-smarts-snapshot-history --record \
  --ledger /private/smarts/facility-history.sqlite3 \
  --csv /private/smarts/facilities-2026-10-12.csv \
  --county Riverside --retain-evidence
```

Repeat with `--county "San Bernardino"` for the second jurisdiction.
A subsequent independently acquired full official CSV can be recorded with the
same command and ledger. An optional
`--reported-publication-at 2026-10-02T08:00:00-07:00` stores an
**operator-provided, unverified** agency publication timestamp. The program
separately records the time of local capture in UTC.

```bash
constructionsight-smarts-snapshot-history --verify \
  --ledger /private/smarts/facility-history.sqlite3
```

The verifier opens an existing owner-only SQLite file **read-only**, never
creates or repairs it, and reconstructs every persisted county snapshot and
transition from the original source bytes. The ledger persists the full CSV
once by content hash even when both counties refer to the same export.
A repeated immediately identical file is an idempotent replay, not a new
snapshot or event. A new file with only CKAN `_id` renumbering produces no
semantic-change event. Missing-from-new remains a review candidate, never a
deletion conclusion. The first snapshot is a **baseline** and emits no
supposed newly constructed projects.

The SQLite transactions and immutable append-only tables preserve source
capture, row hashes and change events atomically. Failed imports leave no
partial source snapshot. These original files may include personal contact
data: **never publish the ledger, raw CSVs, SQLite copies, or logs with source
contents**. The CLI prints aggregate counts and hashes only.

The ledger is a development-stage persistence foundation. It is **not**
proof of complete official exports, permitted automated harvesting,
publisher-reported freshness, a current site, a parcel/project match or
commercial lead readiness. The operator must still verify official resource
identity, completeness, publication periods, terms and approval for recurring
operational use. This stage does not add a scheduler, automatic source
downloads, GUI lead promotion, outreach or bids; the approved layout remains
unchanged. Backup/restore disaster-recovery exercises and cross-source
project reconciliation remain future acceptance gates.
