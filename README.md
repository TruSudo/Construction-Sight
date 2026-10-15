# ConstructionSight

Local construction-site security lead review for San Bernardino and Riverside Counties. Official SMARTS captures feed a ranked lead list, source evidence, contact review, watchlists, maps, estimates and royalty records. Unknown facts show **—**. Demo data is labeled.

## Run

Requires Python 3.11 or 3.12. From this checkout:

```sh
./run-command-center.sh
```

This opens the localhost Command Center and obtains a bounded official SMARTS capture. Use `./run-command-center.sh --offline` to open the retained capture, or `./run-command-center.sh --demo` for the isolated fixture. Default data folder: `~/.local/share/constructionsight/command-center`.

## Use

- Lead Console filters and reviews captured projects; bulk SMARTS contact import verifies retained response/row hashes. Company call-list export excludes Do-Not-Contact and combines eligible sites.
- Contact priority explains source provenance, consultant cues and email/phone sharing across distinct reported developer names. It is a heuristic; shared details may identify filing agents or related entities.
- Lead Console’s **Verify sites** queue supports J/K navigation and requires an evidence URL, review note and explicit decision. Reviews become stale when the captured site changes.
- Contacts, parcel use and source statements remain source-claimed until the relevant facts are independently verified. Ready for Outreach requires sourced contact and site evidence; it is never inferred from missing facts.
- User menu provides reversible folder relocation, integrity-checked backups, dry-run restore and reviewed local PMTiles installation.
- Project Intelligence shows outcome cohorts and reviewed scoring changes. Bid Studio retains exact-cent estimates and reusable scope/price revisions; Royalty Ledger separates calculated, invoiced and received amounts.
- Sources & Collection provides a reviewed daily systemd user timer and exact Zorin setup steps. Installation and a running local user manager are required; next run is **—** when unknown.

Nothing sends outreach automatically. No login/CAPTCHA/access-control bypass. A 403 stops that source attempt. Optional provider credentials are supplied by the operator. OSM maps display attribution and their regional coverage limits.

## Develop

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/python -m ruff check src tests
.venv/bin/python -m mypy src/constructionsight
.venv/bin/python -m pytest -q
```

Run affected tests while editing; run the full suite before merging. CI blocks on tests, Ruff, strict Mypy, JavaScript syntax and dependency vulnerability auditing. The browser workflow checks structure, bundled fonts and actual interactions, and reports the calibrated visual comparison. Historical certification tooling remains available for reference; it is not a production merge gate.

`STATUS.md` is the single current handoff. Superseded phase reports and early audit-tool closure narratives live in `docs/archive/`. Captured source data and retained evidence are not archived or rewritten by documentation cleanup.

The visual workflow uses the original `tests/visual/reference_native_1672x941.png` at device scale 1. `design_tokens.json` records its SHA-256, native measurements and asset crops. Calibration challenges distinguish resampling from 3px displacement, a wrong design color and missing elements. Per-region scores and a four-panel comparison report remaining fidelity differences; the original font identity is unknown and scores remain non-blocking.
