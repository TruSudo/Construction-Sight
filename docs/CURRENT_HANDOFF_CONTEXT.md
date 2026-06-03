# ConstructionSight Current Handoff Context

## Purpose

This document preserves current ConstructionSight project context for continuing development across chats.

## Project Identity

ConstructionSight is a lawful public-record construction intelligence platform focused first on:

- San Bernardino County, California
- Riverside County, California
- incorporated cities inside both counties
- unincorporated county areas

The product goal is to discover, verify, normalize, store, analyze, and eventually visualize public construction, planning, entitlement, CEQA, permit, contractor, parcel, and agenda data.

## Legal Boundary

Use only lawful public access.

Do not bypass authentication, captchas, rate limits, access controls, paywalls, robots restrictions, or terms-of-service limits.

No credential misuse.

No hidden/private data.

No scraping behind logins unless the user lawfully provides credentials and the site terms permit it.

## User Workflow Rules

The user prefers batch-mode project development through GitHub commits.

Continue through the current phase without asking for confirmation between ordinary steps.

Make commits directly to `main` only when each step is coherent and tested by added/updated tests.

Do not stop for ordinary implementation choices.

Stop only if:

1. a test failure occurs,
2. a safety/legal/access-boundary issue appears,
3. a destructive change is required,
4. repository state becomes dirty or conflicted,
5. a major architectural decision is unavoidable,
6. local validation from the user is required.

Expose every defect, fix it before proceeding, and record validation checkpoints.

## Current Validated State

The latest fully validated local state reported by the user was:

```text
84 passed in 0.94s
Adapter Contract Audit: Passed True
Source Adapter Coverage Audit: Passed True
Adapter Dry Run: success, zero records, zero errors
working tree clean
```

At that point, the repository was up to date through:

```text
f805e98897992ccc27fe5f36684a7efd0107d31a  Add CEQAnet live discovery tests
```

Additional commits after that may need local validation.

## Completion Status

Approximate overall completion as full product:

```text
30% overall
75–85% backend foundation / architecture
80–90% data model + persistence foundation
75–85% adapter framework
0–5% live data ingestion
0–10% intelligence/scoring layer
0–5% GUI / installer / desktop polish
20–30% production readiness
```

## Completed Phases

### Phase 1 — Project Foundation

Complete.

Includes Python project structure, package layout, CLI entrypoint, testing setup, source registry seed, and database initialization path.

### Phase 2 — Source Registry

Complete.

Source registry supports public sources with jurisdiction, county/state, source name, source type, platform family, URL, record categories, search method, difficulty, update frequency, confidence, verification status, and provenance notes.

Current seed sources:

```text
CEQAnet State Clearinghouse
CSLB Public License Search
San Bernardino County EZOP
Riverside County PLUS Online
```

### Phase 3 — Source Verification

Complete baseline.

Verifier can check source reachability, likely platform family, public search availability, login requirement, and can persist verification results.

Important correction already made:

```text
Riverside PLUS was corrected to:
https://rivcoplus.org/

and classified as:
tyler_energov
```

### Phase 4 — Domain Model and Persistence

Complete foundation.

Normalized domain models include:

```text
Site
Entity
PermitRecord
PlanningCaseRecord
CeqaRecord
AgendaItemRecord
DocumentRecord
RelationshipRecord
Provenance
confidence bands
enums for roles, relationships, categories, states
```

Validated persistence tables:

```text
domain_sites
domain_entities
domain_permits
domain_planning_cases
domain_ceqa_records
domain_agenda_items
domain_documents
domain_relationships
```

Validated stores:

```text
SiteStore
EntityStore
PermitStore
PlanningCaseStore
CeqaStore
AgendaItemStore
DocumentStore
RelationshipStore
```

### Phase 5 — Adapter Framework and Contracts

Complete.

Includes:

```text
src/constructionsight/adapters/base.py
src/constructionsight/adapters/stub.py
src/constructionsight/adapters/registry.py
src/constructionsight/adapters/runner.py
src/constructionsight/adapters/specs.py
src/constructionsight/adapters/audit.py
src/constructionsight/adapters/coverage.py
src/constructionsight/adapters/__init__.py
```

CLI commands added:

```bash
constructionsight audit-adapters
constructionsight audit-source-coverage data/source_registry.seed.json
constructionsight dry-run-adapters data/source_registry.seed.json --limit 2
```

Validated adapter families:

```text
ceqanet
cslb
accela_aca
tyler_energov
granicus_legistar
civicplus_primegov
laserfiche
custom_report
```

## Current Phase

### Phase 6 — First Live Read-Only Adapters

Current active source family: CEQAnet.

