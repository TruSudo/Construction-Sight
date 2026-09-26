# CS-SR-071 Permanent Closure Evidence

Defect: `CS-SR-071 — assurance-execution-integrity`

## Historical root cause

The isolated vulnerability job invokes three noninteractive Bash steps without step-local BASH_ENV neutralization. A workflow, job, runner, or inherited environment can therefore point BASH_ENV at attacker-controlled startup content that Bash evaluates before the canonically certified step body, allowing the execution semantics to diverge from the text the vulnerability CI certifier binds.

## Required resolution

Set BASH_ENV to /dev/null at each security-critical vulnerability Bash step, bind all occurrences and their placement into the exact vulnerability-job execution contract, add missing-or-weakened neutralizer regressions and focused mutation coverage, rerun the complete exact-head supported-runtime matrix, and retain CS-SR-071 as active until exact-tree Native Maximum Assurance legitimately closes the reviewed defect history.

## Resolution

Resolution implementation commit:

`6e568d2c266550be14f50f1270f4a5d13889d787`

Resolution Git tree:

`7fcfec16460c11694f2ab54650f070cf4ad00732`

The frozen implementation and every descendant current assurance head:

- sets BASH_ENV=/dev/null on each security-critical vulnerability Bash step;
- binds all three neutralizers into the exact job contract;
- tests missing, weakened, higher-scope, and hostile startup-hook cases;
- preserves fail-closed enforcement of the vulnerability-audit outcome;

## Regression evidence

Implementation evidence:

- `.github/workflows/ci.yml`
- `src/constructionsight/vulnerability_ci_certification.py`

Regression/adversarial coverage:

- `tests/test_vulnerability_ci_certification.py`
- `tests/test_vulnerability_ci_startup.py`

## Validation

Frozen exact-head CI run `36105667808` and current-line exact-head runs `36120970387` / `36121225646` exercised the supported Python 3.11 and 3.12 quality and vulnerability matrices. On the current line, vulnerability audits passed and all substantive quality steps passed: exact checkout, dependency integrity, deterministic SBOM, Ruff, mypy, compilation, full pytest, focused mutation certification, adapter/source audits, native assurance preflight, repository/semantic certification, diff hygiene, and environment-identity checks. The only failing quality step was aggregate active-defect enforcement, as expected while unrelated defects remain.

The correction was already present while CS-SR-071 remained active through `93467d37b1876b9732f07ad0ad8a61c02db67b9f`. This ledger transition therefore preserves the historical finding and retires only its corrected root cause.
