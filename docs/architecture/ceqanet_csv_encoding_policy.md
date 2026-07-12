# CEQAnet CSV Encoding Policy

## Purpose

CEQAnet CSV bodies are decoded under an explicit source-specific policy. Encoding fallback is evidentiary behavior, not a permissive cleanup mechanism.

## Selection order

1. Decode strictly as UTF-8 with optional BOM (`utf-8-sig`).
2. Only when strict UTF-8 fails, decode strictly as Windows-1252.
3. Reject the body when both decoders fail.

The parser does not use replacement characters, error suppression, heuristic character detection, or generic ISO-8859-1/Latin-1 fallback.

## Why Windows-1252 is supported

The bounded CEQAnet project CSV proof returned HTTP 200 with a complete 7,832-byte `text/csv` body. The retained response contained byte `0x95`, which is the bullet character in Windows-1252 and is invalid UTF-8. The original UTF-8 inspection failure remains immutable evidence.

A later offline replay decoded the exact retained bytes as Windows-1252 and passed the existing CSV structural, header, row-width, SCH-number, body-hash, and digest checks without another network request.

## Evidence requirements

The selected encoding is stored inside `CeqanetCsvInspection` and therefore participates in the inspection digest. A Windows-1252 inspection also records a warning that strict UTF-8 failed before fallback was selected.

A derived encoding replay must bind:

- the original live execution digest;
- the original response SHA-256;
- the original response byte length;
- the original request URL and HTTP status;
- the complete derived inspection; and
- an independent replay digest.

Replay verification recomputes the inspection from the original retained bytes. It performs no network request and authorizes no persistence mutation.

## Boundaries

Windows-1252 compatibility does not imply:

- acceptance of arbitrary binary or malformed content;
- acceptance of an HTML error page as CSV;
- generic Latin-1 decoding;
- source promotion;
- recurring collection;
- retries;
- attachment downloads; or
- persistence ingestion.

All existing CSV structural and identity checks remain mandatory. CEQAnet source maturity remains a separate controlled decision.
