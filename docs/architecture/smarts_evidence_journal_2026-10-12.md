# SMARTS private source-evidence journal (development, opt-in)

This is a *source evidence journal*, not another ConstructionSight project or
opportunity database. It does not change the governed application schema
(`construction_sight_schema_migrations` schema v1), claim a project, or enable
bid/outreach. It is deliberately separate until a reviewed application-schema
migration and source authorization design are approved.

## Scope and privacy

- Live request is **one exact** public California SMARTS facility by county and
  APP_ID or WDID. The same bounded CKAN response used by the intake preview is
  retained; no second network fetch, redirects, broad crawl, or background poll.
- Normal `smarts_intake_cli` calls are **preview-only**. Persistence requires
  *both* `--retain-evidence` and `--journal-path`.
- The body is the decoded JSON HTTP body as yielded by the approved HTTP
  transport (not encrypted TCP packet bytes). Its SHA-256 is checked before
  retention, separately from the canonical row SHA-256 excluding CKAN `_id`.
- **Raw SMARTS responses may contain contact information.** The journal must
  live in an existing owner-only directory (mode 0700 or stricter), and the
  SQLite file is created as 0600 with symlink and ownership checks. Never commit
  it, upload it publicly, or feed its raw columns to lead generation. The CLI
  displays only the existing curated intake preview and a small receipt.
- Use a dedicated private data directory outside the Git working tree.

## Storage contract

SQLite `synchronous=FULL`, rollback journaling, `BEGIN IMMEDIATE`, foreign
key enforcement, versioned application ID, expected column checks and
`quick_check` protect the bounded local source journal. A single transaction
stores an observation's original response bytes and, **only when its semantic
row digest differs from the latest version for the same source**, an append-only
version. Unchanged repeated observations remain independently auditable but
do not advance the version number. Reverting to earlier content **does** create
a new version. Version entries link to a particular observation and carry a
SHA-256 chain to the preceding semantic event.

Source-scoped identifiers are checked in the `smarts_aliases` table. Known
WDID/APP_ID mappings cannot be silently reassigned; a conflicting mapping or
new alias on an existing identity fails closed for human review. Neither
APP_ID nor WDID is promoted into a globally verified project identity.

UPDATE/DELETE triggers reject normal mutations to observations, versions and
aliases. This is an **application-level immutable journal**, not a tamper-proof
external notarization or solution to malicious same-user filesystem access.
A separately secured evidence archive or third-party timestamp is needed for
stronger adversarial assurance.

## Usage — development checkout only

```bash
mkdir -p ~/ConstructionSight-SMARTS-Private
chmod 700 ~/ConstructionSight-SMARTS-Private

python -m constructionsight.smarts_intake_cli \
  --county Riverside --app-id 600752 --execute-live \
  --retain-evidence \
  --journal-path ~/ConstructionSight-SMARTS-Private/source-evidence.sqlite3

# An exact WDID lookup should become a second observation but the same
# semantic version if the source row is still unchanged.
python -m constructionsight.smarts_intake_cli \
  --county Riverside --wdid '8 33C413320' --execute-live \
  --retain-evidence \
  --journal-path ~/ConstructionSight-SMARTS-Private/source-evidence.sqlite3

# Offline integrity check (no network, no raw contact fields in output)
python -m constructionsight.smarts_evidence_ledger \
  --verify ~/ConstructionSight-SMARTS-Private/source-evidence.sqlite3
```

## Bounded, restart-safe roster collection

`constructionsight.smarts_collection` adds a separate private checkpoint file.
This is a deliberate **1–25 exact facility roster**, with a per-invocation
request budget of 1–25. It requires both `--execute-live` and
`--retain-evidence`, and never derives a roster from recent NOI dates. Use a
reviewed JSON file such as:

```json
[
  {"county": "Riverside", "app_id": "600752"},
  {"county": "San Bernardino", "wdid": "8 36C123456"}
]
```

The IDs above illustrate the file shape; verify every actual target before
running. Both the journal and checkpoint must be `.sqlite3` files in an
existing owner-only directory outside the Git checkout. A sample invocation:

```bash
python -m constructionsight.smarts_collection \
  --roster /private/path/reviewed-roster.json --run-id reviewed-sweep-001 \
  --journal-path /private/path/evidence.sqlite3 \
  --checkpoint-path /private/path/collection-checkpoint.sqlite3 \
  --max-requests 5 --execute-live --retain-evidence
```

Each exact lookup must return one row matching the requested county and
identifier. The original bounded response and its digest are committed to the
immutable journal first. Only then is a receipt and the next roster index
committed in the separate checkpoint. On restart, the roster, journal path,
prior receipts, journal digests, and journal structure are verified before any
new request. A changed roster or missing receipt fails closed. A crash between
the two commits repeats that exact lookup; the repeated observation is retained
but an unchanged row does not create another semantic version. Complete runs
do no work when called again with the same run ID. A new explicit run ID
revisits the roster and reports first, changed, and unchanged source rows.
An unfinished run must be resolved before a new run can start.

This reconciles **only the named source IDs**. Missing records, unexpected
aliases, and source identity drift stop the cursor for human review; they do
not become deletion claims. CKAN's `_id` is ignored in the semantic row digest.
The checkpoint may safely lag evidence after a crash, so observed response
counts can exceed completed roster steps. Keep and back up both private files
together; neither is an adversarial tamper-proof store.

**Completeness limit:** recent `NOI_PROCESSED_DATE` filtering cannot capture
all edits, removals, or newly added records. This stage makes no county-wide
coverage claim or high-water advance. A future complete reconciliation needs
an authorized stable snapshot or change feed with documented ordering,
pagination consistency, deletion semantics, a bounded coverage protocol, and
comparison against a prior complete snapshot. Without that evidence, retain
the last known complete coverage state as unknown.

## Not yet provided

- No scheduled polling, full county snapshot, all-record change-feed,
  county-wide watermark, pagination coverage, or published-CSV reconciliation.
- No longitudinal guarantee that source identifiers are never reassigned.
- No downstream schema migration into the ConstructionSight entity/site graph,
  automatic lead readiness promotion, dashboard feed, or outreach.
- No independent government GIS/parcel, planning, permit, inspection or
  construction-groundbreaking verification.
- External commercial-use terms, retention controls, backup recovery, and
  end-to-end operational certification require separate review.

The offline tests cover unchanged repeat, semantic update, reversion,
transport row renumbering, alias collision, mismatched raw evidence,
filesystem restrictions, transaction rollback on failed capture,
SQL UPDATE/DELETE rejection, partial collection failure, restart replay,
source drift, changed rosters, and missing checkpoint receipts. On this
development increment, the strict repository suite passed 2,347 tests,
Ruff passed across `src` and `tests`, and Mypy passed 307 source files.
The new roster collector has not been exercised live; that remains a separate
controlled operational review.
