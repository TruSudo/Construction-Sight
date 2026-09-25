# ADR-0007: ArcGIS rehearsal transport type boundary

## Status

Accepted as a narrow, expiring compatibility exception.

## Context

`parcel_source_bulk_rehearsal_http.py` is the approved one-request ArcGIS transport. It needs the immutable rehearsal retry/policy types currently co-located in `parcel_source_bulk_rehearsal.py` and the exact in-memory response-envelope/JSON-decoding types currently co-located in `parcel_source_bulk_rehearsal_artifacts.py`.

The transport does not call the complete-rehearsal executor, checkpoint store, artifact-retention store, or any persistence mutation. Moving these shared types into a lower-level contract module is architecturally cleaner but would require a broader compatibility refactor across already-certified rehearsal code.

## Decision

Permit exactly two temporary architecture edges from `constructionsight.parcel_source_bulk_rehearsal_http`:

1. to `constructionsight.parcel_source_bulk_rehearsal`, limited to `ParcelArcGISBulkRehearsalPolicy` and `ParcelArcGISBulkTransientError`;
2. to `constructionsight.parcel_source_bulk_rehearsal_artifacts`, limited to `ParcelArcGISBulkCountResponse`, `ParcelArcGISBulkPageResponse`, and `decode_json_object`.

The exceptions do not authorize transport to execute workflow orchestration, write checkpoints, retain artifacts, mutate persistence, or broaden network authority.

## Consequences

The current exact-response HTTP adapter can remain behaviorally stable while the architecture certifier records the coupling explicitly instead of silently allowing it. The exception must expire and be replaced by a shared lower-level rehearsal contract module if the affected types change materially or if the transport begins needing any executor/store behavior.

## Verification

`tests/test_parcel_source_bulk_rehearsal_http.py` exercises request construction, exact response handling, bounded response behavior, retry classification, and fail-closed transport semantics. Canonical architecture and repository certification must continue to reject every other transport-to-application edge.
