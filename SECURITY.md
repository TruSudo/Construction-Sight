# ConstructionSight security policy

## Security scope

The canonical security scope is every tracked repository file: production code,
tests, governance, CI, dependency locks, documentation claims, and retained
evidence. Untracked caches and generated build output are not product evidence and
cannot satisfy certification.

Report authorization bypass, stale-state or replay behavior, duplicated effects,
unsafe network or persistence authority, provenance loss, supply-chain drift,
cross-boundary data confusion, fail-open behavior, and certification bypass as
security issues. Use a private GitHub security advisory when disclosure could make
exploitation easier; do not publish exploit details in an ordinary issue first.

## Mandatory default: Native Maximum Assurance

ConstructionSight is a private, solo-maintained open-source program without a
standing external reviewer. That limitation raises the mandatory native standard;
it does not authorize self-approval or permit review to be omitted.

Certification requires one frozen exact commit and tree plus all of the following:

1. A repository-wide Codex Security deep scan containing at least three separately
   initiated, context-isolated complete Standard passes.
2. A separate fresh-context security review of the exact change range.
3. A separate fresh-context adversarial invariant and attack-path review.
4. Blind union of every pass's candidates before deduplication or adjudication.
5. Complete coverage, with zero coverage gaps, deferred candidates, unresolved
   candidates, or surviving security mutants.
6. Deterministic negative, boundary, replay, concurrency, interruption, rollback,
   restart, and fault tests wherever the affected authority can exhibit them.
7. Exact-lock dependency integrity, deterministic SBOMs, vulnerability audits,
   Ruff, strict mypy, compileall, warning-strict tests on Python 3.11 and 3.12,
   architecture/capability/governance/authorization certification, adapter and
   source-coverage audits, and diff hygiene.
8. Hash-bound review and gate artifacts, exact reviewed-commit and tree binding,
   immutable defect facts, and explicit owner residual-risk acceptance.

Each analytical pass must begin without implementation-session conclusions or the
other passes' candidate lists. Context isolation supplies a genuine fresh take but
is not described as external or human independence. Any code, contract, test,
dependency, or workflow change invalidates the assurance evidence and restarts the
entire protocol.

## Additive review classifications

The assurance modes are cumulative:

- `native_maximum` is the mandatory baseline. Owner acceptance records residual
  responsibility but is not independent approval.
- `independent_external_model` adds a fresh exact-tree review by a different model
  provider, such as Claude or Gemini. Provider, model, artifact, and digest must be
  recorded. It is independent external-model review, not human approval.
- `independent_human` adds an unrelated human GitHub reviewer whose exact-commit
  `APPROVED` review is re-fetched and verified by CI. The reviewer may not be the
  repository owner or pull-request author.

External-model or human review never replaces or reduces the native baseline.
There is no `none`, bypass, waiver, or self-approval-as-independent mode.

## Closure and accepted limitation

Active defects, incomplete coverage, unresolved or deferred candidates, malformed
evidence, failed gates, and evidence that does not bind the exact frozen tree block
certification. Findings are fixed and the complete protocol is rerun; they are not
suppressed or severity-reduced to obtain a passing result.

The accepted limitation for `native_maximum` is disclosed absence of an external
model or human reviewer. The compensating control is the materially higher native
burden above. This limitation is not an assertion that same-provider passes equal
external independence and is not acceptance of a known security defect.

Reconsider external-model or human review whenever maintainership expands, the
repository becomes public or multiuser, protected or regulated data enters scope,
production scheduling or hosted identity is enabled, or deployment consequences
materially exceed the current local operating model.
