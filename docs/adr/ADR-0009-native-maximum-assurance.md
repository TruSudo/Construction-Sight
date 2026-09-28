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

Retained raw payloads are semantic evidence, not opaque hash targets. Analytical
sources must agree with the normalized reviewer, provider, model, pass status,
context cardinality, candidate count, and coverage/disposition counts. Quality-gate
sources must agree with the normalized gate identity and status and must bind the
canonical CI workflow, exact reviewed SHA, pull request, GitHub Actions run, job,
and step identities. Finalization CI re-fetches the bound run and job data through
the read-only GitHub Actions API and requires the canonical bound step to have
completed successfully. A locally authored `producer = "github-actions"` string is
not sufficient provenance.

Owner acceptance is also external authority, not a repository-authored Boolean.
The assurance report must encode the repository owner's GitHub login, pull-request
number, and GitHub review ID. Its `review_method` must bind a deterministic SHA-256
over every material assurance claim: mode and status, exact reviewed commit and
tree, reviewed active-defect digest, surviving-mutant count, all analytical pass
records, candidate-union reference, quality-gate references, tier-specific pull
request binding, and limitations. Owner/reviewer identity, the acceptance Boolean,
and the later review ID are excluded from that digest so the owner can authenticate
an already-frozen evidence set without circular hashing.

The owner then submits an explicit GitHub COMMENT review on the exact frozen
`reviewed_commit`. The review body must state the exact reviewed commit, reviewed
tree digest, material-assurance digest, and `decision=accepted`. Finalization CI
re-fetches that review and pull request through read-only GitHub API authority and
requires the review to come from a human `User` whose login equals the repository
owner and whose author association is `OWNER`, with exact COMMENTED state, review
ID, commit, and body. General implementation authorization, self-authored JSON, or
an assistant-created acceptance without an explicit owner decision does not satisfy
this requirement.

Because the aggregate repository certification intentionally remains blocked by
active defects and missing assurance before finalization, the frozen candidate also
runs a pre-assurance structural certification. That preflight may disregard only
`ASSURANCE-001` and `DEFECT-ACTIVE-001`; every other architecture, capability,
governance, authorization, test, dependency, or semantic finding remains fatal.
The finalization transaction can therefore bind structural quality gates to a real
successful candidate-run step without circularly requiring completed assurance to
prove the candidate was structurally clean.

The assurance modes are cumulative and exact:

- `native_maximum` makes no independence claim.
- `independent_external_model` adds a fresh exact-tree review from a different
  model provider and explicitly states that it is not human approval.
- `independent_human` adds an unrelated human GitHub approval that CI re-fetches
  and binds to the exact reviewed commit.

External-model and human review never replace or reduce the native baseline.
Self-approval cannot satisfy independent-human review. Owner acceptance is a
separate authenticated decision and never counts as independent-human review.
There is no absent, bypass, waiver, partial-coverage, or unresolved-finding mode.
Any change outside the fixed post-review finalization paths invalidates every
assurance artifact.

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
