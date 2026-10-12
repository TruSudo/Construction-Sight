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
