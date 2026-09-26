# CS-SR-060 Permanent Closure Evidence

Defect: `CS-SR-060 — public-source-egress-authority`

## Historical root cause

Generic source-readiness and verification paths could derive outbound authority from the same caller-controlled URL being constrained, allowing special-use or internal destinations to self-authorize.

## Resolution

Implementation commit: `d15f0742512d02fe3952719e14d99000c6692be9`

Resolution tree: `559092eb40c99722bb6c0db0adee51c5091d0bb6`

The implementation separates reviewed source identity from executable network authority, rejects IP literals and special-use hosts, validates resolved addresses as globally routable, and pins the selected numeric address to the connection while retaining the original hostname for HTTP authority, TLS SNI, and certificate verification. Exact request, redirect, credential, TLS, and response bounds remain enforced.

## Regression and retained evidence

Retained implementation evidence is recorded in `artifacts/remediation_evidence_2026-08-22_cs_sr_060.md`. Canonical regressions cover loopback, private/link-local/reserved destinations, numeric host forms, mixed DNS answers, alias behavior, resolution-to-connect pinning, TLS hostname preservation, and rejection of ungoverned source URLs.

The correction remains present on the current remediation lineage. Exact-head CI run `36122444501` subsequently passed Ruff, mypy, compilation, full pytest, focused mutation certification, adapter/source audits, native assurance preflight, diff hygiene, exact-environment checks, and both isolated vulnerability audits; its aggregate failure was due to still-active ledger findings/final assurance, not reappearance of CS-SR-060.

This closure preserves the historical finding and retires the corrected root cause.
