# Private ConstructionSight test drive

From the GUI integration checkout, run:

```bash
bash scripts/test-drive.sh
```

Requires Python 3.11 or 3.12, Python's venv support and a browser. If necessary,
select the interpreter explicitly:

```bash
CONSTRUCTIONSIGHT_PYTHON=python3.12 bash scripts/test-drive.sh
```

The helper installs the repository's hashed dependency lock into a separate
environment, installs the current checkout, verifies the retained CEQAnet CSV
replay, creates a new trial database, applies a four-operation reviewed write
plan through the existing authorized persistence command, checks both persisted
observations through the content-bound source review queue, and opens the operator
at `http://127.0.0.1:8765`. Stop it with Ctrl+C. Each invocation creates a new trial;
the printed database path remains available for reopening with
`constructionsight-operator --database <printed-path>` from the trial environment.
The default trial environment is under
`~/.local/share/ConstructionSight/test-drive/venv` (or `$XDG_DATA_HOME`).
`--no-browser` starts the same server without opening a browser automatically.

The trial contains two **real, retained public-source observations from July 12,
2026**, not fresh discoveries: the EIR and NOP for the Cabazon Infrastructure Plan
and Cabazon Community Plan, SCH 2026030377. They describe a community planning
area, not two construction jobs. The map point is the source's geographic
reference converted from degrees/minutes/seconds; it is not a verified parcel,
jobsite boundary or construction location. No parcel identifier is invented from
the source's “Multiple, Community-wide” field. Capture date, original source
links, raw CSV hash and limitations are retained with each record.

The approved **Command Center** shell opens at `/`. Its source KPI counts retained
records, not distinct projects or qualified opportunities. The green/yellow/red
workflow summaries report stored workflow states rather than independently verified
construction readiness. The site map is an offline coordinate overview with no
street basemap. **Project Intelligence** opens `/workspace#records`, **Site Map**
opens `/workspace#map`, and **Lead Console** opens a dedicated screen with both
commercial workflow inspection and the new read-only source-observation queue.
The persistent local Watchlist survives browser restarts and flags changes to
retained normalized source records. It does not poll remote sources or deliver
notifications. Outreach and Bid Studio contain governed non-sending preview tools,
not customer-facing commercial authority.

Try this sequence:

1. From the Command Center, check the retained-source count and verify that the green/yellow/red tiles are **not** populated with demo lead counts. Open **Project Intelligence** and search for **Cabazon**.
2. Select **Riverside**, inspect each record and its March/July source milestones.
3. Inspect the agency relationship and the two overlapping source map points.
4. Choose **Inspect review gaps**. The source remains review-required.
5. Check the parcel inspection's missing-exact-parcel explanation.
6. Open **Lead Console**. Confirm the source review queue contains both retained
   Cabazon CEQA observations and their seven evidence checks, with neither
   observation auto-qualified as a commercial lead. The separate commercial
   workflow list is empty because no lead was created.
7. Bookmark one Cabazon source record. Restart the browser/server against the
   printed database path and verify the persisted local watchlist remains present.
   Its membership is not an external monitoring subscription.
8. Refresh and restart using the printed database path to check exact source
   identities, the nonmutating queue and retained source evidence.

The browser interface reads local records. Fresh collection, candidate-docket
staging, commercial workflow changes, outreach and bidding are separate commands
and are not triggered by this trial. Source access and a populated current-data
run still require their own runtime verification. The current interface has an
offline coordinate map, not a street basemap or county/parcel layers.

This trial is development validation, not release certification. PRs #117,
#119 and the stacked UI-lock PR remain drafts; the active ledger and assurance
requirements are unchanged. The new Command Center shell and browser-local
bookmarks do not establish real-browser visual acceptance, durable monitoring,
readiness qualification or operational commercial actions.
If an older database has incompatible tables or columns, startup now rejects it
before serving. Preserve that database for an explicit upgrade; `init-db` does
not repair obsolete column layouts. The helper always uses a fresh database.
