# Opportunity Transition Intake

ConstructionSight treats a public record as evidence first and a lead second. A permit, CEQA notice, agenda item, staff report, or contractor record becomes commercially useful when it exposes a transition event: something changed, advanced, appeared, moved, or became actionable.

## Core rule

The actionable value is the transition event, not the static record.

The opportunity layer consumes universal intake records and converts extracted material facts into source-neutral opportunity candidates. It does not replace source-specific adapters. It provides a common decision layer so CEQAnet, Accela, EnerGov, agenda packets, staff reports, GIS records, CSLB records, PDFs, emails, spreadsheets, and manual notes can all route toward the same lead workflow.

## Transition signals

The first deterministic signal set covers the events most likely to matter for construction-site-security lead generation:

- lawful source record observed
- CEQA or environmental-review signal
- permit application or filing signal
- issued permit signal
- contractor identified signal
- valuation or budget signal
- inspection movement signal
- expiration or finalization signal
- site, parcel, APN, or address anchor
- contact channel signal
- public agency anchor
- construction-scope signal

## Scoring purpose

Lead score is not truth. It is operational triage. The score ranks which preserved records deserve enrichment, deduplication, relationship expansion, outreach preview, or monitoring.

The score is intentionally capped at 100 and is derived from transition-event score deltas. A record with an SCH number, issued permit language, contractor/license signal, valuation, APN/address, contact channel, and construction keywords should become outreach-ready. A record with only a weak source observation should remain archived or monitored.

## Readiness bands

- `not_qualified`: preserve/archive unless future transition movement appears.
- `monitor`: watch for issuance, contractor, valuation, inspection, expiration, or CEQA movement.
- `research_ready`: enrich parcel, entity, permit, agenda, and contractor context before outreach.
- `outreach_ready`: enrich contacts, deduplicate, and prepare outreach preview.

## Product boundary

This layer does not send emails, create bids, or claim that a project is verified. It creates a lead candidate with explicit transition events, reasons, limitations, confidence band, score, priority, and recommended next action. Later outreach and bid modules can consume that candidate only after deduplication, enrichment, and user preview.