CEQAnet is the first adapter because it is a low-friction, high-value public source for early construction intelligence.

## CEQAnet Current State

CEQAnet has been promoted from placeholder to:

```text
contract_ready
```

It is not yet:

```text
live_read_only
```

Implemented and validated:

```text
src/constructionsight/adapters/ceqanet.py
tests/test_ceqanet_adapter.py
```

Capabilities currently implemented:

- fixture-backed parsing of CEQAnet-like rows
- normalization into `CeqaRecord`
- provenance preservation
- high-signal CEQA document classification through existing `CeqaRecord` logic
- adapter runner integration
- default registry wiring for CEQAnet
- adapter-family spec updated to `CONTRACT_READY`
- mocked live public-search discovery tests

CEQAnet public advanced search URL:

```text
https://ceqanet.lci.ca.gov/Search/Advanced
```

Public discovery detects:

- page reachable
- advanced search available
- SCH number field hints
- document type field hints
- date field hints
- lead/public agency field hints

Current boundary:

```text
Discovery only. No live record harvesting yet.
```

## Most Recent Work In Progress

A CEQAnet discovery CLI command was added:

```bash
constructionsight discover-ceqanet
```

Commit added:

```text
9b5542fc999eb8bfd548632acfecc103ddfcbd92  Add CEQAnet discovery CLI command
```

A planned test file for this command was attempted but did not land before the handoff:

```text
tests/test_cli_ceqanet_discovery.py
```

Next immediate step:

1. Confirm whether `tests/test_cli_ceqanet_discovery.py` exists.
2. If not, add it.
3. Run/ask user to run local validation.

Expected next test count after adding CLI discovery tests should likely be:

```text
86 passed
```

## GUI / Map / Relationship Memory Requirement

The user explicitly wants ConstructionSight to eventually include a polished GUI with a map interface.

This requirement is recorded in:

```text
docs/PRODUCT_REQUIREMENTS_GUI_MAP_AND_RELATIONSHIP_MEMORY.md
```

Core GUI requirements:

- map interface for San Bernardino County and Riverside County
- display jobsites
- show active, near-active, early-stage, inactive, completed, stalled, or unknown status
- include general contractors involved
- include developer/owner entities
- include applicants when known
- include project/permit/CEQA/planning/agenda/document evidence
- include confidence and provenance

Entity memory requirements:

- developer profiles
- general contractor profiles
- contractor/director/entity memory
- active and historical projects
- jurisdictions where active
- relationships between developers, GCs, permits, projects, sites, CEQA records, agenda items, documents, and parcels

Non-negotiable integrity rule:

No developer, general contractor, owner, applicant, or relationship may be asserted as fact without stored provenance.

The system must distinguish:

```text
verified fact
public-record text
normalized inference
probabilistic relationship
unresolved ambiguity
```

## Next Recommended Steps

Continue Phase 6 in this order:

1. Finish `discover-ceqanet` CLI tests.
2. Locally validate expected 86 tests.
3. Record Phase 6 CEQAnet discovery CLI validation.
4. Add a controlled CEQAnet live smoke command or fixture-based query interface.
5. Only then consider conservative live read-only CEQAnet record listing.
6. Do not implement Accela/Tyler live scraping yet.

## Standard Local Validation Command

Use:

```bash
cd ~/workspace/projects/Construction-Sight/Construction-Sight
git pull origin main

source .venv/bin/activate
python -m pytest
constructionsight audit-adapters
constructionsight audit-source-coverage data/source_registry.seed.json
constructionsight dry-run-adapters data/source_registry.seed.json --limit 2
git status
```

After the CEQAnet discovery CLI command is validated, also run:

```bash
constructionsight discover-ceqanet
```

## Current Product Reality

ConstructionSight currently has a strong backend foundation, normalized data model, persistence layer, adapter framework, and first CEQAnet adapter contract/discovery path.

It does not yet have:

- live CEQAnet record ingestion
- live CSLB lookup
- Accela extraction
- Tyler EnerGov extraction
- agenda/PDF ingestion
- Laserfiche crawling
- scoring layer
- GUI
- installer
- desktop icon/logo integration
- map view
- CRM/export lead queue

## Important Doctrine for Future Work

Do not let live adapters become one-off scrapers.

Keep the adapter-family architecture.

Every live adapter must have:

- access review
- rate-limit behavior
- provenance capture
- normalized output tests
- dry-run behavior
- fixture tests
- no bypass behavior

## Handoff Instruction

When a new chat begins, continue from this document and the repository state.

Do not re-plan from scratch.

Resume by checking `git status`, pulling latest `main`, running tests, and continuing Phase 6 CEQAnet discovery CLI validation.
