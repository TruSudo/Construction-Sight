# CS-SR-063 Permanent Closure Evidence

Defect: `CS-SR-063 — assurance-context-isolation-integrity`

Implementation commit `aaa96290b45da6fdf12f61ff1919f458f8e9d7a0` (tree `e43b62587f2f595eaa6a7b8a3eaf1eb448745099`) requires each assurance pass to represent exactly one completed review, with distinct pass IDs and distinct retained evidence/source identities. Native Maximum Assurance requires at least five context-isolated native passes and at least three distinct deep_repository passes; aggregated counts and reused contexts/evidence fail closed.

`tests/test_assurance_certification.py` includes explicit aggregation, fresh-context, duplicate/reuse and minimum-count regressions, with focused mutation coverage retained by the assurance mutation overlay.

This closure preserves the historical finding and retires the context-count inflation defect.
