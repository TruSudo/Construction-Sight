# CS-SR-040 Permanent Closure Evidence

## Resolution

Production ArcGIS requests use the governed bounded transport with canonical complete query identity, redirect/auth/hook/environment restrictions, and source-specific evidence integrity checks.

Validated resolution head: `f773c926168c6284c171bfe05aac7f729c870ddc`

Resolution Git tree: `d9e084b83ee887ae65e16918592cc9410e06d87a`

Canonical CI run `36117450690` validated that exact head on Python 3.11 and Python 3.12.
Both isolated vulnerability audits passed. Ruff, mypy, compileall, full pytest, focused
mutation certification, adapter/source audits, assurance preflight,
repository/semantic certification, diff hygiene, and environment identity checks passed.
The only failing quality step was the intentional aggregate blocker for remaining active
defects.

## Evidence

- `src/constructionsight/operator_services/parcel_arcgis_service.py`
- `src/constructionsight/parcel_source_acquisition_http.py`

## Regression coverage

- `tests/test_arcgis_transport_semantic_equivalence.py`
- `tests/test_parcel_arcgis_operator_service.py`
- `tests/test_parcel_source_acquisition_http.py`

This closure preserves the original finding and retires only its corrected root cause.
Remaining active findings and final assurance obligations are unchanged.
