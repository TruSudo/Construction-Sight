# CS-SR-064 Permanent Closure Evidence

Defect: `CS-SR-064 — assurance-source-provenance-integrity`

The final provenance implementation is bound to commit `0285bc90314052a72faf10aa6a609213f7927838` (tree `902150b7bb069dac6729d825b6661ac24763f33e`). Retained source identities are no longer syntax-only hashes: certification resolves source artifacts, recomputes their SHA-256, validates exact reviewed-commit/context metadata, rejects missing, zero-hash, digest-mismatched, cross-commit and reused sources, and binds quality-gate evidence to authoritative GitHub Actions provenance.

Regression coverage spans `tests/test_assurance_certification.py`, `tests/test_assurance_source_certification.py`, `tests/test_assurance_preflight_certification.py` and `tests/test_github_actions_certification.py`. The current exact-head quality matrix executes these checks on both supported Python versions.

This closure preserves the historical finding and retires the fabricated/stale source-provenance defect.
