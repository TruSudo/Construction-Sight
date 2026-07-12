# CEQAnet Recurring-Run Governance

## Purpose

ConstructionSight separates a repeatable source query from autonomous scheduling. The CEQAnet recurring-run boundary defines and verifies exact read-only listing attempts without claiming that the canonical source is currently verified, production-ready, or continuously collected.

The boundary reuses the existing CEQAnet listing planner and bounded GET executor. It does not create a parallel network path, download CEQA documents, parse detail pages, mutate persistence, schedule background work, or send outreach.

## Artifact sequence

The governed sequence is:

```text
current source registry
+ current source-verification checklist
+ reviewed access assumptions
+ stable query template
        |
        v
CeqanetRecurringRunDefinition
        |
        + exact received/posted date window
        v
CeqanetRecurringRunManifest
        |
        + explicit per-attempt --execute-live authorization
        + current registry/checklist revalidation
        v
CeqanetRecurringRunExecution
        |
        v
CeqanetRecurringRunVerification
```

All four artifacts are schema-versioned JSON models.

## Definition readiness

A definition may be created for an unverified source, but its readiness remains `blocked`. It becomes `ready_for_manual_execution` only when all of the following are true:

- the selected registry source is CEQAnet;
- its registry status is `verified`;
- public entry behavior is observed;
- query behavior is observed;
- result-list behavior is observed;
- detail-page behavior is observed;
- terms review is observed;
- the operator affirmatively records that no access barrier was observed;
- at least one evidence reference is preserved; and
- the reviewed access assumptions contain no login, captcha, robots, terms, or paywall blocker.

A reachable URL or guarded executor is not enough to satisfy this gate.

## Registry and execution identities

The canonical registry currently identifies the public source as `https://ceqanet.opr.ca.gov/`. The verified search contract and bounded executor use `https://ceqanet.lci.ca.gov/`.

The run definition preserves both identities. It does not silently replace the registry URL with the execution host. The registry URL must use an approved official HTTPS host, and the execution base must be exactly the approved `ceqanet.lci.ca.gov` host root.

## Query contract

The stable query template supports only filters represented by the CEQAnet advanced-search contract:

- county;
- document type;
- lead agency;
- received-date window;
- posted/review-date window;
- high-signal document-type selection;
- bounded page size; and
- bounded page count.

Free-text terms are rejected. The prior listing query model exposed `text_terms` as a bounding signal even though the CEQAnet request builder did not transmit it. Rejecting that input prevents a run from claiming a filter that the public request did not apply.

Page size remains limited to 100 and page count to 10. Every manifest must contain at least one transmitted bounding filter.

## Deterministic identity

A definition digest covers approval-significant content, including:

- source identity;
- complete registry digest;
- selected checklist-row digest;
- evidence references;
- registry and checklist status;
- access assumptions;
- query template; and
- timeout and body-retention bounds.

A manifest adds the exact inclusive date window and produces a deterministic run ID and manifest digest. Rebuilding the same manifest from the same definition and window produces the same identities.

An execution attempt ID is derived from the run ID, manifest digest, and positive attempt sequence. Attempt-sequence uniqueness remains operator-controlled until a dedicated persisted attempt ledger is introduced.

## Stale-evidence protection

Before any network request, execution must receive the current source registry and current checklist report. It rejects the attempt when:

- the complete registry digest changed;
- the selected source no longer binds to the checklist row;
- source name, URL, platform, or verification status changed;
- checklist status or evidence references changed;
- the selected checklist-row digest changed;
- current evidence is incomplete; or
- current access assumptions now contain a blocker.

Artifact integrity and current authorization are separate controls. A historically intact definition is not sufficient when the current source authority has changed.

## Execution boundary

Each live attempt requires explicit `--execute-live` authorization. The execution service then:

1. verifies definition and manifest digests;
2. verifies all definition/manifest semantic fields;
3. revalidates current registry and checklist evidence;
4. evaluates lawful-access assumptions;
5. rebuilds the exact listing query from the manifest;
6. confirms the official CEQAnet `/Search` target;
7. invokes the existing bounded read-only listing executor; and
8. records a schema-versioned execution envelope.

The execution boundary authorizes no persistence. Existing parsing, detail retrieval, archive, write planning, and persistence-apply tools remain separate governed stages.

## Verification boundary

Verification checks:

- definition, manifest, run, and attempt identities;
- current registry and checklist authorization when supplied;
- exact query agreement;
- request count against `max_pages`;
- successful and failed response-count arithmetic;
- unique in-range page numbers;
- GET-only requests;
- execution flags;
- request and final host boundaries;
- `/Search` request path;
- retained-body size and truncation consistency;
- top-level network-execution truth; and
- absence of persistence mutation.

Verification failures are explicit findings and produce a nonzero CLI exit.

## Operator commands

The command surface is:

```text
constructionsight-ceqanet-recurring-run build-definition
constructionsight-ceqanet-recurring-run build-manifest
constructionsight-ceqanet-recurring-run execute
constructionsight-ceqanet-recurring-run verify
```

`execute` and `verify` require the current registry and checklist, not only previously generated artifacts.

## Current maturity

The canonical CEQAnet registry record remains unverified. Therefore, a definition produced from current canonical repository data remains blocked and cannot execute through this boundary.

This implementation proves the governance and replay contract. It does not establish verified usable coverage, recurring production operation, autonomous scheduling, or ingestion completeness.

## Entry conditions for later recurring operation

Background scheduling or automated downstream processing requires separate governed work covering:

- reviewed and applied source verification;
- persisted attempt identity and duplicate-attempt rejection;
- schedule ownership and timezone semantics;
- nonoverlapping or explicitly overlapping window policy;
- retry and backoff policy;
- archive and replay retention;
- source-change detection;
- operator notification and failure escalation;
- parsing and persistence handoff approval; and
- production observability.
