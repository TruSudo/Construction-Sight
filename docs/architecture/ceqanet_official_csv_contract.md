# CEQAnet Official CSV Contract

## Purpose

ConstructionSight treats CEQAnet source-provided CSV exports as a distinct integration surface from HTML browsing and the existing guarded listing executor.

The contract now has two governed layers:

1. deterministic URL planning and offline inspection; and
2. one-request live proof execution with independently verifiable response evidence.

It downloads no CEQA attachment, mutates no persistence, schedules no work, retries no request, and does not change CEQAnet source maturity.

## Supported URL identities

The approved host and path are:

```text
https://ceqanet.lci.ca.gov/Search
```

Two exact query shapes are supported.

Project export:

```text
OutputFormat=CSV&Sch=<10-digit SCH number>
```

Document export:

```text
DocumentId=<positive integer>&OutputFormat=CSV&Sch=<10-digit SCH number>
```

The parser rejects:

- non-HTTPS URLs;
- another host or path;
- credentials, ports, fragments, or path parameters;
- missing, duplicated, blank, or extra query keys;
- a format other than `CSV`;
- a malformed SCH number; and
- a nonpositive document ID.

The reusable request model records `network_authorized=false` and `persistence_authorized=false`. Network authority is never embedded in the reusable URL artifact; it must be supplied separately for each live attempt.

## Offline body inspection

`inspect_ceqanet_csv_bytes` accepts bytes that were obtained outside the offline contract. It does not fetch the URL.

The inspection boundary:

1. reparses the source URL and requires complete agreement with the request fields;
2. caps the body at 10,000,000 bytes;
3. permits only explicit CSV-compatible media types when a content type is supplied;
4. decodes UTF-8 with optional BOM;
5. rejects NUL bytes and malformed CSV syntax;
6. requires a nonblank, uniquely normalized header;
7. rejects multiple columns that map to the same canonical role;
8. requires at least one data row;
9. requires every row to have the exact header width;
10. requires an identifiable SCH-number column;
11. requires every row SCH number to be ten digits and equal the request SCH number;
12. preserves unknown columns without assigning unsupported meaning;
13. retains a bounded number of normalized rows while preserving the total row count; and
14. binds the complete inspection evidence with a canonical SHA-256 digest.

## Canonical roles

The first contract recognizes aliases for:

- SCH number;
- document ID;
- document type;
- lead agency;
- received date;
- title;
- county;
- location;
- description;
- contact name, email, and phone; and
- parcel number.

Original names, normalized names, ordinal position, and optional canonical roles are all retained. An unrecognized column remains in the normalized row and is listed in `unknown_columns`.

## One-request live execution

`execute_ceqanet_csv_live_request` requires explicit per-attempt authorization. It then:

1. reparses the request URL and requires exact request-model agreement;
2. permits one GET request only;
3. performs no retry;
4. uses an honest ConstructionSight user agent and CSV-oriented `Accept` header;
5. follows redirects only so the final URL can be inspected;
6. applies an explicit timeout;
7. enforces the 10,000,000-byte ceiling;
8. retains the complete response body as Base64 when within the ceiling;
9. preserves the complete-body byte length and SHA-256 even when an oversized body is not retained;
10. records status, final URL, content type, content disposition, errors, and execution time;
11. records explicit no-document-download and no-persistence-mutation assertions;
12. invokes the canonical offline inspector only for an HTTP 200 complete body; and
13. binds the complete retained execution envelope with a canonical digest.

An HTTP 403, non-CSV response, malformed CSV, oversized response, redirected identity, or network error remains an explicit failed artifact. The executor does not retry, alter headers to impersonate a browser, bypass access controls, or silently reinterpret failure as success.

## Independent live verification

`verify_ceqanet_csv_live_execution` operates offline and independently checks:

- execution-envelope digest integrity;
- request URL agreement;
- final official host, `/Search` path, and exact query identity;
- GET-only and zero-retry state;
- network-executed truth;
- no document download and no persistence mutation;
- HTTP 200 and absence of an execution error;
- Base64 validity;
- retained and observed byte counts;
- complete-body SHA-256;
- complete-body retention;
- successful canonical offline inspection;
- inspection digest integrity; and
- exact agreement between the stored inspection and a recomputation from retained bytes.

Literal-safe model fields do not replace these semantic checks. The verifier deliberately widens its local views so post-construction tampering through unsafe object-copy operations is still detected.

## Evidence and replay

An offline inspection records:

- exact export request identity;
- normalized content type when supplied;
- encoding and delimiter;
- byte length and complete-body SHA-256;
- columns and canonical roles;
- total and retained row counts;
- retained normalized rows;
- truncation state;
- unknown columns;
- limitations/warnings;
- no-network and no-persistence assertions; and
- an inspection digest over all retained evidence.

A live execution additionally records the exact response envelope and embeds the inspection when valid. Changing the request, URL, response body, body hash, headers, status, errors, inspection, limitations, or safety flags invalidates the execution or inspection digest.

## Operator commands

```text
constructionsight-ceqanet-csv plan --sch-number <SCH> [--document-id <ID>]
constructionsight-ceqanet-csv inspect-file <path> --source-url <official CSV URL>
constructionsight-ceqanet-csv execute-live --sch-number <SCH> --output <artifact> --execute-live
constructionsight-ceqanet-csv verify-execution <artifact> [--output <verification>]
```

`plan`, `inspect-file`, and `verify-execution` perform no network call. `execute-live` requires explicit authorization, writes the execution artifact before returning a failing exit code, and will not overwrite an existing artifact unless `--overwrite` is supplied.

## Current source maturity

CEQAnet remains `partial`.

The implementation now proves deterministic planning, strict offline validation, and a bounded live-proof mechanism. It does not yet prove that the current official CSV endpoint returns a reliable valid CSV response to ConstructionSight. The recorded automated HTML path returned HTTP 403 and remains blocked.

## Next gate

A separate, self-removing evidence phase may perform one project-scoped request for observed SCH `2026030377`.

The resulting success or failure artifact must be committed with an offline verification report and reviewed before any source-status promotion, parser handoff, recurring schedule, rate policy, persisted attempt ledger, or persistence mutation is considered.
