# Native Maximum Assurance policy transaction

## Scope

This transaction replaces the prior mandatory unrelated-human-review assumption
with an honest cumulative assurance classification for ConstructionSight's current
private, solo-maintained operating model. It changes governance and certification;
it does not close or reinterpret any security defect.

## Mandatory native burden

The default `native_maximum` mode requires one frozen exact commit and tree plus:

- at least three context-isolated complete Standard reviews aggregated by a
  repository-wide Codex Security deep scan;
- a separate fresh exact-diff security review;
- a separate fresh adversarial invariant and attack-path review;
- blind candidate union before deduplication or adjudication;
- complete coverage and zero coverage gaps, deferred candidates, unresolved
  candidates, or surviving security mutants;
- deterministic adversarial and mutation evidence plus every exact-environment
  quality gate listed in `governance/assurance_contract.toml`;
- SHA-256-bound JSON evidence for every pass and gate;
- exact reviewed-commit, assured-tree, and active-defect-fact binding; and
- explicit owner acceptance that is not represented as independent approval.

The certifier rejects reused analytical-pass artifacts, mismatched candidate counts,
unreferenced files in the assurance evidence directory, unsafe evidence paths,
changed evidence digests, malformed or weakened policy, false independence claims,
and any post-assurance change outside the fixed finalization paths.

## Additive classifications

`independent_external_model` adds a fresh exact-tree pass by a different provider.
It records provider and model and expressly does not claim human approval.
`independent_human` adds an unrelated human GitHub approval. CI re-fetches the
artifact-bound pull request and review and verifies the human identity, approval
state, reviewer separation, and exact reviewed commit. Neither tier reduces the
native baseline.

## Deliberate current blockers

This policy transaction creates no assurance report because the policy cannot
retroactively review its own exact tree. All 61 entries remain in
`governance/active_defects.toml`. Until a later frozen commit completes the required
passes and finalization, canonical repository certification must report exactly the
active-defect blockers plus `ASSURANCE-001`, assuming no substantive regression.

There are no new path exclusions, severity reductions, defect waivers, bypass
modes, or self-approval-as-independent mechanisms. The disclosed limitation is the
absence of an external-model or human reviewer in native mode; the compensating
control is the materially increased native assurance burden.
