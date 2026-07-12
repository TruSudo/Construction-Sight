# CEQAnet Official CSV Export Contract

## Purpose

ConstructionSight uses the source-provided CEQAnet CSV export surface as the preferred next integration boundary after bounded HTML automation produced inconsistent access results, including HTTP 403.

This contract does not bypass the HTML response, disguise the client, download CEQA attachments, mutate persistence, schedule recurring work, or change the canonical CEQAnet maturity state.

## Supported official requests

The deterministic request builder supports two observed source-provided forms:

```text
https://ceqanet.lci.ca.gov/Search?OutputFormat=CSV&Sch=<10-digit-SCH>
https://ceqanet.lci.ca.gov/Search?DocumentId=<positive-id>&OutputFormat=CSV&Sch=<10-digit-SCH>
```

The first is project-scoped. The second is document-scoped. Both are GET-only, remain on the approved official HTTPS host and `/Search` path, and explicitly state `OutputFormat=CSV`.

## Operator surface

```text
constructionsight-ceqanet-csv plan
constructionsight-ceqanet-csv execute
constructionsight-ceqanet-csv parse
constructionsight-ceqanet-csv verify
```

`plan` performs no network access. `execute` requires explicit `--execute-live` authorization for one bounded request. `parse` and `verify` operate offline against retained artifacts.

## Evidence model

An execution artifact preserves:

- exact request model and deterministic request URL;
- final URL;
- HTTP status;
- content type and content disposition;
- exact response bytes encoded as Base64;
- response byte length and SHA-256;
- network-execution truth;
- explicit no-document-download and no-persistence-mutation assertions;
- error classification, when applicable;
- execution timestamp; and
- a canonical digest over all retained evidence except timestamp and the digest field itself.

Unknown top-level fields and unsupported schema versions are rejected.

## Verification

Verification independently checks:

- execution digest integrity;
- deterministic request URL agreement;
- official HTTPS host;
- exact `/Search` path;
- query identity and ordering;
- GET-only request identity;
- HTTP 200 response;
- absence of execution errors;
- exact Base64 decoding, byte length, and SHA-256;
- no document download;
- no persistence mutation; and
- strict offline CSV parsing.

A recomputed digest cannot make a semantically altered host, path, query, response, or mutation claim valid.

## CSV parsing

Parsing uses the Python standard-library CSV parser with UTF-8 BOM support. It requires:

- one nonblank header row;
- unique headers;
- no rows containing more values than headers; and
- complete lossless source-text values keyed by the normalized header text.

No semantic field inference or persistence is performed in this phase. A later mapping phase must preserve raw headers, raw values, unknown fields, provenance, and parse limitations.

## Current maturity boundary

The canonical CEQAnet source remains `partial` until a bounded live CSV proof succeeds and is reviewed in a separate evidence phase. This contract alone is not verified source coverage and does not authorize recurring scheduling.

## Next gate

Run one bounded project-scoped CSV export using an observed public SCH number, retain and verify the execution artifact, inspect the actual header/row contract, and record any HTTP, content-type, schema, or data-quality limitation before considering source promotion or recurring operation.
