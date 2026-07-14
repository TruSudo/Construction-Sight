# Parcel Longitudinal Evidence and Current Selection

ConstructionSight retains complete parcel source observations before deriving which record, if any, is safe to treat as current. This layer is additive: it does not change `ParcelCoreRecord`, historical parcel payloads, geometry behavior, site resolution, or the direct current-record interface of parcel assurance.

## Immutable observation boundary

`build_parcel_record_observation` copies one validated `ParcelCoreRecord` into a frozen `ParcelRecordObservation`. The observation contains:

- the complete canonical parcel record;
- a SHA-256 digest over that complete record;
- a second SHA-256 content digest that excludes only observation-specific parcel-record identity and observation time; and
- a deterministic `parcel-observation:` identity bound to the complete-record digest.

The complete digest detects any change to retained evidence. The content digest permits two separately retained observations of the same source content to be recognized as equivalent without discarding either observation. Source key, source-record ID, source-effective time, field values, geometry, limitations, and every other record field remain content-significant.

Observation and source-effective timestamps must be timezone-aware. The selection service normalizes timestamps to UTC for comparison while the retained record preserves its original JSON representation.

## Conservative current-selection rules

Selection is performed independently for each source key and only across observations for the same normalized APN and county.

| Available source times | Governing rule | Safe outcome |
|---|---|---|
| Every observation has source-effective time | Latest source-effective instant | Select only if the leading content is unambiguous. |
| No observation has source-effective time | Latest observation instant | Select only if the leading content is unambiguous. |
| Some observations have source-effective time and others do not | The clocks are incomparable | Retain every observation as a current candidate and require review. |
| Governing-time tie with equivalent content | Latest observation instant, then deterministic observation identity | Select one evidence representative; retain and supersede the equivalent observations explicitly. |
| Governing-time tie with different content | Competing current candidates | Select nothing and require review. |

A source record observed later cannot displace a record with a newer source-effective time. Observation time is never used to break a content conflict between records tied at the governing source-effective instant.

## Explicit supersession

Every source selection includes one disposition for every supplied observation:

- `current` identifies the unique governed current observation;
- `current_candidate` preserves each unresolved leading observation; and
- `superseded` identifies every observation it is superseded by.

When leading content is ambiguous, older comparable observations name every current candidate as a possible successor. The selection report does not invent a singular successor before the leading conflict is resolved. Supersession is derived evidence; immutable source observations are never updated or deleted.

`ParcelCurrentSelectionReport` has a deterministic `parcel-current-selection:` identity over the complete per-source selection evidence, excluding only report generation time. Report status is `complete` only when every source has exactly one current observation. Otherwise it is `review_required`.

## Assurance integration

`build_longitudinal_parcel_assurance` requires source contexts to match the observed source keys exactly. It performs current selection first.

- A complete selection passes only the selected parcel records into the existing field-level assurance builder.
- Any ambiguous source returns `blocked_review` with no assurance report.
- Superseded observations remain retained evidence but cannot contribute claims, agreement, authority, or corroboration to current assurance.

The original `build_parcel_assurance_report` interface remains available for callers that already possess a governed current set. The longitudinal entry point is the safe path when multiple observations per source are present.

## Persistence and operator access

Two additive tables preserve the new layer:

- `parcel_record_observations` stores immutable, exact-idempotent observation payloads and indexed source, parcel, time, and digest fields; and
- `parcel_current_selection_reports` stores immutable, semantic-idempotent selection reports and indexed parcel, status, review, source-count, current-count, ambiguity-count, and generation fields.

An exact observation replay returns the existing row. Reuse of an observation identity for different payload content is rejected. A selection report replay that differs only by generation time returns the existing row; any other identity collision is rejected.

Typed replay loaders revalidate observation/report models, recompute digest-bound identities, and compare every indexed field with the preserved payload. Malformed JSON, invalid models, changed digests, and indexed/payload drift are rejected before replayed observations can reach selection or assurance.

The read-only upstream operator exposes `parcel_observation` and `parcel_current_selection` list/detail records. Observation filters support source key, source-record ID, normalized APN, and county. Selection filters support status, normalized APN, and county. No generic parcel mutation or conflict-resolution action is added.

## Compatibility

This layer adds no required `ParcelCoreRecord` field and does not change existing parcel IDs, tables, update behavior, assurance outcomes, geometry parsing, or site matching. Existing database initialization creates the additive tables. Historical databases and payloads remain readable.

## Current limits

This phase does not:

- acquire San Bernardino or Riverside County parcel, roll, tax, recorder, zoning, planning, permit, or CEQA data;
- establish lawful access, source coverage, source freshness, countywide completeness, legal title, or survey-grade boundaries;
- infer a missing source-effective timestamp;
- choose between same-time conflicting content;
- resolve cross-source field conflicts;
- register county-specific proposition authority or dependency lineage automatically; or
- make the existing mutable parcel-core table an evidence ledger.

Countywide source acquisition, retained raw source artifacts, field-authority registration, coverage accounting, and recurring update orchestration remain separately governed work. New acquisition paths must create and store immutable observations before deriving current selection and assurance.
