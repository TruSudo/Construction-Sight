# CS-SR-068 Permanent Closure Evidence

Defect: `CS-SR-068 — supply-chain-action-runtime-provenance`

## Historical root cause

Canonical CI pins third-party GitHub Action source commits, but the pinned checkout, setup-python, and upload-artifact commits declare Node 20 while current GitHub-hosted runners forcibly execute those bundles under Node 24. The immutable source SHA therefore no longer fixes the interpreter semantics actually executing in CI, and the workflow lacks a native binding from Action identity to a reviewed runtime class.

## Required resolution

Review and pin Node-24-native checkout, setup-python, and upload-artifact releases by immutable commit; preserve existing least-privilege and quality semantics; machine-certify the exact Action repositories, commits, occurrence counts, and reviewed runtime annotations; retain the composite pip-audit identity; rerun the complete exact-head matrix; and require the Node-20 forced-runtime warning to disappear before assurance freeze.

## Resolution

Resolution implementation commit:

`6e568d2c266550be14f50f1270f4a5d13889d787`

Resolution Git tree:

`7fcfec16460c11694f2ab54650f070cf4ad00732`

The frozen implementation and every descendant current assurance head:

- pins all canonical third-party Actions by immutable commit;
- records reviewed Node 24 runtime identity in the workflow and certifier;
- fails closed on runtime annotation drift, unreviewed repositories, unpinned refs, or wrong occurrence counts;

## Regression evidence

Implementation evidence:

- `.github/workflows/ci.yml`
- `src/constructionsight/ci_action_certification.py`

Regression/adversarial coverage:

- `tests/test_ci_action_certification.py`

## Validation

Frozen exact-head CI run `36105667808` and current-line exact-head runs `36120970387` / `36121225646` exercised the supported Python 3.11 and 3.12 quality and vulnerability matrices. On the current line, vulnerability audits passed and all substantive quality steps passed: exact checkout, dependency integrity, deterministic SBOM, Ruff, mypy, compilation, full pytest, focused mutation certification, adapter/source audits, native assurance preflight, repository/semantic certification, diff hygiene, and environment-identity checks. The only failing quality step was aggregate active-defect enforcement, as expected while unrelated defects remain.

The correction was already present while CS-SR-068 remained active through `93467d37b1876b9732f07ad0ad8a61c02db67b9f`. This ledger transition therefore preserves the historical finding and retires only its corrected root cause.
