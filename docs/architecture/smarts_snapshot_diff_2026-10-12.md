# Development: offline SMARTS facility CSV reconciliation

This read-only preview compares two independently retained, local,
operator-provided UTF-8 SMARTS facility CSV exports scoped to Riverside or San
Bernardino. It neither downloads data nor claims either export is complete or
currently authoritative. Both snapshots must be obtained under authorized
source-use terms and preserved with provenance outside the Git repository.

Run after checking out and installing the SMARTS integration branch:

    python -m constructionsight.smarts_snapshot_diff \
      --county Riverside \
      --previous /private/path/older.csv \
      --current /private/path/newer.csv

## Official source discovery (verified 2026-10-12)

The California State Water Resources Control Board publishes the
[SMARTS Stormwater Regulatory dataset](https://publish.data.ca.gov/dataset/stormwater-regulatory-including-enforcement-actions-information-and-water-quality-results).
Its [Construction Discharge - Facility Information CSV](https://publish.data.ca.gov/dataset/stormwater-regulatory-including-enforcement-actions-information-and-water-quality-results/resource/8a0ed456-ca69-4b29-9c5b-5de3958dc963)
is a statewide resource identified by the same CKAN resource ID as the API
adapter (`8a0ed456-ca69-4b29-9c5b-5de3958dc963`). The state's catalog
listed the facility CSV at about 88.4 MB with a last-update date of
2026-10-02, and gave the encompassing dataset an R/P1W (weekly) cadence
as of this review. This is catalog metadata, **not** a retained download,
a confirmed historical snapshot series, a guarantee of weekly success,
or proof the CSV contents meet the tool's identity constraints.

The dataset-level rights metadata says `No Restrictions on Public Use`.
The individual resources may omit a license statement; source attribution,
commercial reuse/retention rules and operational download terms should be
checked under the access-governance process before unattended collection.
The snapshot-diff tool does no downloading itself.

The tool emits JSON with original file SHA-256 digests, input row totals, county
row totals, new/changed/unchanged/missing-from-new counts, and up to 25
non-contact identifier/hash review candidates. No source row contents, contact
columns, construction activity assertions, parcel joins, or outbound actions
are exposed. Transient CKAN `_id` is excluded from semantic CSV row hashes.
Hashes derived from CSV cell strings **cannot** be compared to typed CKAN JSON
hashes held in the evidence journal without a separately reviewed type mapping.

Fail-closed checks include ambiguous WDID or APP_ID mappings, missing source
identities, source identity drift across exports, changed column schema,
malformed CSV rows, and input-size limits. An absent row **never** means an
actual deletion or completed construction: it remains `missing_from_new` pending
manual verification. Even a clean diff has `coverage_status: unverified` until
independent completeness, source time, official publication, and use rights
have been checked. There is no watermark, poller, database write, scheduling,
asset enrichment, or readiness promotion.

Offline test: `pytest -q tests/test_smarts_snapshot_diff.py`.
