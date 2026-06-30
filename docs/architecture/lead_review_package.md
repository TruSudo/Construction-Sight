# Lead Review Package

Lead review packages convert opportunity enrichment into a reviewable operator package.

## Core rule

No external sales action should be implied by scoring alone. The review layer must classify the lead, preserve evidence notes, preserve limitations, and provide a deterministic next step.

## Statuses

The first implementation supports:

- `hold`
- `monitor`
- `review_required`
- `ready`

## Status logic

```text
score 0 -> hold
score below 50 -> monitor
score 50+ with limitations -> review_required
score 50+ without limitations -> ready
```

## Package contents

A `LeadReviewPackage` includes:

- package ID
- base candidate ID
- lead score
- review status
- summary
- review items
- evidence notes
- limitations
- review note

## Why this matters

Opportunity enrichment creates score and reasons. The review package turns that into an operational lane that can later support outreach preview, duplicate suppression, sales status, and royalty tracking without mixing those concerns into the scoring engine.
