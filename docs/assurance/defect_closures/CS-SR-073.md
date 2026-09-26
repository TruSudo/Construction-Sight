# CS-SR-073 Permanent Closure Evidence

Defect: `CS-SR-073 — ci-pre-gate-build-execution`

## Historical root cause

The quality job installed the pull-request candidate with pip install --no-deps --no-build-isolation -e . before the structural and assurance gates. Because the candidate controls its PEP 517 build backend and build configuration, repository-controlled build code could execute before those gates and mutate runner command files or the checkout, allowing later gate execution to diverge from the reviewed workflow while the whole-workflow digest itself remained unchanged.

## Required resolution

Remove all candidate project installation and build execution from the pre-gate quality bootstrap; install only the exact hash-locked third-party environment; execute canonical source through a reviewed PYTHONPATH binding; certify the dependency-only install block and prohibit additional project-install commands independently of the workflow digest; verify source-project identity without invoking a build backend and reject installed-project shadowing; add regression and mutation coverage; rerun both supported runtimes; and retain CS-SR-073 as active until exact-tree Native Maximum Assurance legitimately closes reviewed defect history.

## Resolution

Resolution implementation commit:

`6e568d2c266550be14f50f1270f4a5d13889d787`

Resolution Git tree:

`7fcfec16460c11694f2ab54650f070cf4ad00732`

The frozen implementation and every descendant current assurance head:

- contains no editable or candidate project installation before the gates;
- installs the exact hash-locked dependency environment only;
- executes repository source through the reviewed PYTHONPATH binding;
- regressions reject -e/--editable, build-isolation bypass, source shadowing, and bootstrap drift;

## Regression evidence

Implementation evidence:

- `.github/workflows/ci.yml`
- `src/constructionsight/ci_execution_certification.py`
- `docs/adr/ADR-0009-native-maximum-assurance.md`

Regression/adversarial coverage:

- `tests/test_ci_execution_certification.py`

## Validation

Frozen exact-head CI run `36105667808` and current-line exact-head runs `36120970387` / `36121225646` exercised the supported Python 3.11 and 3.12 quality and vulnerability matrices. On the current line, vulnerability audits passed and all substantive quality steps passed: exact checkout, dependency integrity, deterministic SBOM, Ruff, mypy, compilation, full pytest, focused mutation certification, adapter/source audits, native assurance preflight, repository/semantic certification, diff hygiene, and environment-identity checks. The only failing quality step was aggregate active-defect enforcement, as expected while unrelated defects remain.

The correction was already present while CS-SR-073 remained active through `93467d37b1876b9732f07ad0ad8a61c02db67b9f`. This ledger transition therefore preserves the historical finding and retires only its corrected root cause.
