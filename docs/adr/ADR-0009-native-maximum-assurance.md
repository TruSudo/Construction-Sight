# ADR-0009: Native Maximum Assurance and honest review classification

- Status: Accepted
- Date: 2026-08-22
- Owners: ConstructionSight maintainers

## Context

ConstructionSight is presently a private, solo-maintained open-source program. A
standing unrelated human reviewer is not available. Requiring one as the only path
to certification would leave the repository permanently blocked without improving
the work actually performed, while calling owner or same-provider review
"independent" would overstate the evidence.

Context-isolated reviews still provide a materially fresh analytical take. Their
value should be preserved without confusing execution independence with an
external source or human approval. The absence of an external source should raise,
not lower, the mandatory standard of care.

## Decision

`native_maximum` is the mandatory baseline. It requires a frozen exact commit and
tree; at least three context-isolated complete Standard reviews within a sealed
repository-wide deep scan; a separate fresh exact-diff scan; a separate fresh
adversarial invariant/attack-path pass; blind union of every candidate before
adjudication; complete coverage; zero gaps, deferred or unresolved candidates, and
surviving security mutants; all exact-environment quality gates; hash-bound
artifacts; immutable defect facts; and explicit owner acceptance.

A context-isolated review is one distinct pass record, not an integer claim inside
another pass. Every pass has `completed_reviews = 1`, its own unique pass identity,
and its own retained source artifact. The native baseline therefore contains at
least five distinct native pass records, including at least three distinct
`deep_repository` records. Aggregating several alleged reviews into one pass is
prohibited.

Normalized pass and quality-gate evidence is not permitted to assert an orphaned
SHA-256 value. Every `source_artifact_sha256` must bind actual retained JSON bytes
under `governance/reviews/evidence/raw/`. Those source artifacts bind the exact
reviewed commit, pass kind or `quality_gate` classification, unique pass/gate
context identity, producer, and retained payload. The certifier recomputes the
source digest, rejects placeholder hashes, missing or unsafe source paths,
cross-commit evidence, and source reuse across distinct evidence owners.

The assurance modes are cumulative and exact:

- `native_maximum` makes no independence claim.
- `independent_external_model` adds a fresh exact-tree review from a different
  model provider and explicitly states that it is not human approval.
- `independent_human` adds an unrelated human GitHub approval that CI re-fetches
  and binds to the exact reviewed commit.

External-model and human review never replace or reduce the native baseline.
Self-approval cannot satisfy independent-human review. There is no absent, bypass,
waiver, partial-coverage, or unresolved-finding mode. Any change outside the fixed
post-review finalization paths invalidates every assurance artifact.

The canonical artifact is `governance/reviews/assurance_review.json`. Its evidence
is confined to `governance/reviews/evidence/`, is SHA-256 bound, and must account
exactly for every file in that directory, including retained raw-source artifacts.
Candidate-union evidence must account for every pass and every pass's candidate
count before defect closure can run.

## Consequences

Certification can proceed without misrepresenting unavailable external review,
but only through a substantially more expensive native process. A successful
native result remains candid about its limitation and is not represented as equal
to a different provider's fresh review or an unrelated human's approval.

The policy transaction itself does not satisfy the policy. Until a frozen exact
commit completes the new protocol, `ASSURANCE-001` remains an intentional
certification blocker and every active defect remains active.
