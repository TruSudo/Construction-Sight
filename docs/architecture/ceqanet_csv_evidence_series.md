# CEQAnet Governed CSV Evidence Series

## Purpose

ConstructionSight maintains an immutable, independently verifiable ledger for
the bounded official-CSV observations required by the current CEQAnet access
policy.

The ledger does not make a request, promote CEQAnet, or authorize production
recurring execution. It governs separately authorized evidence requests and
preserves whether the evidence is still collecting, halted, or sufficient for a
separate maturity review.

## Artifact layers

Each governed request produces one complete
`ceqanet_csv_evidence_execution.v1` artifact containing:

- the exact policy digest;
- the explicit authorization timestamp and UTC date;
- the one-request assertion;
- the policy timeout and maximum body size;
- the complete existing live-execution response envelope;
- the independently recomputed live verification; and
- a digest over the complete policy-bound artifact.

The series stores compact `ceqanet_csv_evidence_observation.v1` records. Each
record binds the repo-relative execution-artifact reference, policy execution
digest, live execution digest, request identity, UTC date, export scope,
response/body identity, inspection digest, verification findings, success
classification, and access-control halt state.

The `ceqanet_csv_evidence_series.v1` snapshot binds the ordered observations,
append-only sequence and predecessor digest, counts, successful dates/scopes,
policy criteria, current status, halt metadata, next gate, and non-authority
assertions. Every nonempty snapshot's predecessor is deterministically
recomputed from the prior observation prefix, making forks visible.

## Pre-request gate

The governed executor makes no request until it has:

1. recomputed the policy verification from the current registry and complete
   canonical evidence chain;
2. independently rebuilt and verified the current series from every referenced
   evidence-execution artifact;
3. confirmed that the policy is effective for the current UTC date;
4. confirmed that the series status is `collecting`;
5. confirmed that no execution already exists for the current UTC date;
6. confirmed that authorization follows the current append-only series head;
7. confirmed that normalized row retention is between 0 and 1,000;
8. confirmed that the requested export scope is allowed;
9. received explicit `--execute-live` authorization;
10. atomically reserved the policy, series, request, and trusted UTC-date allowance in the ConstructionSight-owned durable consumption store; and
11. confirmed that the output path is distinct, available, and writable enough
   to create its parent directory.

The request then uses the policy's 20-second timeout and 10,000,000-byte maximum
body. The existing bounded executor performs exactly one GET and zero retries. An
exact committed replay returns the retained evidence execution without a second
GET. A concurrent, conflicting, failed, unavailable-store, or crash-indeterminate
allowance cannot execute automatically.

## Series rules

The ledger rejects:

- absolute, traversal-capable, backslash, or noncanonical artifact references;
- changed policy, evidence-execution, live-execution, observation, or series
  digests;
- a stored policy or live verification that differs from recomputation;
- authorization after the recorded request;
- observations outside the policy window;
- disallowed export scopes;
- duplicate artifact, policy-execution, live-execution, or observation identity;
- more than one execution on any UTC date; and
- any observation recorded after an access-control halt or maturity readiness;
- a nonempty snapshot without its deterministically recomputed predecessor; and
- a request authorization that does not follow the current series head.

HTTP 401, 403, 407, 429, or 451 produces a terminal `halted` series. Other
independently verified failures remain in the ledger but do not count as
successful observations.

## Status boundary

The only statuses are:

- `collecting`: more governed evidence is required;
- `halted`: an access-control response ended collection without bypass; and
- `ready_for_maturity_review`: all policy evidence criteria are satisfied.

Readiness requires at least four successful observations, at least three
successful UTC dates, and both project and document export scopes. Because the
policy allows only one execution per UTC day, four new successful observations
necessarily span four UTC dates.

Readiness is report-only. Source promotion and production recurring execution
remain fixed to `false`.

## Canonical baseline

The pre-execution baseline is:

- `evidence/source_verification/ceqanet_csv_evidence_series_2026-07-14.json`;
- `evidence/source_verification/ceqanet_csv_evidence_series_verification_2026-07-14.json`;
- `docs/audits/ceqanet_csv_evidence_series_2026-07-14.md`; and
- series digest
  `b2a18770ec5ca28dfb907ce74b0b5ba120e6bb028ee35e3acd5188d42c182634`.

It contains zero observations, is independently verified, and has status
`collecting`. Creating it made no network request.

## Current series head

Sequence 1 adds the first governed observation:

- project export for SCH `2026030377`;
- authorized and executed on UTC `2026-07-14`;
- one HTTP 200 GET with zero retries;
- complete 7,832-byte Windows-1252 body retained;
- 2 parsed source rows;
- evidence-execution digest
  `57c2c3a64f65f6cd7ca8e512c862d02fe92b04fcaa7cc1bb6eaeb7b091857f10`;
- predecessor series digest
  `b2a18770ec5ca28dfb907ce74b0b5ba120e6bb028ee35e3acd5188d42c182634`;
- current series digest
  `a6f6e548d675ee9716822fef87cc02d8a4d169f16ab151bae0f297321b8c07df`;
  and
- independent live and series verification with 0 findings.

The current status remains `collecting`. No further execution is permitted on
UTC 2026-07-14.

## Operator commands

`constructionsight-ceqanet-evidence-series build` builds a series from the
canonical policy chain and zero or more policy-bound execution artifacts.

`constructionsight-ceqanet-evidence-series verify` independently rebuilds and
verifies the same snapshot.

`constructionsight-ceqanet-evidence-series execute` performs one request only
after all pre-request gates pass and the operator supplies
`--execute-live`. Prior evidence-execution paths and their repo-relative
artifact references must be supplied in matching order.

The build and verify commands are offline. The execute command is the only
network-capable command in this module.

## Next gate

The next action is one separately authorized document CSV evidence execution no
earlier than UTC 2026-07-15, provided that date has no series observation and the
policy remains current. Its complete artifact must be committed, independently
verified into sequence 2, and reviewed before any later day's execution.

Three additional successful observations on later unused UTC dates are still
required. At least one must cover the document export scope. Source promotion,
scheduling, and production authority remain false.
