# Lead Operator CLI

## Purpose

The lead operator CLI exposes persisted post-enrichment records without collapsing their evidence, limitations, confidence, workflow history, or result-share uncertainty.

The command is:

```text
constructionsight-leads
```

This is an operator and audit surface. It is not a GUI, outreach sender, CRM replacement, or claim of live source coverage.

## Record families

The CLI exposes these persisted record families:

| Kind | Persisted record | Supported list filters |
|---|---|---|
| `enrichment` | Opportunity enrichment report | `base_candidate_id` |
| `review` | Lead review package | `status`, `base_candidate_id` |
| `fingerprint` | Lead dedupe fingerprint | `base_candidate_id` |
| `duplicate` | Lead duplicate result | `status`, `base_candidate_id` |
| `workflow` | Lead workflow record | `status`, `base_candidate_id`, `workflow_id` |
| `event` | Lead workflow event | current `status`, `workflow_id` |
| `ledger` | Result ledger record | `status`, `workflow_id` |
| `share` | Result share record | `workflow_id` |

Unsupported filters fail explicitly. They are never silently ignored.

Every detail result includes the complete preserved JSON payload in addition to indexed operator fields. Reasons, limitations, notes, confidence fields, source identifiers, workflow events, and share-state uncertainty remain visible.

## Read commands

List records:

```text
constructionsight-leads list workflow --status review
constructionsight-leads list ledger --workflow-id lead-workflow:...
```

Show one complete record:

```text
constructionsight-leads detail workflow lead-workflow:...
```

Show matrix-valid next statuses:

```text
constructionsight-leads allowed-transitions lead-workflow:...
```

All commands accept `--database-url`. List and detail commands support `--json-output` for machine-readable use.

## Governed workflow transition

A persisted workflow transition is the only mutation exposed in this phase:

```text
constructionsight-leads transition \
  lead-workflow:... \
  review \
  --expected-current-status monitor \
  --reason "new evidence requires review" \
  --apply
```

The command requires all of the following:

- explicit `--apply` authorization;
- a nonblank audit reason;
- an operator-reviewed expected current status;
- exact current-state agreement between the expected status and persisted payload;
- indexed-column and full-payload integrity agreement;
- unique historical event identifiers;
- a transition allowed by the canonical workflow matrix;
- persistence through the existing workflow store, including the appended event.

The expected-current-status requirement is an optimistic stale-state guard. If another actor changes the workflow after review, the command refuses the transition instead of applying against an obsolete assumption.

## Event identity integrity

Workflow event identifiers previously depended only on workflow/status/reason values. A valid cycle could therefore repeat the same status pair and reason and reuse an earlier event identifier. Because event storage upserts by event ID, that could overwrite earlier history.

Event identity now includes the event sequence within the workflow. Workflow models also reject duplicate event IDs. Repeated transition cycles therefore retain distinct append-only event rows.

## Result ledger boundary

Ledger and share records are read-only in this phase.

The current result service can build outcome rows, but the repository does not yet define authoritative replacement or append-only history doctrine for multiple differing outcome records on one workflow. Exposing a mutable result command before that rule exists could create contradictory `won`, `lost`, or `no_fit` records for the same lead.

A future result mutation command must first define and test:

- whether one workflow has one authoritative current outcome or an append-only outcome history;
- replacement, correction, and supersession behavior;
- required relationship between workflow final status and ledger outcome;
- stale-state and duplicate-outcome protection;
- audit treatment for gross value and share-rate corrections.

## Safety boundary

The CLI does not:

- send outreach;
- bypass workflow transition rules;
- reopen final statuses;
- alter enrichment, review, fingerprint, duplicate, ledger, or share payloads;
- create live source coverage;
- suppress reasons, limitations, evidence, uncertainty, or event history.
