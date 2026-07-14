# Parcel ArcGIS Complete-Rehearsal Proof Bundle

The portable complete-rehearsal proof layer turns a successful rehearsal execution into one self-contained, independently verifiable JSON artifact. It exists to prevent a future county rehearsal from being represented by loose manifests, checkpoint files, and response files whose relationship cannot be recomputed after the original runtime is gone.

## Bundle contents

`ParcelArcGISBulkRehearsalProofBundle` binds:

- the exact ArcGIS capability snapshot;
- the digest-bound rehearsal HTTP plan;
- the complete count-reconciled manifest and its structured page, checkpoint, resume, and retry evidence;
- proof that the checkpoint was durably reloaded;
- one embedded artifact for the starting-count response, every successful data page, and the ending-count response;
- exact artifact kind, sequence index, SHA-256 digest, byte size, safe portable file reference, and canonical base64 response body;
- explicit limitations; and
- `bulk_run_authorized=false`.

The bundle identity is a SHA-256 digest over every proof-bearing field except the artifact creation time. Any change to the snapshot, plan, manifest, evidence, response bytes, artifact metadata, limitations, or authority boundary changes or invalidates the identity.

## Exact-response verification

Each embedded response body is decoded from canonical base64 and checked against its declared byte size and SHA-256 digest. The first and last artifacts must be count responses; every middle artifact must be a page response in a contiguous sequence.

The verifier reparses both count bodies and requires them to equal the manifest's starting and ending counts. Every page body is reparsed using the snapshot's object-ID field, and the resulting ordered identifiers must exactly match the corresponding structured page evidence. Page artifact digests must also equal both the receipt sequence and the manifest page-response digest sequence.

## Independent recomputation

`verify_arcgis_bulk_rehearsal_proof_bundle` performs no network or database access. It:

1. rebuilds the HTTP plan from the snapshot and every retained plan parameter;
2. rebuilds the complete manifest from the snapshot and structured rehearsal evidence;
3. reconstructs the hardened execution receipt contract, including starting- and ending-count response digests;
4. reparses every embedded response body and object-ID sequence; and
5. rebuilds the complete bundle identity.

A verification result records that plan, manifest, response bytes, and object identifiers were independently recomputed. It cannot authorize import, profile promotion, recurring collection, or another network request.

## Atomic save and replay

Saving a bundle requires the exact expected bundle identity. The file is written through a temporary path and atomically replaced. An existing path is accepted only when it independently loads, verifies, and exactly equals the proposed bundle. Conflicting content fails closed.

Artifact references are informational portable file names only. Absolute paths, traversal components, nested paths, and backslash-separated paths are rejected. Exact response bytes remain embedded in the bundle and do not depend on the original filesystem store.

## Current boundary

The portable proof layer is implemented and tested with deterministic offline rehearsals. It does not expose a live county command and has not collected either official county dataset. San Bernardino and Riverside remain `bounded_query_verified`, not `bulk_rehearsal_verified`.

A later live-proof phase must separately authorize each county rehearsal, execute through the governed HTTP adapter, build and save this portable bundle, independently verify it from the saved JSON, and retain that verification before any profile-promotion review.
