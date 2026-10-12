# SMARTS → source-neutral intake → site-resolution integration (development)

Status as of 2026-10-12: **development preview only; no graph writes, scheduler,
source maturity promotion, dashboard feed, or approved production collection**.

Development update: an explicit opt-in, private SQLite SMARTS source-evidence journal
now retains bounded exact-record response bodies and append-only source versions;
see `smarts_evidence_journal_2026-10-12.md`. This sidecar never writes the
application graph or authorizes scheduled production collection. Full repository
quality checks and live retained capture were pending when that journal stage
was first documented. The user subsequently reported a successful controlled
live evidence-retention replay and integrity check; exact terminal totals were
not provided here and are not asserted.

A further development stage adds an explicit 1–25 facility roster collector
with a separate restart checkpoint. It revisits only named exact source IDs,
reports semantic source-row changes via the evidence journal, and advances its
cursor only after evidence is committed. It does not claim complete source
coverage or use recent NOI dates as a change feed; operational details and
limitations are in `smarts_evidence_journal_2026-10-12.md`.
Its new offline tests and the full strict repository suite passed (2,347 tests);
Ruff and Mypy passed. The roster collector itself has not been run live.

## What was integrated

On development branch `agent/smarts-source-neutral-integration-2026-10-12`
the public California SMARTS DataStore client (from draft PR #209) is now
connected to ConstructionSight's **existing**
`UniversalIntakeRecord`/`IntakeEvidenceRef` and `SiteResolutionInput`/
`SiteResolutionResult` contracts. There is no new competing project database.

Modules:
- `smarts_api.py`: exact facility lookup by APP_ID or WDID in one approved
  county; one or two bounded returned rows, fail if zero or ambiguous. A
  source-supplied `APP_ID='NA'` is never accepted as an exact app ID.
- `smarts_intake_bridge.py`: canonical row fingerprint excluding the
  transient CKAN `_id`; source-claimed title/address/developer facts; optional
  WGS84 coordinate hint; evidence reference with row SHA-256 and original
  response SHA-256; a site-resolution **candidate**, not a verified parcel.
  No raw contact phone/email is copied into the output.
- `smarts_intake_cli.py`: one exact record -> complete reviewable intake
  and site-resolution preview (human review).
- `smarts_recent_review_cli.py`: up to five recent NOI candidates ->
  explicitly identified facility records -> compact review report. At most
  six requests (one recent SQL query + five exact record lookups).
- `tests/test_smarts_intake_bridge.py` and
  `tests/test_smarts_recent_review_cli.py`: offline mocked API/identity
  and source-neutral integration regression cases.

The separate five-case research evidence fixture (#211/#210) has been
copied onto this integration branch for one coordinated future review.
Its associations are **candidate relationships** and are deliberately
not promoted to verified project-level joins.

## Verified observations vs remaining uncertainties

A user-operated Linux terminal confirmed anonymous GET access on
2026-10-12 to the California DataStore for two counties:

- San Bernardino: 10,428 county-matching source records, with 698
  regulatory status `Active` in a separate SQL status query.
- Riverside: 13,856 matching source records, with 918 regulatory status
  `Active`.

The user's SQL query also returned recent dated records (and one
`APP_ID='NA'`). These are **user-run observed results**, not independent
full source captures. Do not treat any totals as active construction
projects, stable unique sites, or fresh statewide completeness proof.

## Usage (only after checking out this branch and reinstalling package)

```bash
python -m pytest -q tests/test_smarts_api.py tests/test_smarts_intake_bridge.py tests/test_smarts_recent_review_cli.py tests/test_smarts_five_project_pilot.py
python -m ruff check src/constructionsight/smarts_api.py src/constructionsight/smarts_intake_bridge.py src/constructionsight/smarts_intake_cli.py src/constructionsight/smarts_recent_review_cli.py tests/test_smarts_api.py tests/test_smarts_intake_bridge.py tests/test_smarts_recent_review_cli.py tests/test_smarts_five_project_pilot.py
python -m mypy src/constructionsight/smarts_api.py src/constructionsight/smarts_intake_bridge.py src/constructionsight/smarts_intake_cli.py src/constructionsight/smarts_recent_review_cli.py
```

One project (SMARTS APP_ID 600752, not automatically confirmed as the
Northern Gateway warehouse subproject):

```bash
constructionsight-smarts-preview --county Riverside --app-id 600752 --execute-live
```

Bounded recent active-regulatory review:

```bash
constructionsight-smarts-review --county 'San Bernardino' --limit 3 --execute-live
constructionsight-smarts-review --county Riverside --limit 3 --execute-live
```

If scripts have not been installed, use
`python -m constructionsight.smarts_intake_cli` or
`python -m constructionsight.smarts_recent_review_cli`.

This integration makes **zero automatic outbound contact**. Review results
may include source-provided site locations, but not underlying personal
emails/phones. No default background network execution occurs.

## Safety / identity conditions

- The `_id` DataStore position is a transport identifier, not stable
  source, permit, parcel, or project identity.
- WDID is preferred as a source-scoped candidate key; numeric APP_ID is
  a fallback. Their uniqueness and lifetime must be independently verified
  before they can anchor durable persistence.
- Missing identifiers are surfaced as an explicit blocker, not assigned
  fabricated stable IDs. A record with no usable location resolves to
  `UNRESOLVED`, not a fake parcel.
- Coordinates are source-claimed and accepted only as possible WGS84
  points within a conservative California envelope. They must be verified
  against official GIS/parcels before an exact match.
- Source-reported commencement and SMARTS regulatory Active do not
  establish physical groundbreaking, specific project phase, or unfilled
  security demand.
- Existing site-resolution confidence/strength only indicates evidence
  within one observation, **not independently corroborated site identity**.
- CKAN SQL recency sorts by processing date; it does not guarantee full
  chronology. A `NOI_PROCESSED_DATE` may reflect an administrative update.
- The public catalog describes an open resource; commercial license and
  recurring collection conditions remain subject to source-specific review.
- Full historical/no-loss capture is not proven by these small API queries.

## Remaining operational integration gates

1. Run the entire targeted suite and certification on a controlled checkout;
   resolve any failures, including Python 3.11/3.12 strict typing.
2. Execute one exact-record public preview from a controlled Linux environment,
   retain response and derived evidence digests, verify actual schema and
   county query behavior; report real failure if source access is denied.
3. Reconcile exact WDID/APP_ID against the five independent official
   planning/CEQA project cases, retaining rejected links and contradictions.
4. Verify the new **opt-in private evidence journal and source-scoped version
   ledger** on the exact commit. Then design reviewed integration with governed
   application persistence, restart-safe polling/checkpoint/reconciliation, and
   complete snapshot validation. No high-water advance until a complete source
   snapshot is validated; date filtering alone cannot guarantee all updates.
5. Establish source-specific access/commercial-use terms and production
   rate limits, automated source freshness, alerting, and weekly authoritative
   CSV completeness checks.
6. Only once #204 and #207 acceptance evidence exists, wire the read-only
   source-health and candidate review data into the approved desktop GUI,
   preserving the charcoal/amber design and manual outreach/bid gates.

Draft PRs: #209 upstream SMARTS API, #211 research-only fixture, this
integration PR as consolidation. All target the integration development
branch, not `main`. Never merge to `main` without explicit authorization.
