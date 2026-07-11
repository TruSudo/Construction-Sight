# Upstream Operator CLI

## Purpose

The upstream operator CLI exposes persisted permit, contractor, decision, parcel, and site-resolution records without modifying observed evidence or bypassing the domain builders that created those records.

The command is:

```text
constructionsight-upstream
```

This is a read-only operator and audit surface. It is not a source adapter, ingestion engine, record editor, outreach system, or claim of live source coverage.

## Record families

| Kind | Persisted record | Supported list filters |
|---|---|---|
| `permit_snapshot` | Source-neutral permit snapshot | `status`, `source_key`, `source_record_id`, `site_key` |
| `permit_transition` | Detected permit movement | `source_key`, `source_record_id` |
| `contractor` | Conservative contractor identity | `status` |
| `decision` | Public decision or pre-permit signal | `source_key`, `source_record_id`, `site_key`, `apn` |
| `parcel` | Canonical parcel core record | `source_key`, `source_record_id`, `apn`, `county` |
| `site_resolution` | Source-neutral site-resolution result | `status`, `site_key` |

Unsupported filters fail explicitly. They are never silently ignored.

## Commands

List newest records:

```text
constructionsight-upstream list permit_snapshot --status issued
constructionsight-upstream list decision --site-key site:...
constructionsight-upstream list parcel --county "San Bernardino" --apn 0123-456-78
```

Show one record and its complete preserved payload:

```text
constructionsight-upstream detail contractor contractor:...
constructionsight-upstream detail site_resolution site-resolution:...
```

Both commands accept `--database-url`. They support `--json-output` for machine-readable use.

## Payload preservation

Each result contains a normalized operator envelope and the complete persisted JSON payload. The CLI does not flatten or discard:

- source identifiers;
- reasons and limitations;
- confidence scores;
- APN and site anchors;
- geometry limitations;
- transition values;
- conflict and candidate details;
- future payload fields not promoted to indexed columns.

Malformed payload JSON fails explicitly rather than returning a partial or misleading record.

## Mutation boundary

No mutation command is exposed in this phase.

These upstream records are either observed facts or deterministic products of existing domain services. Editing them through a generic operator command would bypass source evidence, normalization, identity-resolution, transition-detection, geometry, and confidence rules.

Future upstream actions must be domain-specific. They must call the canonical builder or transition service, preserve the original source evidence, and define stale-state, correction, supersession, and audit behavior before a write command is added.

## Safety boundary

The CLI does not:

- edit permit snapshots or transitions;
- alter contractor identities;
- rewrite decision records;
- mutate parcel geometry or identity;
- change site-resolution candidates or conflicts;
- create or verify live source coverage;
- suppress reasons, limitations, confidence, provenance, or uncertainty;
- send outreach.
