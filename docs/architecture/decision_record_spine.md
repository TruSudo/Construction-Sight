# Decision Record Spine

Decision records are the pre-permit public decision layer in ConstructionSight's Shovels-style overlay.

## Core rule

Decision records should preserve source evidence and uncertainty. A CEQA notice, agenda item, staff report, planning commission hearing, or city council item can become an early opportunity signal before a permit exists, but it must remain traceable and confidence-scored.

## First decision signals

The first `DecisionRecord` supports:

- source key
- source record ID
- source kind
- decision kind
- title and normalized title
- decision/effective dates
- jurisdiction and county
- case number
- project name
- site key
- APN
- applicant/developer signal
- contractor key
- project value
- unit count
- source URL
- summary
- why-it-matters text
- confidence score and band
- reasons and limitations

## First matching behavior

The first `DecisionSiteMatch` supports:

- site-key match
- APN hint match
- matched / review-needed / unmatched status
- reasons and limitations

## Why this matters

This creates the pre-permit signal layer:

```text
CEQA / agenda / staff report / hearing item
  -> DecisionRecord
  -> site/APN hint
  -> DecisionSiteMatch
  -> opportunity enrichment before permit issuance
```

Later PRs can add agenda/staff-report intake and richer decision-to-parcel matching.
