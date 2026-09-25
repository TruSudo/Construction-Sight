# Concrete runtime blocker corrections — 2026-09-22

This batch implements the owner's direction to correct material operational
failures and establish a private runtime baseline. It does not close the active
ledger, grant release certification, or authorize merge to main.

Starting backend: `ceea88953af6eb39a49717946934d7abe64b59b5` (PR #117).
Starting GUI: `7ceac11e38f79ae315060e1798a8783d0dc96cde` (PR #119).
The 30 changed backend files since the GUI's base were retrieved at the exact
backend commit; their Git blob hashes and full backend tree
`5f69c77b9dbbbda9ef3baf0cf2415d0aaf204f6e` were verified. Backend and GUI changed
path sets do not overlap at that checkpoint.

## Shared backend corrections

- **CS-SR-047, narrow duplicate-verdict identity correction:** two different
  candidates with the same match fingerprint produced the same result ID.
  Persisting the second raised `persisted lead duplicate results are immutable`.
  A versioned full SHA-256 identity now includes candidate attribution, match
  basis, status, unique sorted matched keys and decision rationale. Repeated
  observation timestamps and scores remain non-decisional; old persisted IDs
  stay readable. Repeated match observations no longer create different IDs,
  and changed rationale receives its own verdict identity. This is not complete
  remediation of every derived identity or the durable duplicate-review workflow.
- **First-run initialization:** invoking `constructionsight init-db` from a
  directory without `data/` failed with SQLite's `unable to open database file`.
  The explicit default initialization command now creates that directory.
  This does not introduce implicit schema migration or change explicit target
  paths. The fresh-directory CLI regression checks actual domain tables.
- The existing order-independence mutation witness was updated to the new
  canonical identity. Added focused witnesses for candidate attribution,
  rationale and first-run initialization; all four directly affected mutations
  were killed locally in the pinned Python 3.12 environment.

## GUI runtime corrections and trial

On the GUI integration branch, source/workflow/parcel schema compatibility is
checked without reading rows or changing the database, before serving requests
and on health checks. Empty or obsolete SQLite schemas no longer appear healthy.
Missing-table, renamed-column and post-startup schema-drift regressions pass.
This addresses the GUI startup exposure under CS-SR-056; repository-wide schema
versioning and migrations remain open.

The one-command trial uses the existing hashed dependency lock, package build,
CSV replay verifier, authorized CEQAnet write-plan application, SQLite database
and loopback GUI. It retains the two July 12, 2026 public Cabazon CSV observations
with their source date, URL, hash and geographic limitations. It does not
represent those observations as current jobs or create commercial workflows.

## Validation boundary

Local validation of the integrated worktree: **2,014 pytest tests pass**, Ruff
passes, strict mypy passes on 273 source files, compilation and diff hygiene
pass. A wheel was installed with the repository's hashed Python 3.12 dependency
lock and `pip check` passed. The complete trial helper successfully installed,
verified retained evidence, initialized, applied four operations and started the
installed operator executable. Fifteen HTTP checks passed across bundled assets,
health, source search/counties, map footprint, timeline, candidate preview,
parcel explanation, entity links, workflow reads and restart. All initial HTTP
reads left the database hash unchanged. An explicitly confirmed local docket
stage and separate-process readback retained one unapproved entry; restart
preserved two sources and zero commercial workflows.

These are local diagnostic results for the changed worktree, not final-head CI
or assurance artifacts. The raw trial HTTP result is retained on the GUI branch.
Cloud Browser refused the loopback URL (`ERR_BLOCKED_BY_CLIENT`), so visual and
interactive browser acceptance remains a real user test-drive step. Fresh
public-source collection was not exercised in this retained-data trial.
CS-SR-045/046/048/049/050/052/053/056 and the other active assurance findings are
not represented as resolved by a read-only trial. The 75-record active ledger
remains unchanged; PRs #117/#119 remain draft.
