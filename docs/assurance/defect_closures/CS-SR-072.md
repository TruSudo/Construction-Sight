# CS-SR-072 Permanent Closure Evidence

Defect: `CS-SR-072 — ci-inherited-execution-controls`

## Historical root cause

The canonical CI workflow launches noninteractive Bash without suppressing inherited shell options and exported functions. SHELLOPTS=noexec skips a failing script and exits successfully even with BASH_ENV=/dev/null; an imported test function can also turn failed enforcement into success. A workflow-level noexec setting outside the literal vulnerability-job block passes the complete existing structural preflight, and quality-job shells remain exposed to inherited startup hooks.

## Required resolution

Use an explicit reviewed Bash executable and startup-isolated launch flags for every canonical CI run step, preserving errexit and pipefail; bind all workflow bytes including global settings and quality-job controls into structural and final certification; preserve the existing BASH_ENV neutralizers and vulnerability-job contract; add real inherited-option, exported-function, startup-hook, command-resolution, and failure-propagation regressions plus digest and integration mutation witnesses; rerun the complete supported-runtime matrix; and retain the defect until exact-tree Native Maximum Assurance closure.

## Resolution

Resolution implementation commit:

`6e568d2c266550be14f50f1270f4a5d13889d787`

Resolution Git tree:

`7fcfec16460c11694f2ab54650f070cf4ad00732`

The frozen implementation and every descendant current assurance head:

- uses /bin/bash --noprofile --norc -p -e -o pipefail for every run step;
- rejects inherited SHELLOPTS, BASHOPTS, exported functions, startup hooks, PATH overrides, and shell/default drift;
- binds execution semantics outside the literal vulnerability-job block with a whole-workflow seal;

## Regression evidence

Implementation evidence:

- `.github/workflows/ci.yml`
- `src/constructionsight/ci_execution_certification.py`

Regression/adversarial coverage:

- `tests/test_ci_execution_certification.py`

## Validation

Frozen exact-head CI run `36105667808` and current-line exact-head runs `36120970387` / `36121225646` exercised the supported Python 3.11 and 3.12 quality and vulnerability matrices. On the current line, vulnerability audits passed and all substantive quality steps passed: exact checkout, dependency integrity, deterministic SBOM, Ruff, mypy, compilation, full pytest, focused mutation certification, adapter/source audits, native assurance preflight, repository/semantic certification, diff hygiene, and environment-identity checks. The only failing quality step was aggregate active-defect enforcement, as expected while unrelated defects remain.

The correction was already present while CS-SR-072 remained active through `93467d37b1876b9732f07ad0ad8a61c02db67b9f`. This ledger transition therefore preserves the historical finding and retires only its corrected root cause.
