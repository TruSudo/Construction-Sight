# County ArcGIS Bounded Proof Evidence — 2026-07-14

## Scope

This phase executed one explicitly bounded four-request, geometry-disabled ArcGIS probe for each official county parcel source. It retained portable proof bundles, independently verified each bundle offline, and exercised exact-identity transactional persistence against an ephemeral SQLite database.

No countywide parcel download, verification-profile promotion, production scheduling, recurring authority, or bulk authorization was performed.

## Results

| County | Source key | Assessment | Observations | Offline verification | Persistence authorized | Bulk authorized | Bundle ID |
|---|---|---|---:|---:|---:|---:|---|
| San Bernardino | san-bernardino:county-gis-parcels | bounded_query_verified | 4 | true | true | false | `parcel-arcgis-bounded-proof-bundle:c3edb797417fef70d4a34672193e53679c811d91e0cab58dd5aa44dd1101d2a1` |
| Riverside | riverside:county-gis-parcels | bounded_query_verified | 4 | true | true | false | `parcel-arcgis-bounded-proof-bundle:49c20754f092ac960601ee7d03a4bcc9ef0c1fb4c71deefa295c3863e151f3f5` |

## Retained artifacts

- `evidence/source_verification/san_bernardino_arcgis_bounded_proof_2026-07-14.json`
- `evidence/source_verification/riverside_arcgis_bounded_proof_2026-07-14.json`
- `evidence/source_verification/san_bernardino_arcgis_bounded_proof_verification_2026-07-14.json`
- `evidence/source_verification/riverside_arcgis_bounded_proof_verification_2026-07-14.json`
- `evidence/source_verification/san_bernardino_arcgis_bounded_proof_persistence_2026-07-14.json`
- `evidence/source_verification/riverside_arcgis_bounded_proof_persistence_2026-07-14.json`

## Governing boundary

A successful bounded proof establishes only the observed count/page/replay behavior against the refreshed schema snapshot. It does not establish legal-title accuracy, surveyed geometry, countywide completeness, stable long-term pagination, import readiness, or authority to run a complete acquisition.
