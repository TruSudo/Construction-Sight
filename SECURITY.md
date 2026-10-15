# ConstructionSight security policy

## Report security problems responsibly

Security-sensitive findings involving authorization bypass, credential disclosure,
unsafe external effects, duplicate execution, provenance loss, supply-chain risk,
data corruption, or boundary confusion should be reported privately through a
GitHub security advisory if disclosure could enable exploitation. Do not publish
exploit details in an ordinary issue before they are addressed.

## Active protection rules (2026-10-15)

Security protections are **risk-proportionate** and remain mandatory where failure
has meaningful consequences. The general development and release workflow is in
[README.md](README.md); previously mandated five-pass, all-file, exact-tree
certification is **not** required for routine development, feature work or merge.
The historical contracts and tooling remain in the repository for optional
focused audits and reproducibility of prior certification claims.

**Always enforce these boundaries:**

- Collect only lawfully accessible information in accordance with source terms,
  access restrictions, rate limits and permissions. HTTP 403 is not an invitation
  to route around an access boundary. No credential, CAPTCHA or login bypass.
- Preserve genuine acquired source evidence and provenance where permitted;
  never invent facts or promote a source claim, unverified match or hypothesis to
  verified status. Retain timestamps, source scope and explicit uncertainty.
- Keep external sending, purchases, destructive changes and high-impact effects
  behind the existing operator-authorization rules. No automatic outreach.
- Protect local secrets, credentials, source evidence and user data. Preserve
  reliable, verified backups and safe recovery paths for persistent data changes.
- Fail closed at permission and external-effect boundaries, and report access
  failures, stale data, and unsupported coverage honestly rather than silently
  claiming success.

## Development and release security gates

Normal PRs retain existing mandatory CI: Python 3.11 and 3.12 regression tests,
Ruff, strict Mypy, JavaScript syntax, dependency integrity and vulnerability
audit, plus affected functional/browser and source-specific tests. Never disable
a failing required gate merely to obtain a green PR. Run focused tests during
implementation and the full required CI before merge.

**Heightened adversarial review is triggered by affected risk, not by every
change in the repository.** Use review of the relevant threat model, negative
permission cases, replay and idempotence, concurrency, fault interruption,
restart and rollback as applicable when changing:

- Credential or authorization enforcement and HTTP/source-access restrictions.
- Automatic outbound effects, billing or privileged execution.
- Irreversible schema/data migration, deletion, backup, restore and relocation.
- Evidence/provenance integrity, source trust boundaries and cryptographic checks.
- CI permissions, dependency trust and vulnerability handling.

Mutation tests and multi-context independent reviews may be employed for the
specific dangerous invariants under examination. Repeating entire-repository
assurance without a concrete risk question is not an ordinary release requirement.

## Known defects and incidents

Use severity **P0 critical, P1 major, P2 moderate, P3 minor** as defined in
README.md. P0 blocks affected execution/release immediately. P1 blocks the
affected feature or release, but does not freeze isolated unrelated development.
P2 and P3 are tracked and prioritized rather than treated as universal blockers.
Never conceal a defect, fabricate a passing result, or treat an acceptance gap
as completed functionality.

On an actual safety or data-integrity incident, disable the affected action,
preserve relevant logs/evidence, determine scope and exposure, repair the fault,
and run targeted regression/recovery checks before reactivation. Security defects
are not severity-downgraded merely to ship.

## Historical full-repository certification

The legacy `governance/assurance_contract.toml`, semantic certification
commands, mutation contracts, assurance passes, archived reviews and earlier
accepted ADRs remain available for retrospective verification and unusually
high-risk audits. **If that historical certification is intentionally invoked,
its own internal evidence rules still apply to the claim it makes.** Passing
current product CI does not claim the old native-maximum certificate, and the
old certificate is not a universal prerequisite for operating or improving the
local-first application.

No policy change here relaxes source authorization, data access, external effects,
evidence integrity, consent or the owner's existing approval controls.
