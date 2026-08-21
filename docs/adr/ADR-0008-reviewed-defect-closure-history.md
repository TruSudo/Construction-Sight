# ADR-0008: Bind defect closure to reviewed Git history

- Status: Accepted
- Date: 2026-08-21
- Owners: ConstructionSight maintainers

## Context

The active and resolved defect ledgers are permitted finalization paths after an independent review. Schema validation alone therefore cannot prove that a resolved entry preserves the facts that the reviewer actually saw, accounts for every reviewed defect, or names a resolution commit in the reviewed implementation history.

## Decision

The independent-review artifact binds both the exact reviewed commit and a domain-separated SHA-256 digest of that commit's complete canonical active-defect facts. Final repository certification reads the active and resolved ledgers directly from the reviewed commit and requires:

- every reviewed active ID to move to the resolved ledger exactly once;
- no reviewed ID to remain active and no unreviewed ID to appear;
- original ID, severity, area, root cause, discovery commit, and required resolution to remain byte-for-byte equal as parsed TOML values;
- every previously resolved record to remain unchanged;
- every resolution commit to exist as a Git commit object and be an ancestor of the reviewed implementation commit; and
- the reviewed implementation commit to be an ancestor of the finalization head.

Canonical quality jobs fetch complete Git history so ancestry checks never degrade into shallow-clone guesses. Missing history, malformed reviewed ledgers, or Git command failure blocks certification.

## Consequences

Review and finalization remain separate stages, but ledger mutation after review is limited to mechanically provable closure. A commit SHA that merely has the right shape is not evidence, rewritten defect prose cannot pass as the reviewed fact, and partial or invented closure accounting fails closed.
