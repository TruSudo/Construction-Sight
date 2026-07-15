# ADR-0002: Reproducible dependency and Action governance

- Status: Accepted
- Date: 2026-07-15
- Owners: ConstructionSight maintainers

## Decision

`pyproject.toml` remains the direct declaration. Every direct, development, and build dependency uses an exact version and appears in `governance/dependency_contract.toml`. Python 3.11 and 3.12 have separate exact environment locks. CI installs the selected lock without dependency resolution, installs the project without dependencies or build isolation, verifies installed versions, runs `pip check`, performs a fatal vulnerability audit, and emits a deterministic SBOM.

Every third-party GitHub Action is pinned to an immutable commit SHA with an inline release or review comment. Dependency, lock, build, Action, or install changes require explicit review evidence.

## Hash boundary

The first supported-environment locks enforce exact versions but do not yet enforce artifact hashes for every ABI/platform wheel. This is deliberately classified as partial enforcement, not full hash reproducibility. Hash enforcement becomes mandatory when reviewed lock generation covers every supported runner artifact without excluding required native wheels.

## Consequences

Resolver-selected upgrades and mutable Action tags are prohibited. A scanner failure is a failed audit, not a reason to continue. Vulnerability exceptions must be narrow, owned, justified, and expiring.
