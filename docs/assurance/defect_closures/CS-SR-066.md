# CS-SR-066 Permanent Closure Evidence

Defect: `CS-SR-066 — assurance-owner-acceptance-authenticity`

## Historical root cause

Native Maximum Assurance owner acceptance could be represented by repository-controlled Boolean/text fields without an externally authenticated owner action bound to the exact frozen assurance evidence set.

## Resolution

Implementation commit: `ba5c837ee5c549697944df04d0264b28e36e87c4`

Resolution tree: `4c222ce11a3dc4734227df93a3428cb4698bb1d4`

Owner acceptance now binds the repository owner's GitHub login, pull request, review ID, exact reviewed commit, reviewed tree digest, and a deterministic SHA-256 digest of all material assurance claims. Canonical CI re-fetches the GitHub review and requires the exact COMMENTED owner review, human User identity, OWNER association, exact commit, and exact acceptance body. A repository-authored Boolean, arbitrary owner string, stale acceptance, or changed evidence set cannot satisfy the gate.

## Regression and retained evidence

`tests/test_owner_acceptance_certification.py`, `tests/test_ci_exact_head_contract.py`, and the assurance mutation overlay exercise wrong owner, review ID, commit, state/body, evidence digest, and CI-wiring failures. `docs/adr/ADR-0009-native-maximum-assurance.md` makes explicit that assistant-created or self-authored repository acceptance cannot substitute for the owner's later authenticated decision.

This closes the authenticity defect in the acceptance mechanism. It does not fabricate or claim the final owner acceptance for the current candidate; that action remains required after the assurance evidence set is frozen.
