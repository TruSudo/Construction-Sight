# CS-SR-074 Permanent Closure Evidence

Defect: `CS-SR-074 — supply-chain-newly-disclosed-anyio-advisories`

## Historical root cause

Both supported artifact-hashed dependency locks retained AnyIO 4.9.0 when exact-head CI newly detected active GHSA-5p39-cfhj-2xmp (CVE-2026-64847) and GHSA-82r6-8w77-94w6 (CVE-2026-63374); their distinct public disclosure dates are not inferred from the CI detection date. The canonical 2026-09-20 exact-head CI vulnerability audits identified both as active and failed, invalidating reliance on the older no-active-advisory checkpoint. Exposure of affected AnyIO code paths within ConstructionSight has not been independently established.

## Required resolution

Retain independent source evidence for both advisories and the reviewed fixed AnyIO release; pin exact PyPI-published universal wheel identity and SHA-256 consistently for Python 3.11 and 3.12; validate strict hash-locked installation, dependency compatibility, network/TLS behavior, full tests and independent fresh vulnerability collection at an exact new head; propagate the fix to stacked GUI and hardening trees; keep this defect active until Native Maximum Assurance, reviewed closure and authenticated owner acceptance legitimately succeed.

## Resolution

Resolution implementation commit:

`6e568d2c266550be14f50f1270f4a5d13889d787`

Resolution Git tree:

`7fcfec16460c11694f2ab54650f070cf4ad00732`

The frozen implementation and every descendant current assurance head:

- pins AnyIO 4.14.2 identically in Python 3.11 and 3.12 lock files;
- binds the exact published artifact SHA-256;
- collects and validates current vulnerability-source evidence independently of the lock;
- passes isolated vulnerability certification on both supported runtimes;

## Regression evidence

Implementation evidence:

- `requirements/py311.lock`
- `requirements/py312.lock`
- `scripts/acquire_vulnerability_sources.py`
- `src/constructionsight/vulnerability_certification.py`

Regression/adversarial coverage:

- `tests/test_vulnerability_certification.py`
- `tests/test_vulnerability_collection.py`

## Validation

Frozen exact-head CI run `36105667808` and current-line exact-head runs `36120970387` / `36121225646` exercised the supported Python 3.11 and 3.12 quality and vulnerability matrices. On the current line, vulnerability audits passed and all substantive quality steps passed: exact checkout, dependency integrity, deterministic SBOM, Ruff, mypy, compilation, full pytest, focused mutation certification, adapter/source audits, native assurance preflight, repository/semantic certification, diff hygiene, and environment-identity checks. The only failing quality step was aggregate active-defect enforcement, as expected while unrelated defects remain.

The correction was already present while CS-SR-074 remained active through `93467d37b1876b9732f07ad0ad8a61c02db67b9f`. This ledger transition therefore preserves the historical finding and retires only its corrected root cause.
