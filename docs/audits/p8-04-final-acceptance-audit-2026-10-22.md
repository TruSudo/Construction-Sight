# P8-04 final acceptance audit — 2026-10-22

**Scope:** The pre-existing P8-04 twelve-item acceptance contract, not a new
feature or requirement. This document is an explicit final-gate audit; it does
not certify live external county data, complete the owner-data gate (P8-07),
approve deployment (P8-19) or alter visual-reference parity (P8-17).

## Verified implementation chain

1. **Original source and historical observation:** The current approved source
   registry, exact retained bounded ArcGIS proof, source-specific field mapping,
   verified OBJECTID page membership and schema fingerprint are required. The
   official URL is derived from the registry rather than operator input.
2. **Separate source-read approval:** Existing current lawful-access assessment,
   scoped local operator authorization, single-use effect lease and CS-NET-004
   bounded HTTP transport control one explicit source read. Normal app navigation
   and preview perform no external GET. Source access unknown/denied stays denied.
3. **Original response preservation:** One response OBJECTID, expected registered
   attributes, no geometry, JSON/content limits, and original parser readiness
   are enforced. Actual returned bytes are retained with SHA-256; no inferred
   parcel attributes, coordinates, geometry or independent project identity.
4. **Separate parcel-persistence approval:** The retained bytes are checked
   against the same proof and re-parsed before the original
   `build_parcel_core_record_from_preview` is used. A second consent persists
   one evidence-bound `ParcelCoreRecord` and immutable parcel observation in
   the existing private investigation schema. Conflicting source identity and
   contradictory/stale revisions fail closed rather than overwrite.
5. **Separate native-investigation approval:** Before a third explicit review
   the native worker has no investigation. The existing original
   `_queue_sources` replay and native worker then commit the exact source claim
   to the single shared investigation reality. Unmapped evidence stays
   unmapped; dossier and embedded/full-screen relationship graph reference the
   same original evidence. No commercial lead, outreach, bid or royalty is
   automatically authorized.

## Acceptance evidence

| Obligation | Focused evidence | Disposition |
| --- | --- | --- |
| Source-specific proof and manual row interpretation | `tests/test_native_arcgis_proof_persistence.py` | Verified |
| One exact official object-ID request plan | `tests/test_native_arcgis_proof_persistence.py` | Verified |
| Explicit reviewed bounded transport and response bytes | `tests/test_native_arcgis_single_record_acquisition.py` | Verified with mocked external transport |
| SHA-bound reviewed parcel persistence, tamper and retry denial | `tests/test_native_arcgis_parcel_import.py` | Verified with synthetic retained bytes |
| Separately reviewed worker, missing/tampered evidence and conflicting identity denial | `tests/test_native_arcgis_investigation_cross_view.py` | Verified with synthetic retained bytes |
| Native browser Sources action, third approval and original commercial controls | `tests/ui/source_inspection.js` | Verified with synthetic source data |
| Python 3.11 and 3.12, Ruff, strict Mypy, complete regression | GitHub Actions run `39746706213`, commit `92ad8a82` | Success: 2,923 tests passed each |
| Command Center structure, behavior, graph and USGS | GitHub Actions run `39746706320`, commit `92ad8a82` | Success |

## Last checkpoint disposition — P8-04-12

**Open (O).** The individual source, persistence and worker pathways have
passed at the preceding exact application HEAD. A single certified end-to-end
read-through-persist-through-queue-through-worker final acceptance test with
all relevant authority, retry, source-replacement and offline/no-geometry
negative controls needs to be gathered in the final-head acceptance package.
A permissioned real-source execution is separately controlled by P8-20 and
must not be silently represented by an HTTP mock; incomplete owner-data
reconciliation is P8-07. The absence of a verified current rights profile
must not be overridden merely to close this gate.

**Meter:** P8-04 = 11/12 = **92%**. P8-03 = 20/20 = 100%.
Phase 8 accepted integration = 10/15 = **67%**. Nothing in this audit
constitutes an independent full-product completion claim.

## Next proof needed

Carry one immutable synthetic receipt through a source-access permission
review, exact-body validation, separately approved parcel store, third
approval, worker processing, and cross-view assertions in one end-to-end
regression. Include ambiguous or conflicting identities, forged extra
attributes, tampered SHA, stale replay expectations, no source geometry,
unchanged retained bytes and no unreviewed commercial authority.
Only mark P8-04-12 verified when that focused acceptance and applicable
exact final-head CI/browser gates pass. Keep the owner permissioned
live-source and device/deployment acceptance separate.
