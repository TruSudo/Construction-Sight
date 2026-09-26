# Defect Closure Semantic Evidence

ConstructionSight defect closure is forward-activated by
`governance/defect_closure_semantic_contract.toml`.

Historical closures whose last-active commit predates that marker remain governed by
their original Git-bound v2 closure rules. Once the marker exists in a defect's
last-active history, closure additionally requires a sibling
`.proof.json` file beside the Markdown closure evidence.

The semantic proof must bind the exact SHA-256 of the defect's
`required_resolution` to:

1. changed implementation evidence retained in `evidence_paths`;
2. changed regression tests retained in `regression_tests`;
3. literal positive/negative assertions evaluated against the exact
   `resolution_commit`; and
4. an explicit defect marker in every regression witness.

At least one negative witness is mandatory so a closure must prove that a material
contradictory or unsafe condition is absent, not merely assert that a correction
exists.

For activated closures, `resolution_summary` is no longer free-form authority. The
certifier derives the only accepted summary deterministically from the bound
required-resolution digest and the verified implementation/test paths. Human
narrative may remain in the Markdown closure record, but narrative alone cannot
satisfy closure.
