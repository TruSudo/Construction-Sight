# Exhaustive Lawful Intake and Progressive Understanding

ConstructionSight treats every stated objective as requiring the most complete lawful, relevant, and verifiable understanding possible. The system does not presume that every future source layout is already known. It instead uses a finite digital-format intake boundary, preserves every lawful input exactly, extracts all recognizable material facts, and routes unknown structure for review or adapter development.

## Operating rule

Formats are finite. Layouts are variable. Meaning is contextual. Evidence must be preserved. Understanding must be progressive. Normalization must be universal.

## Source-neutral intake flow

```text
lawful digital input
  -> evidence preservation
  -> binary/structural format detection
  -> generic material-fact extraction
  -> source-family routing when declared or detected
  -> unmapped evidence preservation
  -> human review or adapter backlog when understanding is incomplete
  -> lead/opportunity intake when enough universal facts exist
```

## Finite format families

The universal intake layer classifies inputs into high-level digital evidence families instead of hard-coding every agency layout:

- plain text
- HTML
- XML
- JSON
- JSONL
- CSV
- TSV
- PDF
- DOCX
- XLSX
- PPTX
- ZIP
- email
- image
- media
- SQLite
- binary
- unknown

This gives the system binary-level structure without pretending every source layout is already understood.

## Progressive understanding statuses

- `preserved_only`: the input is preserved but not safely understood.
- `format_detected`: the format family is known but no material facts were extracted.
- `partially_understood`: some material facts were extracted, but source-specific structure may remain unmapped.
- `structured`: a future source adapter has mapped the input into a known structured contract.
- `adapter_ready`: the source pattern is stable enough for source-specific adapter development.
- `unsupported`: processing is rejected or unavailable under current rules.

## Universal material facts

The first generic extractor targets source-neutral anchors useful across construction intelligence workflows:

- address
- APN
- SCH number
- permit number
- CSLB license
- email
- phone
- URL
- money
- date
- agency
- project title
- person or organization
- construction keywords

Source-specific adapters can later extract more, but the universal layer must never discard unknown material merely because no adapter exists yet.

## Routing outcomes

- `generic_extraction`: run or rerun generic extraction.
- `source_adapter`: route to a declared or detected source-family adapter.
- `human_review`: preserve and require review before mapping.
- `adapter_backlog`: preserve unmapped structure as a candidate for repeatable adapter development.
- `opportunity_intake`: send extracted facts toward lead-candidate and opportunity normalization.
- `archive_only`: preserve with no extraction path.
- `reject`: do not process under current lawful access or safety rules.

## Engineering purpose

This layer is the bridge between source-specific adapters and the broader ConstructionSight product. CEQAnet, Accela, EnerGov, agendas, staff reports, GIS records, CSLB records, manual notes, emails, PDFs, and future inputs should not become isolated silos. Each input first becomes a preserved evidence record and universal intake record. From there, qualifying facts can become lead candidates, opportunities, entity relationships, site/parcel records, outreach actions, and bid records.
