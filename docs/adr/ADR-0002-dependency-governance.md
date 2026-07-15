# ADR-0002: Reproducible dependency and Action governance

- Status: Accepted
- Date: 2026-07-15
- Owners: ConstructionSight maintainers

## Decision

`pyproject.toml` remains the direct declaration. Every direct, development, and build dependency uses an exact version and appears in `governance/dependency_contract.toml`. Python 3.11 and 3.12 have separate supported-environment locks for the GitHub-hosted Ubuntu x86_64 runner. Each logical lock entry binds the exact distribution version to one or more reviewed SHA-256 wheel identities.

CI installs the selected lock with `--require-hashes`, `--only-binary=:all:`, and `--no-deps`; it then installs the project without dependency resolution or build isolation. The supply-chain certifier rejects unhashed, nonexact, duplicate, malformed, or dangling lock entries, verifies installed versions, runs `pip check`, performs a fatal vulnerability audit, and emits a deterministic SBOM.

Every third-party GitHub Action is pinned to an immutable commit SHA with an inline release or review comment. Dependency, lock, build, Action, or installation changes require explicit review evidence.

## Artifact boundary

The checked-in locks certify the exact binary artifacts supported by the current GitHub-hosted Linux CI environments for CPython 3.11 and 3.12. They do not claim reproducibility for macOS, Windows, alternative architectures, alternative Python implementations, source distributions, or local environments whose wheel-selection tags differ from those runners. Adding another supported environment requires a separately reviewed lock and CI job; broadening a lock by admitting unreviewed alternate hashes is prohibited.

## Consequences

Resolver-selected upgrades, source-build fallback, unhashed installation, mutable Action tags, and silent package substitution are prohibited. A scanner failure is a failed audit, not a reason to continue. Vulnerability exceptions must be narrow, owned, justified, and expiring. Hashes establish artifact identity; they do not independently establish that a package is secure, maintained, correctly licensed, or semantically suitable, so the dependency registry and vulnerability review remain mandatory.
