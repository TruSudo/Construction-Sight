# SMARTS construction public API — bounded proof plan (2026-10-12)

## Status: development proof only; user-run live observations recorded

Source: California State Water Resources Control Board, SMARTS stormwater
public construction dataset, https://publish.data.ca.gov/dataset/stormwater-regulatory-including-enforcement-actions-information-and-water-quality-results.

Public source identities:

- Construction facility resource: `8a0ed456-ca69-4b29-9c5b-5de3958dc963`
- Inspections resource: `33047e47-7d44-46aa-9e0f-1a0f1b0cad66`
- CKAN DataStore GET: `https://publish.data.ca.gov/api/3/action/datastore_search`
- CKAN DataStore SQL GET: `https://publish.data.ca.gov/api/3/action/datastore_search_sql`
- Alternate `/api/action/` route appears in publisher API examples; it has not been exercised here.

The catalog describes a public DataStore dataset, weekly updates, and
construction fields such as SITE_COUNTY, SITE_LATITUDE/LONGITUDE,
APP_ID, WDID, STATUS, CONSTRUCTION_COMMENCEMENT_DATE, and DEVELOPER_NAME.
Its parent dataset declares no restrictions on public use; the individual
resource lists "No License Provided." This is a matter to resolve before
any commercial redistribution or blanket automation claims.

## Probe implementation

`src/constructionsight/smarts_api.py` contains a fail-closed, one-page
observer, a maximum 500-record exploratory snapshot method, fixed-shape
county SQL status summaries and recent NOI candidate queries, and an
explicitly gated CLI. The probe does NOT schedule requests, retry,
store raw records, create project intelligence, contact people, or
promote a source to verified. The SQL queries accept only the two named
counties, return at most 31 status groups or 25 candidate rows, and select
no contact, address, owner, or developer columns. Output includes curated
fields, request URL, and SHA-256 of response bytes. The status endpoint
returns regulatory status counts, not a count of active construction sites.
Returned internal row `_id` is a **transport row identity**, not a
stable project, permit, or agency identity. Identifiers APP_ID and WDID
must be evaluated for meaning, duplication, null rates, and join safety.

Local command examples from an installed repository:

```bash
python -m constructionsight.smarts_api --resource facilities --limit 3 --execute-live
python -m constructionsight.smarts_api --resource facilities --county 'San Bernardino' --limit 3 --execute-live
python -m constructionsight.smarts_api --resource facilities --county Riverside --limit 3 --execute-live
python -m constructionsight.smarts_api --resource inspections --limit 3 --execute-live
python -m constructionsight.smarts_api --mode status-summary --county 'San Bernardino' --execute-live
python -m constructionsight.smarts_api --mode recent-candidates --county Riverside --limit 10 --execute-live
python -m pytest -q tests/test_smarts_api.py
```

A `SITE_COUNTY` exact-value filter is used for facility queries. If a
county query returns zero, that is NOT evidence that the county has
zero records; inspect the returned field values and confirm casing,
data quality, and filtering semantics. Inspection-resource county
filters are intentionally disabled until its published schema has
been verified with real response data.

## First live proof requirements

1. Retrieve exactly one bounded, read-only statewide facilities page.
   Record HTTP status, CKAN success, response hash, field names, counts,
   and non-contact sample evidence.
2. Repeat separately for San Bernardino and Riverside, compare counts
   and validate actual county values; no assumptions about casing.
3. Observe a bounded inspection page and independently validate APP_ID
   and WDID semantics, missing values, and whether records join.
4. Confirm that offset pagination is supported and stable in practice.
   Source counts may drift during a multi-page scan. Count agreement
   does not prove a consistent source snapshot.
5. Compare with an official complete CSV publication, assessing exact
   snapshot scope, document metadata, version/hash and publication dates.
6. Obtain permission/policy review for proposed recurring collection
   and commercial-use terms; conduct a separate P0 acceptance gate for
   durable, unattended ingestion, provenance, replay, and recovery.

## Obstacles observed on 2026-10-12

The public catalog and resource schema were accessible through browser
lookup. An attempted direct CKAN API read did not produce rows in the
available web browsing interface; the code-execution runtime could not
resolve `publish.data.ca.gov` (DNS/network restriction). The user then ran
the public CKAN API successfully in their own terminal. **These are
user-supplied terminal observations, not independent direct observations
by this agent or a production ingestion run.** The MockTransport regression
tests are synthetic and must not be represented as live proof.

The user's bounded `datastore_search` facility queries reported 10,428
San Bernardino and 13,856 Riverside records. Their separate
`datastore_search_sql` status query returned the following counts:

| Regulatory status | San Bernardino | Riverside |
| --- | ---: | ---: |
| Terminated | 9,165 | 12,252 |
| Active | 698 | 918 |
| Expired | 499 | 578 |
| Undetermined | 40 | 70 |
| No Action Required | 16 | 19 |
| NOI Required | 7 | 18 |
| NONA Submitted | 2 | 1 |
| NOI Filed | 1 | not reported |

The user's SQL query also returned recent NOI application records, and
some records contained future reported `CONSTRUCTION_COMMENCEMENT_DATE`
values. This field is a reported or planned date and cannot verify that
work began. The earlier sorted `datastore_search` sample returned old
terminated records with null `NOI_PROCESSED_DATE`; the SQL candidate query
therefore excludes null processed dates. We have not independently
replayed either live query, validated all row semantics, or reconciled a
complete official CSV snapshot. No ingestion was activated.

## Project linkage boundaries

SMARTS is a water-quality compliance dataset, NOT an exhaustive registry
of all building or construction work. A commencement-date field can
describe a planned or reported date; it does not itself verify physical
commencement. Regulator inspections are not building-stage inspections.
Project graph changes, construction phase advancement, and lead readiness
must remain independently evidence-gated. Source-specific APP_ID/WDID
identity and schema drift must be validated before persistence.

Related: #204 autonomous acquisition release gate; #207 evidence-based
construction lifecycle; PR #201 integration. Do not merge into main or
claim recurring production coverage without explicit approval and live
end-to-end evidence.
