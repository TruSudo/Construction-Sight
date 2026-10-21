# P8-01 historical capability disposition: first bounded reconciliation

**Status:** evidence-backed triage, **NOT P8-01 acceptance**. Source is the immutable
`docs/audits/unification-preservation-baseline-2026-10-16.json` (its fixed
4c8f8eaf historical comparison) cross-checked with the Phase 8 gate register
and the live modules present on the unification branch. This document does not
alter or supersede the baseline, silently import historical branches, modify
product behavior, or make an untested claim of runtime equivalence.

## Historical items with an explicit disposition

| Historical capability/path family | Current counterpart and disposition | Still-open proof or boundary |
| --- | --- | --- |
| `ceqanet_csv_export_*` (historical-only CLI/models/service/tests) | Original CSV request/model/services in `src/constructionsight/ceqanet_csv_*`, policy/series services and the reviewed native project/document CSV preview/execution and retained import. **Replaced by narrower guarded services**, not a reason to restore an old parallel CSV executor. | P8-03 accepted at tested `a4a0cd5`; actual current source access is separately P8-20. Preserve historical branch while comparing any unique edge semantics. |
| `src/constructionsight/money.py` | Current native commercial code uses Decimal or integer-cent arithmetic; original result ledger models historically had floating-point fields. **Historical primitive potentially superseded, numeric equivalence NOT established.** | P8-09 must prove exact historical amounts, corrections, result ledger and authority invariants end-to-end; no automatic entitlement or float conversion. |
| `result_ledger_authority_*` | Current `result_authority_service` and `storage/result_authority_*` implement independently governed immutable outcomes and compare-and-swap. **Partial service replacement, operator parity open.** | P8-09: actual reviewed transitions, outcome corrections and native commercial readback; do not copy the historical authority system into a second store. |
| `source_intelligence_bridge.py` | Historical preliminary read-only bridge with documented whitespace comparison defect. **Rejected prototype, not a second source of truth.** | P8-01 must ensure that no unique required verified behavior was omitted; P8-04/08 still own real cross-source identity/lead handoffs. |
| `tests/test_database_integrity.py` | Original primary database foreign-key guarantee exists; historical test file missing from branch. **Regression restoration candidate, NOT a product feature to reimplement.** | Add direct negative FK/cascade integrity regression where existing coverage is insufficient; do not duplicate DB engine. |
| `tests/test_ceqanet_ingestion_inbox.py` | Current `tests/test_operator_ingestion_inbox.py` and operator CSV bridge exercise the inbox; full original-source handoffs accepted under P8-03. **Covered functional family, exact historical test comparison still open.** | Verify any unique failure/recovery conditions before classifying the old test fully superseded. |
| `tests/test_ceqanet_verified_source_maturity.py` | Retained original replay, maturity, policy and series verifiers and native audits accepted under P8-03. **Original governance behavior covered; historical evidence stays preserved.** | Expired historical policy never authorizes current live access; P8-20 remains separate. |
| `tests/test_result_ledger_authority.py` | Current result-authority test families exercise immutable history and correction; **historical regression equivalence still open**. | P8-09 must compare unique authority and financial invariants. |
| `scripts/apply_source_verification_metadata_governance.py` | Historical one-time metadata patch. **Recovery/migration artifact, not a routine user feature.** | Preserve on historical branch; never replay blindly against current registry. |
| `governance/reviews/*` historical quality snapshots | 25 retained historical closure/evidence paths, some branch-only. **Historical certification evidence only, not current runtime modules.** | Historical certification scope must not substitute current exact-tree tests, dependency audits, or source permission. |

## Accounting rules before P8-01 can become V

1. Process **all** unique historical branch contribution paths from the fixed
   193-branch baseline, including the 83 non-ancestor branches, not just the ten
   explicitly described path families above. Use the retained blob IDs and compare
   actual behavior and tests; ancestry and filename similarity are insufficient.
2. For every mandatory historical operator action, provide the exact native
   route/service/worker entrypoint, persisted source identity, positive and
   negative authority tests and observed cross-view result. Where an old feature
   is superseded, prove equivalence rather than merely stating it.
3. Classify each unmatched item as **integrated**, **superseded with a proven
   equivalent**, **setup-only/development-only**, **historical recovery/evidence**,
   or **still mandatory and open**. Explicitly distinguish commercial integration
   (P8-08/09), parcel/source resolution (P8-04), and report/export families
   (P8-11), none of which close merely because a legacy file exists.
4. Preserve historical branches and artifacts. Never mass-cherry-pick branch
   history, automatically restore old networking code, enable source authority,
   discard evidence, or alter the approved Command Center in pursuit of a count.

**Evidence for this bounded slice:** fixed JSON source inventory; current
`governance/capability_contract.toml`; actual P8-01/04/08/09/11 register;
the accepted P8-03 original-source parity and
`https://github.com/TruSudo/Construction-Sight/actions/runs/39532859099`
dual-Python application acceptance. This is a classification document, not a
certification or a passing execution test.

**Progress accounting:** P8-01 remains **O**. Integration acceptance remains
**10/15 = 67%**; P8-03 remains **20/20 = 100%**.
