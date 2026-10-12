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

## Not yet provided

- No scheduled polling, full county snapshot, all-record change-feed,
  checkpoint/watermark, pagination coverage, or published-CSV reconciliation.
- No longitudinal guarantee that source identifiers are never reassigned.
- No downstream schema migration into the ConstructionSight entity/site graph,
  automatic lead readiness promotion, dashboard feed, or outreach.
- No independent government GIS/parcel, planning, permit, inspection or
  construction-groundbreaking verification.
- External commercial-use terms, retention controls, backup recovery, and
  end-to-end operational certification require separate review.

The unit-test suite covers unchanged repeat, semantic update, reversion,
transport row renumbering, alias collision, mismatched raw evidence,
filesystem restrictions, transaction rollback on failed capture, and
SQL UPDATE/DELETE rejection. The complete repository test suite and live
opt-in capture must still be run on the exact development commit before
this stage can be considered verified.
