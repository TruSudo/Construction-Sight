# CS-SR-028 Permanent Closure Evidence

Defect: `CS-SR-028 — defect-closure-fact-integrity`

The closure certifier now proves every resolved record against immutable Git history rather than trusting current ledger text. It reloads the complete active ledger at `last_active_commit`, requires exact preservation of ID, severity, area, root cause, discovery commit and required resolution, proves the correction commit exists and is an ancestor of the last-active commit, verifies its Git tree, and binds assurance to the canonical digest of all reviewed active-defect facts.

The current v2 closure implementation was synchronized at `3f932df4a275f894796c8779fb376fb6bd8eb4f5` (tree `316fff8506714d00fb1ca3a8cc4f5c06ff372ce5`). Dedicated negative tests reject changed historical facts, missing or unrelated resolution commits, invalid ancestry, incomplete reviewed-fact digests, overlaps and malformed closure evidence. Exact-head CI on the same remediation lineage executes these tests in the full Python 3.11/3.12 suite.

This closure preserves the historical finding and retires the fact-integrity defect.
