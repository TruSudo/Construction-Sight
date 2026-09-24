# CS-SR-072: inherited CI execution controls

Status: implementation validation in progress; defect remains active.
This is an engineering reproduction note, not a Native Maximum Assurance pass,
reviewed-history closure, or authenticated owner acceptance.

## Reproduction

The starting source tree matches commit
`71c34f275a8d6fa99692e730ff7254b932da7983`, Git tree
`d38153f19ee737b5764d59f1b8178213c2be139a`.

The existing launch was equivalent to:

```text
/bin/bash --noprofile --norc -e -o pipefail step.sh
```

With `BASH_ENV=/dev/null`, a script containing a marker followed by
`test failure = success` returned success without printing its marker when
`SHELLOPTS=noexec` was inherited. With `BASH_FUNC_test%%` set to an exported
function that returns zero, the marker ran but the failed check returned success.
These are different mechanisms from reading a BASH_ENV startup file.

Adding `SHELLOPTS: noexec` to the workflow-level environment preserved the literal
vulnerability-job block. Both that job's certifier and the complete structural
preflight accepted the modified source tree. The local reproduction was confined
to a separate worktree; the hostile setting was not published to GitHub.

## Remediation

All 25 canonical CI run steps now declare:

```text
/bin/bash --noprofile --norc -p -e -o pipefail {0}
```

The explicit executable avoids shell selection through an inherited PATH. Bash's
startup privileged mode ignores inherited shell options, exported functions, and
startup files; the runner still executes with its existing account permissions.
Explicit errexit and pipefail preserve the existing failure behavior. The three
step-local BASH_ENV neutralizers and the literal vulnerability-job contract remain.

`ci_execution_certification.py` additionally binds the complete canonical workflow
bytes to a reviewed literal SHA-256. Both pre-assurance structural certification
and final repository certification enforce this binding. It covers global env,
defaults, job and step settings, and ambiguous or additional YAML content without
introducing a second interpretation of YAML semantics.

A legitimate workflow edit must therefore include review of the whole workflow
and an explicit digest update in production code. The expected digest is never
learned from the current file at runtime. This is a drift control; the digest alone
does not prove that a proposed workflow is safe. Hosted-runner integrity and the
reviewed Action implementations remain part of the execution trust assumptions.

## Required regression witnesses

- Actual declared shell execution under inherited noexec/onecmd, shell options,
  exported functions, and an early-exit startup hook.
- Preservation of successful and failed script outcomes, errexit, and pipefail.
- Rejection of shell executable shadowing through PATH.
- Every run step bound to the reviewed launch command.
- Workflow-level and quality-job changes rejected even when the old literal
  vulnerability-job certifier still accepts them.
- Missing/unsafe workflow paths, alternate shells, and trailing YAML rejected.
- Focused mutation witnesses for the workflow digest and both certification
  integration points; existing vulnerability-job witnesses remain in force.

The exact published candidate must still complete the Python 3.11/3.12 CI matrix.
All active defects remain active until legitimate exact-tree assurance closure.
