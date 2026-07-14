# Parcel Fact Assurance

ConstructionSight now derives explainable, field-level assurance from current canonical parcel records without replacing or mutating those records.

## Integration boundary

The assurance builder accepts:

- one or more existing `ParcelCoreRecord` objects for the same normalized APN and county;
- exactly one current record per source key;
- an explicit `ParcelAssuranceSourceContext` for every supplied source; and
- the parcel fields to evaluate.

Each source context carries a dependency-lineage key, default evidence class, proposition-specific authoritative fields, and limitations. The builder never infers independence or authority from a source name, URL, provider type, or the number of websites displaying the same upstream data.

Existing parcel records, parcel storage, site resolution, geometry behavior, and operator payloads are unchanged. Assurance is a new derived layer above them.

## Field-level claims

For every populated requested field, the builder emits a deterministic `parcel-claim:` record that preserves:

- the canonical parcel-record ID;
- source key and source-record ID;
- dependency-lineage key;
- field role;
- original and normalized comparison values;
- proposition-specific authority;
- direct, deterministic-derivation, or inference method;
- evidence reference;
- source-effective and observed timestamps; and
- combined record, source, and geometry limitations.

The initial builder consumes direct fields already present in `ParcelCoreRecord`: APN, address, county, state, jurisdiction, zoning, land use, acreage, geometry identity, and centroid coordinates. Owner is evaluated as `missing` until a supported canonical record actually supplies it. Missing evidence never asserts that the underlying fact is absent.

## Assurance outcomes

Assurance is evaluated per field. There is no opaque parcel-wide truth or confidence score.

| Status | Meaning |
|---|---|
| `authoritative_corroborated` | A claim explicitly authoritative for this field agrees with a different source lineage. |
| `authoritative_source` | At least one direct claim is explicitly authoritative for this field, without independent corroboration. |
| `independently_corroborated` | Two or more independent source lineages agree. |
| `dependent_sources_agree` | Multiple claims agree but share one upstream lineage. |
| `single_source` | One current source lineage supplies the field. |
| `conflict` | Current supplied records disagree; no value is selected and human review is required. |
| `missing` | No supplied current record contains the field; absence is not inferred. |

Conflicts retain every normalized value group, claim ID, source lineage, authority class, reason, and limitation. Agreement across mirrors or republishers is visible but is not promoted to independent corroboration.

## Persistence and operator access

Complete reports are stored in the additive `parcel_assurance_reports` table. Indexed columns cover report ID, APN, county, review status, review requirement, source and lineage counts, claim count, conflict count, missing count, and generation time. The complete claims and field outcomes remain in the preserved JSON payload.

The existing read-only `constructionsight-upstream` interface exposes `parcel_assurance` list/detail records. It supports exact review-status, normalized-APN, and county filters. No generic upstream mutation is added.

## Compatibility

This phase does not add required fields to `ParcelCoreRecord`, alter existing parcel or site-resolution tables, rewrite historical payloads, change parcel IDs, or modify site-matching behavior. Database initialization creates the new table alongside existing tables. Historical databases and payloads remain readable.

## Current limits

The assurance engine evaluates only the current records supplied to it. It does not yet:

- collect countywide parcel, roll, tax, recorder, zoning, planning, permit, or CEQA data;
- establish that a source is complete, current, legally dispositive, or countywide;
- keep superseded longitudinal claims or perform bitemporal selection;
- resolve a conflict automatically;
- transfer authority from one field to another;
- count repeated publication of one upstream dataset as independent evidence; or
- treat tensor, similarity, or other inferred output as canonical truth.

Countywide acquisition, field-authority registration, longitudinal supersession, and broader evidence-family integration remain separate governed phases. Their outputs can feed this layer once lawful access, source identity, evidence retention, and coverage are verified.
