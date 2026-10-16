# ConstructionSight

Local construction-site security lead review for San Bernardino and Riverside Counties. Official SMARTS captures feed a ranked lead list, source evidence, contact review, watchlists, maps, estimates and royalty records. Unknown facts show **—**. Demo data is labeled.

## Run

Requires Python 3.11 or 3.12. From this checkout:

```sh
./run-command-center.sh
```

This opens the localhost Command Center and obtains a bounded official SMARTS capture. Use `./run-command-center.sh --offline` to open the retained capture, or `./run-command-center.sh --demo` for the isolated fixture. Default data folder: `~/.local/share/constructionsight/command-center`.

**Entry points:** `./run-command-center.sh` / `constructionsight-command-center` is the current native-layout lead product. The installed `constructionsight-operator` and `constructionsight-desktop` commands use the separate earlier operator interface; they remain available for compatibility and specialized workflows, not as substitutes for the native-layout visual acceptance target. Do not delete their implementation until those workflows are explicitly migrated and tested.

## Use

- Lead Console filters and reviews captured projects; bulk SMARTS contact import verifies retained response/row hashes. Company call-list export excludes Do-Not-Contact and combines eligible sites.
- Contact priority explains source provenance, consultant cues and email/phone sharing across distinct reported developer names. It is a heuristic; shared details may identify filing agents or related entities.
- Lead Console’s **Verify sites** queue supports J/K navigation and requires an evidence URL, review note and explicit decision. Reviews become stale when the captured site changes.
- Contacts, parcel use and source statements remain source-claimed until the relevant facts are independently verified. Ready for Outreach requires sourced contact and site evidence; it is never inferred from missing facts.
- User menu provides reversible folder relocation, integrity-checked backups, dry-run restore and reviewed local PMTiles installation.
- Project Intelligence shows outcome cohorts and reviewed scoring changes. Bid Studio retains exact-cent estimates and reusable scope/price revisions; Royalty Ledger separates calculated, invoiced and received amounts.
- Sources & Collection provides a reviewed daily systemd user timer and exact Zorin setup steps. Installation and a running local user manager are required; next run is **—** when unknown.

Nothing sends outreach automatically. No login/CAPTCHA/access-control bypass. A 403 stops that source attempt. Optional provider credentials are supplied by the operator. OSM maps display attribution and their regional coverage limits.

## Active development policy (2026-10-15)

**Build usable construction-security intelligence quickly, with controls proportional to actual risk.** This is the current operational policy. Earlier five-pass assurance, universal zero-defect, exact-tree recertification, one-narrow-phase-at-a-time and governance-document proliferation requirements are **historical**, not routine development or merge gates. Historical tools may still be run when their protected risks justify them. This policy changes development procedure, **not** lawful-access boundaries, source evidence, authorization limits or the product's honest reporting standards.

### Delivery loop

1. **Pick a measurable user outcome.** Prefer real leads classified, corroborated, made callable, or matched to upcoming work. State a baseline and one acceptance result; avoid refactoring or new architecture without a concrete gap.
2. **Inspect what exists; reuse it.** Build a complete but reviewable vertical slice in a development branch: permitted source acquisition, parse/evidence, identity and event, storage, operator UI/action, and honest error states as relevant. Commit stable intermediate changes; incomplete features stay disabled or explicitly labeled partial. No duplicate pipeline, demo claimed as live, or deferred integration masquerading as complete.
3. **During development run only affected checks.** Use focused tests, format/type checks and a real bounded sample when source logic changes. Don't rerun the entire repository assurance suite after every edit.
4. **Before merge run mandatory CI.** Python full tests on supported versions, Ruff, strict Mypy, JavaScript syntax when relevant, dependency integrity and vulnerability audit; the affected browser/functional journeys and source evidence checks must pass. Do not silently skip a failing gate. Existing CI remains authoritative. Calibrated pixel fidelity is a reported non-blocking ratchet; preserve approved dashboard geometry and improve visual differences separately.
5. **Review and deliver.** A concise PR report states **live / partial or blocked / tests / measured outcome / next**. Update `STATUS.md` once per PR with current facts; do not create additional phase, assurance or handoff documents. Merge only after the owner's applicable approval and green blocking gates. No automatic outreach.
6. **Measure outcomes, then iterate.** Track useful unique projects, independently verified site identities, appropriate reachable contacts, source freshness/coverage, false joins, time to a working slice, regressions and business outcomes. Do not substitute test counts, document totals or certification passes for demonstrated utility.

### Severity and stop rules

- **P0 critical:** unlawful/unauthorized access or outbound activity, significant confidentiality/integrity/security breach, irreversible data loss, or systematic false verification. **Stop the affected action and release immediately**; repair and prove recovery before release.
- **P1 major:** broken core lead/backup/collection/bid workflow, silent source failure, material wrong project links or severe regression. **Block the affected feature/release**, preserve truthful status; unrelated isolated work may proceed.
- **P2 moderate:** bounded classification or usability defect with safe workaround. Track impact and test plan; fix by priority, may ship other unaffected functionality.
- **P3 minor:** cosmetic or low-impact issue. Track or defer without blocking unrelated delivery.

A **specific acceptance criterion** may remain unmet without becoming a universal severity escalation. No concealed defect, knowingly fabricated fact or falsely claimed readiness. Original acquired evidence remains auditable; derived classifications are versioned, correctable and recomputable.

### Risk-based review and authorization

- Routine, reversible source, model, UI and test work is authorized on development branches; use code review and targeted tests, not repeated full-repository deep reviews.
- Require heightened adversarial/recovery review when touching credentials, permission boundaries, destructive migrations, backup/restore, financial/external effects, source-access enforcement, or provenance tamper protection. Security mutation checks apply to affected invariants, not every UI or classifier change.
- Never bypass HTTP 403, login, CAPTCHA, rate limits, licensing or source restrictions. Never guess missing facts; display **—**. Do not treat a permit or regulatory filing alone as confirmed construction, decision-maker or security demand.
- Keep external outreach, costs, destructive actions and production/main merges behind the existing approval rules. Scheduled collection is opt-in and reversible. A local working prototype can ship while specific enrichment coverage remains **partial**; no unsupported claim of complete county coverage or continuous deployment.

### Evidence of completion

A new source is **implemented** only when its real acquisition, retained evidence, conservative project linkage, persisted updates and operator workflow actually work. Report **live-verified** separately from test-fixture success, and **owner-device deployed** separately from both. A bounded prototype may be merged when safe and honestly labeled; a production/full-coverage claim still requires the stronger end-to-end proof for that claim.

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
