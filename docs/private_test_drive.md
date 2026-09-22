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
plan through the existing authorized persistence command, and opens the operator
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

Try this sequence:

1. Check that two source records appear, then search for **Cabazon**.
2. Select **Riverside**, inspect each record and its March/July source milestones.
3. Inspect the agency relationship and the two overlapping source map points.
4. Choose **Inspect review gaps**. The source remains review-required.
5. Check the parcel inspection's missing-exact-parcel explanation.
6. Open the workflow view; it is empty because no commercial leads were created.
7. Refresh and restart using the printed database path to check persistence.

The browser interface reads local records. Fresh collection, candidate-docket
staging, commercial workflow changes, outreach and bidding are separate commands
and are not triggered by this trial. Source access and a populated current-data
run still require their own runtime verification. The current interface has an
offline coordinate map, not a street basemap or county/parcel layers.

This trial is development validation, not release certification. PRs #117 and
#119 remain draft; the active ledger and assurance requirements are unchanged.
If an older database has incompatible tables or columns, startup now rejects it
before serving. Preserve that database for an explicit upgrade; `init-db` does
not repair obsolete column layouts. The helper always uses a fresh database.
