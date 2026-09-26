# CS-SR-060 implementation-candidate evidence

Implementation parent: `72c121f807a775d207092caab34cbea39b004785`

This record documents code-level correction and regression evidence for
`CS-SR-060`. It is not an independent review, an approval, a resolution record,
or final exact-head certification. `CS-SR-060` and every other registered defect
remain in `governance/active_defects.toml`.

## Implemented controls

- Generic source readiness and verification accept only four exact, separately
  reviewed source URLs. A source-registry record can no longer grant itself
  outbound host authority.
- The owned low-level transport rejects IP literals and special-use hostnames,
  resolves the exact hostname once, rejects an empty result or any answer that
  is not globally routable, and also rejects IPv4-mapped, NAT64, Teredo, and
  6to4 transition ranges.
- The selected numeric address is bound to the TCP connection through the
  public `httpcore.NetworkBackend` interface. The original hostname remains the
  HTTP authority, TLS SNI identity, and certificate-verification identity, so a
  second attacker-controlled DNS resolution cannot change the connection
  target.
- The transport is single-use, permits no proxy, local-address, UNIX-socket,
  retry, redirect, ambient trust-store, client-certificate, or environment
  authority, and retains the existing exact-request and bounded-response rules.
- `certifi==2025.6.15` and `httpcore==1.0.9` are direct governed dependencies;
  both were already present with exact wheel hashes in the Python 3.11 and 3.12
  locks.

## Adversarial evidence

Focused regressions cover loopback and metadata IP literals, special-use names,
private and mixed DNS answers, legacy decimal and hexadecimal numeric host
forms, resolver-hidden alias/CNAME behavior, one-resolution TCP pinning, TLS
hostname preservation, owned pool construction, and rejection of ungoverned
source URLs by both readiness and verification.

Four new mutation witnesses remove IP-literal denial, public-address validation,
resolution-to-connect pinning, and the separate source-authority allowlist. Each
mutant is killed by its focused adversarial regression.

## Local exact-tree checks

The working candidate was evaluated with the exact Python 3.12 lock:

- Ruff: passed.
- strict mypy: passed across 248 source files.
- compileall over source and tests: passed.
- warning-strict pytest: 1,240 passed.
- focused mutation certification: 51/51 mutants killed.
- repository certification: exactly 62 deliberate blockers, comprising
  `CS-SR-001` through `CS-SR-061` plus `REVIEW-001`, with no additional finding.

No live HTTP request was performed as part of this evidence transaction. Exact
Python 3.11 and 3.12 GitHub CI on the resulting commit remains required.

## Remaining closure requirements

`CS-SR-060` remains active until the implementation commit and its exact-head
evidence complete fresh adversarial review, the complete corrected tree receives
a distinct real-human GitHub `APPROVED` review at the exact reviewed commit, and
reviewed-history closure certification permits the ledger transition. This
transaction does not satisfy or bypass any of those requirements.
