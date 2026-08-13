# ConstructionSight Adversarial Review — 2026-08-13

## Result

**FAILED. Candidate `4cc3ce763354ea91ef8c4bed28c3ce0b531379c3` is invalidated and must not be certified or merged.**

This review was separately initiated at the repository owner's direction after the implementation was frozen. Prior implementation summaries and successful CI were treated as claims to challenge rather than proof.

## Findings

### AR-001 — Reviewed defect facts are not immutable during closure — P0

Resolved-defect validation checks schema and evidence references but does not prove that the original defect facts are identical to those present in the reviewed commit. Resolution commit values are not proven to exist in reviewed history.

Required correction: bind closure records to the reviewed commit's active-defect ledger, preserve original fields exactly, require complete reviewed-ID accounting, and validate resolution commit ancestry.

### AR-002 — HTTP authorization and outbound URL canonicalization can diverge — P0

The bounded HTTP layer validates one path representation while the HTTP client may transmit a normalized representation. Ambiguous path encodings are not rejected consistently.

Required correction: derive one canonical outbound URL, validate that exact representation, reject ambiguous path forms, and execute only the representation that was authorized.

### AR-003 — Persistence authorization is not bound to a detached payload snapshot — P0

The persistence facade authorizes a caller-owned mutable write-plan object and later gives the same object to the effect boundary.

Required correction: create and authorize a detached canonical snapshot, verify its identity immediately before execution, and execute only that snapshot.

### AR-004 — CI modifies the verified Python environment before quality gates — P0

The exact installed environment is verified before vulnerability tooling runs. The vulnerability action then installs additional Python distributions into the same interpreter before lint, type, test, mutation, and repository certification steps.

Required correction: isolate vulnerability tooling and verify the supported interpreter's exact installed-distribution inventory immediately before and after executable quality gates.

### AR-005 — CEQAnet compatibility transport configuration conflicts with redirect doctrine — P0

The production-visible injected-client path enables redirect following even though the network contract requires redirect denial. Current tests preserve that setting.

Required correction: deny redirects at request time on every production-visible path and replace the regression that preserves the conflicting behavior.

### AR-006 — Repository evidence containment is incomplete — P0

Tracked symbolic links are not prohibited and several governance artifact references are validated without proving the resolved file remains inside the repository.

Required correction: reject tracked symbolic links and require resolved repository containment for governance evidence, tests, ADRs, locks, and mutation references.

### AR-007 — Semantic authorization certification relies on naming convention — P0

The static authorization audit accepts application calls based on `*_authorized_*` naming patterns without resolving the target and proving that canonical authorization occurs before an effect.

Required correction: replace naming trust with resolved call-path evidence from operator entry point through canonical authorization/preflight to the effect boundary.

### AR-008 — Exact query scope remains prose rather than executable policy — P0

The network contract describes exact query scope, but the shared bounded policy does not represent query authority and the CEQAnet planner permits caller-supplied base search URLs.

Required correction: bind query scope or exact canonical request identity in executable policy and reject unreviewed base-query content.

## Disposition

The previous candidate is no longer a valid review candidate. Each finding requires an active defect record, focused regression coverage, correction, complete Python 3.11/3.12 validation, and a new adversarial review of the corrected exact tree.
