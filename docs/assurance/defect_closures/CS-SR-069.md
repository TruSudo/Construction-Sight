# CS-SR-069 Permanent Closure Evidence

Defect: `CS-SR-069 — supply-chain-vulnerability-toolchain-reproducibility`

## Historical root cause

The immutable pypa/gh-action-pip-audit composite source does not pin the scanner implementation it executes: its requirements allow resolver-selected pip-audit and transitive versions, so the mandatory vulnerability gate can change without a ConstructionSight tree or Action-SHA change.

## Required resolution

Remove the resolver-selected vulnerability-scanner bootstrap; use a repository-owned deterministic vulnerability certifier with explicit fail-closed advisory provenance or a fully artifact-hashed exact scanner environment; preserve isolated zero-known-vulnerability enforcement and retained evidence; add negative network, schema, advisory, and mutation coverage; and rerun the complete supported-runtime matrix.

## Resolution

Resolution implementation commit:

`6e568d2c266550be14f50f1270f4a5d13889d787`

Resolution Git tree:

`7fcfec16460c11694f2ab54650f070cf4ad00732`

The frozen implementation and every descendant current assurance head:

- collects vulnerability sources with repository-owned code;
- certifies retained source bytes and exact lock identities;
- runs the same reviewed certifier in both supported-runtime vulnerability jobs;
- fails closed on malformed, missing, stale, or inconsistent vulnerability evidence;

## Regression evidence

Implementation evidence:

- `.github/workflows/ci.yml`
- `scripts/acquire_vulnerability_sources.py`
- `src/constructionsight/vulnerability_certification.py`
- `src/constructionsight/vulnerability_ci_certification.py`

Regression/adversarial coverage:

- `tests/test_vulnerability_certification.py`
- `tests/test_vulnerability_collection.py`
- `tests/test_vulnerability_ci_certification.py`

## Validation

Frozen exact-head CI run `36105667808` and current-line exact-head runs `36120970387` / `36121225646` exercised the supported Python 3.11 and 3.12 quality and vulnerability matrices. On the current line, vulnerability audits passed and all substantive quality steps passed: exact checkout, dependency integrity, deterministic SBOM, Ruff, mypy, compilation, full pytest, focused mutation certification, adapter/source audits, native assurance preflight, repository/semantic certification, diff hygiene, and environment-identity checks. The only failing quality step was aggregate active-defect enforcement, as expected while unrelated defects remain.

The correction was already present while CS-SR-069 remained active through `93467d37b1876b9732f07ad0ad8a61c02db67b9f`. This ledger transition therefore preserves the historical finding and retires only its corrected root cause.
