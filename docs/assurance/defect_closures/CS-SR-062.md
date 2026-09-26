# CS-SR-062 Permanent Closure Evidence

Defect: `CS-SR-062 — assurance-reviewed-tree-binding`

Implementation commit `ecf85a78878aa368de0025bd8633ac94d5e1c7e9` (tree `b388d55cb43d698cfc655d18c4f7054c26d9c068`) changed assurance validation to compute the covered-tree digest from the named reviewed commit itself, using canonical Git object identities and the same finalization exclusions. The report digest must match that historical commit and the current covered tree; stale reviewed commits and non-finalization implementation drift fail closed.

`tests/test_assurance_reviewed_tree_binding.py` reproduces stale-commit rebinding, covered-tree mutation, permitted finalization and exact-tree cases. These regressions remain in canonical CI.

This closure preserves the historical finding and retires the reviewed-tree rebinding defect.
