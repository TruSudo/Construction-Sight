# Parcel ArcGIS Complete-Rehearsal HTTP Adapter

The complete-rehearsal HTTP layer binds official ArcGIS query endpoints to the exact-response source protocol used by `execute_arcgis_complete_rehearsal`. It is a read-only proof transport. It is not an importer, scheduler, profile-promotion mechanism, or bulk-run authorization surface.

## Deterministic plan

`ParcelArcGISBulkRehearsalPlan` binds:

- the exact capability snapshot, verification profile, source key, and county;
- the HTTPS layer `/query` endpoint;
- the unique object-ID field;
- page size, checkpoint location, resumed-segment fault-injection page, bounded attempts, and retry delays;
- timeout and maximum response-byte limits;
- retry-eligible HTTP status codes and accepted JSON media types;
- a timezone-aware generation time; and
- an explicit `bulk_run_authorized=false` boundary.

The plan identity is a SHA-256 digest over the complete canonical payload. Changing any scope, transport, retry, checkpoint, or response-limit value changes the plan identity. Building a plan performs no network request.

## Retry ownership

The HTTP source performs exactly one HTTP request for each `fetch_count` or `fetch_object_id_page` call. It contains no internal retry loop. This is deliberate: retry sequencing, attempt count, delay application, injected-fault evidence, and exhaustion remain owned by the complete-rehearsal executor, where they are retained in the structured retry proof chain.

Transport failures and configured HTTP or ArcGIS service error codes are converted to `ParcelArcGISBulkTransientError`. Terminal statuses, malformed service errors, invalid JSON, redirect behavior, endpoint changes, response-policy violations, and query-scope violations fail immediately.

## Exact request contract

Count requests use only:

```text
f=json
where=1=1
returnCountOnly=true
returnGeometry=false
```

Page requests use only:

```text
f=json
where=1=1
outFields=<object-id-field>
orderByFields=<object-id-field> ASC
resultOffset=<page-aligned offset>
resultRecordCount=<planned page size>
returnGeometry=false
```

The source rejects negative or misaligned offsets, page sizes that differ from the plan, and attempt numbers outside the planned bound. Geometry is never requested.

## Response boundary

Every request must:

- remain on the planned HTTPS scheme, host, and `/query` path;
- return directly without redirect history;
- return HTTP 200 unless the status is explicitly classified as retryable;
- use a permitted JSON-compatible media type;
- remain within both declared and streamed response-byte limits;
- contain a nonempty strict UTF-8 JSON object; and
- contain no terminal ArcGIS service error.

Successful response bytes are returned unchanged in `ParcelArcGISBulkCountResponse` or `ParcelArcGISBulkPageResponse`. The executor then atomically retains those exact bytes in its digest-addressed artifact store before accepting the corresponding proof.

## Current boundary

The adapter and plan are implemented and tested with `httpx.MockTransport`, including an end-to-end complete-rehearsal execution. No live countywide rehearsal command is exposed, and neither official county source has been executed through this adapter. San Bernardino and Riverside therefore remain `bounded_query_verified`, not `bulk_rehearsal_verified`.

A later live-proof phase must separately authorize each county execution, retain every exact response artifact and checkpoint, independently verify the final manifest, and review any source-profile promotion as a distinct decision.
