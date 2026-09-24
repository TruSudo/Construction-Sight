# Governed current CEQAnet project capture → reviewed import → Command Center

## Actual operator path

`constructionsight-ceqanet-reviewed-import capture-preview` connects the existing lawful-access, one-request CEQAnet CSV service to the independently replayable, exact-digest reviewed import bridge. It does not bypass authorization or perform database writes. The source endpoint must be the exact public **project-scope** SCH CSV export, the returned body must be complete and independently replayable, and the resulting normalized project rows must all be in San Bernardino or Riverside counties (at most 100 rows). The service rejects incompatible formats instead of fabricating or silently omitting source rows.

An operator obtains an exact 10-digit SCH number from the official public source, verifies current legal/technical access restrictions and source conditions, and runs an **explicitly authorized single request**, for example:

```sh
constructionsight-ceqanet-reviewed-import capture-preview \
  --sch-number 2026030377 \
  --output evidence/manual/ceqanet-2026030377-NEW-UTC-ID.json \
  --plan-output evidence/manual/ceqanet-2026030377-NEW-UTC-ID-reviewed-plan.json \
  --authorization-reason "Operator reviewed one official public project CSV" \
  --execute-live
```

The example SCH is the known **historical Cabazon project ID**; it is not asserted to have changed since July 2026. Replace the SCH and filename with a project actually reviewed for new capture; do not overwrite an existing artifact. Output paths must be new and distinct. If the source has a CAPTCHA, login, disallowing robots policy, disallowing terms or paywall, disclose it through the command's corresponding access flags; the existing lawful-access facade then denies or holds the request. Do not attempt a bypass. This operation is not an all-county feed, scheduled collector, discovery engine or production recurrence.

The command uses the preexisting, effect-consumed authorization layer to execute **one exact public GET**, preserving the complete source-execution JSON through the protected, no-overwrite runtime artifact writer **before** the offline bridge parses it. If verification or bridging fails, retained evidence stays available for investigation but there is **no proposed import plan**. The successful console response includes the execution timestamp, original source SHA-256, exact proposed write-plan digest, source-record identities and count, and the paths of the retained artifact and optional unapproved plan. It explicitly reports `persistence_mutated: false` and `source_claims_verified: false`.

In the approved Command Center's Sources & Collection section, the **Prepare local capture instructions** control validates an exact SCH number and builds a command for the operator to review and run manually. This GUI remains local and read-only: clicking the preparation control does not access the internet, run shell commands, import evidence or authorize outreach. The original SCH page is linked for manual inspection. Local evidence must be imported into the **same existing SQLite file** opened by the Command Center.

## Independent import review

Inspect the complete retained public response and its county/identity claims. Then independently review the source digest and **entire** proposed write plan:

```sh
constructionsight-ceqanet-reviewed-import preview \
  --evidence evidence/manual/ceqanet-<SCH>-<UTC-ID>.json \
  --plan-output evidence/manual/independently-reviewed-plan.json
```

If accepted, execute the already-existing separate, independently authorized import, using the **actual two digests printed by review**, not placeholders or automatically copied approvals:

```sh
constructionsight-ceqanet-reviewed-import apply \
  --evidence evidence/manual/ceqanet-<SCH>-<UTC-ID>.json \
  --database data/constructionsight.sqlite3 \
  --approved-source-sha256 <INDEPENDENTLY-REVIEWED-SOURCE-DIGEST> \
  --approved-plan-digest <INDEPENDENTLY-REVIEWED-PLAN-DIGEST> \
  --authorization-reason "Independently reviewed this exact CEQAnet capture" \
  --execute-write
```

The existing reviewed-import `apply` governs the atomic upsert and readback. On the running dashboard, the existing local SQLite revision probe checks approximately every 90 seconds while the Command Center is visible; a successfully imported source observation becomes available under the correct CEQA/county filters, evidence inspection and Entity Network. A newly captured public planning observation **does not certify a permit, current active construction, precise jobsite, usable contact, qualified security lead or bid request**.

## Verified implementation boundary

This increment's CLI regressions use a mocked authorized one-request facade and actual preserved historical July CEQAnet evidence to verify invocation arguments, offline plan reconstruction, explicit confirmation, new-path/no-overwrite safety and failed-verification retention. They also exercise actual facade CAPTCHA denial. The source-connected database→HTTP regression remains in the earlier development branch; no claim is made that the CLI unit fixture performs a new September live request. The interactive helper's validation is separately covered by Command Center tests and browser-simulation checks.

No external request or SQLite write is performed by the GitHub development pass itself. No automatic acceptance of the source/plan hashes, background polling, scraper, browser POST, payment authorization, bid submission or autonomous outreach is introduced. Existing certification findings and the prohibition on merging to `main` without explicit owner authorization remain unchanged.
