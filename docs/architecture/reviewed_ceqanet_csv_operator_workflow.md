# Verified retained CEQAnet CSV → operator Command Center

## Scope

This development workflow reuses existing, separately governed operations. The
network-access and exact-write-plan authorities remain independent; no GUI HTTP
POST, credentials, bulk scraping, automatic lead promotion, outreach or bid
authorization has been introduced. Source verification here means that the
**retained capture and replay are digest-consistent**; the truth of every
source-claimed planning fact or present construction activity is *not* certified.

The repository contains one previously captured **July 2026** official-source
CEQAnet project CSV for SCH `2026030377`, describing the Cabazon Infrastructure
Plan / Community Plan in Riverside County. This is a **historical public
planning/environmental-review record**, not proof of a construction start,
issued construction permit, precise construction-site APN or security contract.

The original retained evidence is:

`evidence/source_verification/ceqanet_csv_live_execution_2026-07-12.json`

This committed evidence includes the complete original response bytes and body
SHA-256 `5b1bc503c81d12ed0f00e52539edb437b42ae4c3a539a25e1c82a02b84273163`.
The newer offline parser replays the historical Windows-1252 response. Do not
relabel the July capture as a September live acquisition.

## New one-shot project capture (optional, separate from historical replay)

For a newly selected **exact SCH project that has not already consumed the durable
one-request allowance**, the reviewed-import CLI now provides the governed
`capture-preview` command. It calls the *existing* authorized one-request CEQAnet
project CSV service, preserves the full execution artifact in a new path, and
independently replays that saved evidence to present the proposed import plan
without writing SQLite. The source response must contain at most 100 complete
rows in the two target counties; incompatible or ambiguous source claims block
preview. The Command Center's Sources & Collection view can prepare an exact
SCH command for manual execution; it never calls remote APIs itself.

Read `docs/architecture/governed_ceqanet_capture_to_command_center.md` for the
exact operation, source-access flags, timestamp freshness/replay limitation,
separate digest approval and non-overwrite evidence handling. **The existing
historical July Cabazon fixture is not a newly executed September capture.**
The durable effect layer may replay a previously authorized SCH request;
`capture-preview` refuses to relabel older replayed bytes as a new capture.

## Operator workflow

1. Start from an **existing, operator-compatible SQLite database**. This CLI
   will not silently initialize or migrate a destination.
2. Independently replay and inspect the exact retained source and proposed
   normalized upserts. The preview contains two distinct document observations
   (EIR and NOP), the retained raw rows and parent-body digest, two source-claimed
   agency observations, **no fabricated parcel geometry**, and no lead:

   ```sh
   constructionsight-ceqanet-reviewed-import preview \
     --evidence evidence/source_verification/ceqanet_csv_live_execution_2026-07-12.json \
     --plan-output reviewed-cabazon-plan.json
   ```

3. Inspect the plan. If its source digest, complete source-row set, legal access
   and destination are acceptable, explicitly approve **both exact digests**
   printed by the preview. Execute the single governed atomic write:

   ```sh
   constructionsight-ceqanet-reviewed-import apply \
     --evidence evidence/source_verification/ceqanet_csv_live_execution_2026-07-12.json \
     --database data/constructionsight.sqlite3 \
     --approved-source-sha256 <copy-source-sha256-from-preview> \
     --approved-plan-digest <copy-plan-digest-from-preview> \
     --authorization-reason "Import reviewed historical CEQAnet evidence" \
     --execute-write
   ```

   This command recomputes both digests, uses the **existing authorized
   CEQAnet write-plan service**, and attempts a readback using the GUI's
   **actual SQLite read-only engine**. It does not issue network requests.
   The optional operator ID is an audit label, not authentication. Never
   automate copying approval digests or bypass the existing authorization.
4. Open the approved dashboard using the same database:

   ```sh
   constructionsight-operator --database data/constructionsight.sqlite3 --open-browser
   ```

   Search `Cabazon`. The Command Center / Project Dossier and exact
   `/api/candidate-preview` route expose both source observations and their
   evidence. The source date and document type appear as source-claimed historical
   milestones. The actual Cabazon community-wide location is **not** converted
   into a verified parcel, precise jobsite point, lead or outreach authorization.
   If the GUI is already open on the Command Center, it checks only the **local
   SQLite source revision** approximately every 90 seconds while visible and
   reloads on change without re-opening the application. This is **not remote
   source polling, notification delivery, or automated live acquisition**.

For a *new* SCH observation, first perform the existing governed single-request
lawful-access workflow (`constructionsight-ceqanet-csv execute-live --help`).
It produces a separate digest-bound retained execution artifact. The reviewed
import commands can consume that new artifact only if it is a complete,
independently replayable **project-scope** export with no more than 100 rows,
all required title/county fields and source rows within the two target counties.
Unsupported or ambiguous evidence is rejected, never guessed or quietly skipped.

## Acceptance boundaries

The real-source integration regression imports the committed **historical
July Riverside CSV** into an isolated temporary SQLite database, exercises
the actual backend snapshot, geographic-footprint, candidate-preview and
lead-workflow services, then issues genuine loopback HTTP GETs against the
canonical Command Center on that database. It verifies all source records
remain unassessed, that no unsupported geographic point is created, and that
read-only requests do not mutate SQLite. The CLI has a separate exact-hash /
explicit-write confirmation regression.

A real-browser visual pass, continuously scheduled live acquisition, verified
construction-site geographic boundaries and automatic qualification of a
commercial lead are **not included** in this increment. These remain separate
work items, and final production/release assurance is not claimed.
