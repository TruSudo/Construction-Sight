# CEQAnet Official CSV Contract

## Purpose

ConstructionSight treats CEQAnet source-provided CSV exports as a distinct integration surface from HTML browsing and the existing guarded listing executor.

This phase is offline-first. It can build or parse an exact official export URL and inspect an already-obtained CSV body. It performs no network request, downloads no attachment, mutates no persistence, and does not change CEQAnet source maturity.

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

A request model always records `network_authorized=false` and `persistence_authorized=false`.

## Body inspection

`inspect_ceqanet_csv_bytes` accepts bytes that were obtained outside this contract. It does not fetch the URL.

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

## Evidence and replay

An inspection records:

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

Changing the request, body hash, columns, rows, counts, limitations, or flags invalidates the digest.

## Operator commands

```text
constructionsight-ceqanet-csv plan --sch-number <SCH> [--document-id <ID>]
constructionsight-ceqanet-csv inspect-file <path> --source-url <official CSV URL>
```

Both commands emit schema-versioned JSON. `inspect-file` may accept an observed content type and a maximum retained-row count. Neither command performs a network call.

## Current source maturity

CEQAnet remains `partial`.

This contract proves deterministic planning and offline validation only. It does not prove that a live CEQAnet CSV request is currently allowed, reliable, complete, or stable. The recorded automated HTML path returned HTTP 403 and remains blocked.

## Entry condition for live CSV proof

A separate phase may perform one explicitly authorized, bounded request to an observed official CSV URL only after it defines:

- the exact request being attempted;
- the user agent and media types;
- timeout and maximum body size;
- redirect and final-host rules;
- response content-type expectations;
- archive or hash retention;
- rate and retry policy;
- failure/no-bypass behavior; and
- whether source-specific clarification is required.

The response must pass this offline contract before any verified promotion, parser handoff, recurring schedule, or persistence mutation is considered.
