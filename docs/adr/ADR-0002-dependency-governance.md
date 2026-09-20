# ADR-0002: Reproducible dependency and Action governance

- Status: Accepted
- Date: 2026-07-15
- Owners: ConstructionSight maintainers

## Decision

`pyproject.toml` remains the direct declaration. Every direct, development, and build dependency uses an exact version and appears in `governance/dependency_contract.toml`. Python 3.11 and 3.12 have separate supported-environment locks for the GitHub-hosted Ubuntu x86_64 runner. Each logical lock entry binds the exact distribution version to one or more reviewed SHA-256 wheel identities.

CI installs the selected lock with `--require-hashes`, `--only-binary=:all:`, and `--no-deps`; it then installs the project without dependency resolution or build isolation. The supply-chain certifier rejects unhashed, nonexact, duplicate, malformed, or dangling lock entries, verifies installed versions, runs `pip check`, performs a fatal vulnerability audit, and emits a deterministic SBOM.

Vulnerability tooling runs in a separate matrix job and cannot modify the interpreter used for executable quality gates. The supported interpreter is reverified against the exact lock immediately before and after the complete executable gate sequence. Both jobs reject tracked Git mode `120000` entries before consuming repository paths.

Every third-party GitHub Action is pinned to an immutable commit SHA with an inline release or review comment. Dependency, lock, build, Action, or installation changes require explicit review evidence.

## Artifact boundary

The checked-in locks certify the exact binary artifacts supported by the current GitHub-hosted Linux CI environments for CPython 3.11 and 3.12. They do not claim reproducibility for macOS, Windows, alternative architectures, alternative Python implementations, source distributions, or local environments whose wheel-selection tags differ from those runners. Adding another supported environment requires a separately reviewed lock and CI job; broadening a lock by admitting unreviewed alternate hashes is prohibited.

## Consequences

Resolver-selected upgrades, source-build fallback, unhashed installation, mutable Action tags, and silent package substitution are prohibited. A scanner failure is a failed audit, not a reason to continue. Vulnerability exceptions must be narrow, owned, justified, and expiring. Hashes establish artifact identity; they do not independently establish that a package is secure, maintained, correctly licensed, or semantically suitable, so the dependency registry and vulnerability review remain mandatory.

## 2026-09-14: CS-SR-069 native vulnerability audit

The reviewed `pypa/gh-action-pip-audit` composite commit bootstraps a
resolver-selected scanner environment. Its immutable Action SHA therefore does
not fix the scanner code. The replacement uses repository-owned standard-library
code, with no scanner installation or additional package dependency:

- `scripts/acquire_vulnerability_sources.py` runs only in the isolated audit job.
  It requests the exact lock's release URLs from `https://pypi.org`, with verified
  TLS, no redirects or proxy inheritance, a 15-second socket timeout, a 60-second
  per-response deadline, a 2 MiB response limit, and at most 256 packages. Access
  failures, invalid media types/encodings, truncation, and incomplete acquisition
  are fatal. A completion manifest is written only after all raw sources exist.
- `constructionsight.vulnerability_certification` has no network authority. It
  derives its inventory from the artifact-hashed lock, reconciles the full source
  inventory, commit, lock digest, release identities, and raw hashes, and rejects
  duplicate or malformed JSON and vulnerability records. Every active advisory
  fails the audit. Valid withdrawn advisories remain visible in the report.
- CI retains both raw release responses and the deterministic offline report.
  A separate native CI certifier requires the complete reviewed isolated job,
  including the two runtimes, exact checkout, acquisition, certification, outcome
  enforcement, and retention. Preflight and final repository certification both
  enforce this binding.

The source contract is PyPI's release-specific JSON API:
<https://docs.pypi.org/api/json/#get-a-release> and
<https://docs.pypi.org/api/json/#known-vulnerabilities> (reviewed 2026-09-14).
The prior scanner used the same PyPI service. The result describes known PyPI
advisories at collection time; raw hashes provide integrity, not independent
source authentication. Authentic execution is established by the canonical CI
run on the reviewed SHA. Offline replay does not claim a fresh advisory check.

The current exception inventory is empty. This implementation provides no
vulnerability bypass. Future exception handling requires its own reviewed
implementation and tests. Existing lock, environment, dependency, and SBOM
checks remain mandatory. CS-SR-068's historical composite-identity requirement is
superseded by this explicit removal of that composite Action; its immutable
ledger facts remain preserved. Action runtime pins for checkout, setup-python,
and upload-artifact are unchanged.

## 2026-09-20: CS-SR-074 AnyIO transitive-lock remediation candidate

The canonical CI-only integration verification run 35525561087, bound to
`3be6ee6529ed5d8cbb69d88c064de9fd6174c0a4`, retained fresh PyPI
release-specific vulnerability evidence that `anyio==4.9.0` has two active
advisories in both supported Python locks:
`GHSA-5p39-cfhj-2xmp` (CVE-2026-64847) and
`GHSA-82r6-8w77-94w6` (CVE-2026-63374). The September 18 historical
checkpoint did not establish the absence of advisories discovered afterward.
The source reports do not by themselves prove exploitation or reachability of
these specific affected AnyIO code paths in ConstructionSight.

Publisher identity and artifact selection: the AnyIO 4.14.2 release is at
`https://pypi.org/project/anyio/4.14.2/`, which lists Python >=3.10,
MIT license, a universal `anyio-4.14.2-py3-none-any.whl`, a PyPI-verified
Trusted Publishing attestation, and wheel SHA-256
`9f505dda5ac9f0c8309b5e8bd445a8c2bf7246f3ce950121e45ea15bc41d1494`.
Both upstream advisories identify 4.14.2 as the first fixed release. No
source distribution, alternate wheel, changed direct requirement, or scanner
exception is admitted. Both supported environment locks now select only that
exact publisher-reviewed wheel for AnyIO. The rest of each lock remains unchanged.

This is an **implementation candidate**, not an exact-head verification,
proof of library compatibility, completed Native Maximum Assurance review,
closed defect, or release authorization. Collect fresh independent PyPI source
reports and run the entire Python 3.11/3.12 gate matrix and network/TLS
regressions at a frozen exact new head. Keep CS-SR-074 active until legitimate
review, Native Maximum Assurance, and authenticated owner acceptance close it.
