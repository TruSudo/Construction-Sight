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

## Versioned scoring profile

Opportunity scoring is governed by a versioned profile, not anonymous hardcoded weights. The default profile is:

```text
profile key: opportunity-scoring:default
version: 2026-09-25.1
```

The default profile preserves the original behavior:

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

Configured weights are nominal evidence weights. Operational contribution is
confidence-weighted as `round(configured_weight * confidence_score / 100)`, then
capped at 100 across the report. Zero-confidence signals contribute zero
operational points. The report model independently recomputes both aggregate
confidence and the confidence-weighted lead score so caller-supplied values cannot
override those derivations.

The default profile also requires aggregate confidence of at least 70 before a
high-value score can produce an outreach-preview action. A nominally high score
with insufficient confidence remains review-bound.

Scores are capped at 100.

## Next action

The default next-action thresholds are deterministic:

- 70+ with no limitations and aggregate confidence 70+: prepare outreach preview
- 50+ or a high nominal score below the actionable-confidence floor: review limitations before outreach
- positive score below 50: monitor and enrich with more source evidence
- zero score: hold until a source signal appears

The enrichment report records the scoring profile key and version so later tuning does not erase the meaning of previously generated reports.

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

Later PRs can tune weights using real sales feedback from Ron's workflow by adding new profile versions while preserving old report semantics.
