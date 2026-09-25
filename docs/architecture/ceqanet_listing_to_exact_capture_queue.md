# Saved CEQAnet listing → exact-SCH source capture review

## The supported development path

ConstructionSight already has a separately authorized, bounded public CEQAnet listing executor and a conservative offline search-result parser. This integration closes the operator-facing handoff between them and the new governed project-level capture:

1. Review source-access conditions and run an independently authorized, *bounded* listing using the existing CLI (two target counties, a bounded posted/received date range, a page limit and explicit `--execute-live`). Retain the complete output as JSON; no county-wide coverage or freshness is inferred merely because execution was requested.
2. Replay the saved listing **offline** to identify candidates with an unambiguous ten-digit SCH, an exact matching official CEQAnet project/document detail URL, and an explicitly source-claimed San Bernardino or Riverside county. The full listing must have a governed v2 envelope, complete authorized pages, official HTTPS /Search URL identity, no redirects, no errors and no truncated bodies. Unknown/outside counties and ambiguous identifiers are excluded and counted, never guessed; conflicting county observations for a single SCH block the whole queue.
3. Review the resulting candidate queue and official project page. Select an SCH for a **separate**, lawful-access-reviewed `capture-preview` operation; the listing queue never invokes network acquisition, writes SQLite or grants the separate project request any authorization. The project capture must be genuinely new in this invocation, not old exact-effect replay.
4. Independently inspect the complete project CSV and exact source/write-plan digests. Use the existing separate `apply` operation only after express operator review and write authorization. The approved Command Center then reads newly persisted observations through its local source-revision check.

Example offline handoff from an **already acquired** governed listing artifact:

```sh
constructionsight-ceqanet-reviewed-import discover-preview \
  --listing-evidence evidence/manual/existing-governed-ceqanet-listing.json \
  --output evidence/manual/new-exact-sch-review-queue.json
```

A queued entry has a source-claimed SCH number, county, title, detail URL, observed page numbers and total observations. The output binds to the *exact retained input bytes* with SHA-256, states the number of excluded observations, and carries explicit unverified/source-only status. It is not a validated permit, duplicate-suppressed project, active site, named contractor, source authorization, commercial lead or solicitation authority. No listed link or source label is allowed to change the target URL for the governed project CSV request.

The queue parser intentionally accepts only a **full, self-reported** governed listing execution and does not independently authenticate or cryptographically verify that an arbitrary JSON artifact was genuinely emitted by the listed source. Manual provenance review remains necessary. The listing parser may omit valid projects if source HTML changes or counties/SCHs are absent; queue counts cannot be interpreted as complete county coverage. The source-backed, separately authorized listing itself is provided by `constructionsight-ceqanet-listing-execute execute --help`, which is outside the scope of this offline command. Do not use local fixture data as present-day source observations.

## Explicit limitations

There is still **no continuous county-wide acquisition**, no automatic project request per queue entry, no backend polling of the public website, no multi-jurisdiction permit adapter activation, and no new right to requery a previously effect-consumed exact SCH. Source/plan digest approval remains manual and isolated from discovery. Queue production cannot trigger AI, lead qualification, contact collection, outreach or bidding. Existing assurance/release findings remain recorded; this is a development integration on a non-main branch.
