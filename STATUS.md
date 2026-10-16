# ConstructionSight — current handoff

Updated 2026-10-16. This is a current-state summary, not an assurance or release certificate. Historical analysis and audit evidence remain in Git history and existing records.

## Running product

- **Canonical local launch:** `./run-command-center.sh`; `--offline` uses retained capture, `--demo` is an isolated fixture. No owner-laptop installation or deployment is verified here.
- **USGS mapping:** PR #231 is merged into `main` at `4c8f8eaf08653e2d571b0df821b862dcc9b158ac`. Three official USGS imagery/topographic basemaps, coordinate-based lead markers, fractional-zoom alignment, source attribution, and offline fallback are implemented. Imagery is geographical context, not proof of construction activity or acquisition date.
- **CI:** both Python 3.11/3.12 quality gates and the Command Center visual + observational USGS jobs passed on that exact post-merge commit. GitHub's `Main Save` ruleset protects `main` against deletion/force pushes and requires PRs; mandatory CI check names remain unconfigured in that ruleset.
- **Visual acceptance:** reference stays at native 1672×941; structure, functional browser journeys and bundled-font checks passed. Calibrated pixel parity is still unmet in all eight regions. The pixel ratchet is reported, not an acceptance gate.
- **Lead data:** last verified SMARTS batch contained 1,563 source observations. Unknown type count was 542 (34.68% overall; 38.44% among nonexcluded). The grouped contact export identified 809 companies / 1,097 eligible sites; independent site/contact verification and sales outcomes are **not** established by those counts. Figures are a historical capture snapshot, not a current live refresh.
- **Safety:** public/authorized access only; HTTP 403 stops that attempt; source claims remain unverified until independently corroborated; unknown fields show `—`; no automatic outreach.

## Repository and active work

- **Pass A:** 189 branches audited, 109 heads reachable from `main` (including `main` and three historical archive branches), and 80 with divergent commits. None deleted or force-updated. Recovery reference: `archive/pre-pass-a-2026-10-15`.
- **Outstanding historical PRs:** #143, #155, #158, #186, #193, #195; each has selective-reconciliation notes. Preserve unmatched assurance evidence and source-access semantics; do not mass merge stale code.
- **Pass B:** reduce repeat work and ambiguous handoffs in small reviewed development-branch slices. Current slice shares one keyword-config load per lead-ranking batch, with a regression test proving the next batch reloads it. No behavioral changes to classification or scoring are intended. CI must pass before merging.
- **Pass B-2 (stacked draft):** parity audit confirms two non-interchangeable operator surfaces: the native SMARTS/local-state Command Center and the earlier CEQA/permit/SQLite read-model interface (including its separate `/workspace` view). Both launches, assets and data contracts remain supported. The older operator GET handler now reuses its existing fail-closed local-origin verifier rather than duplicating authorization logic; additional HTTP and entrypoint regression checks guard the unchanged behavior. No cross-database migration, interface removal, external request, or outbound change. CI pending.

## Operator next action

Run `./run-command-center.sh`, inspect the retained/source-backed lead list, verify the highest-value sites and actual reachable contacts, then request bids only from qualified opportunities. The codebase is not evidence that contact verification, deployment, or commercial conversion has already occurred.
