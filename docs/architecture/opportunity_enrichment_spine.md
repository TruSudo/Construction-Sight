# Opportunity Enrichment Spine

Opportunity enrichment is ConstructionSight's native advantage layer above parcel, permit, contractor, and decision signals.

## Core rule

A lead score must be explainable. Every score contribution must come from a named signal with a reason, confidence, and limitations.

## First signal layers

The first implementation supports:

- parcel/site signal
- permit transition signal
- contractor identity signal
- public decision signal

## First scoring behavior

```text
resolved site anchor: +20
ambiguous/partial site anchor: +10
new permit record: +10
permit status change: +20
permit value change: +15
permit contractor change: +15
permit date change: +10
permit site change: +20
permit description change: +5
contractor identity with license: +15
contractor identity without license: +8
public decision with site/APN hint: +15
public decision without site/APN hint: +10
```

Scores are capped at 100.

## Next action

The first next-action logic is deterministic:

- 70+ with no limitations: prepare outreach preview
- 50+ with limitations: review limitations before outreach
- positive score below 50: monitor and enrich with more source evidence
- zero score: hold until a source signal appears

## Why this matters

This is where ConstructionSight stops being a data collector and becomes a sales-intelligence tool:

```text
parcel/site anchor
  + permit movement
  + contractor identity
  + public decision signal
  -> explainable lead score
  -> next action
```

Later PRs can tune weights using real sales feedback from Ron's workflow.
