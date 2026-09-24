# Command Center functional integration: scoped source navigation and history

This development increment is stacked on PR #125. It preserves the owner-approved charcoal/amber desktop dashboard and uses the existing, read-only local SQLite operator APIs. It does not start live acquisition, infer a physical construction site, qualify a lead, send a message, place a bid, calculate verified royalty entitlement, or activate AI.

## Available controls

- The Command Center search bar now includes **All sources / CEQA / Permits** and **All retained counties / San Bernardino / Riverside** selectors. A search submission or selector change applies the same validated `kind`, `county` and `q` to `/api/snapshot` and `/api/footprint`; any old page offset is reset. Subsequent pagination retains the scope. The server independently validates permitted filter values and applies them to actual stored records.
- Sources & Collection uses existing count endpoints, now with direct links from the CEQA/permit totals and individual target-county cells into the matching filtered dashboard. The Other/unknown column remains informational because no corresponding exact county filter is exposed by the existing operator service.
- Browser-local watchlist entries now have an **Open record** action. Opening a bookmark performs a fresh exact `/api/candidate-preview?kind=...&record_id=...` GET against the selected database and verifies record identity and read-only authority. A deleted/absent record produces an error instead of a synthetic or stale dossier. The selected record can be outside the current filter/page; that condition is disclosed.
- Sources & Collection now has an explicit **Load retained timeline** action. It reads the existing bounded `/api/timeline` endpoint for current source-family, county and query filters, shows dated *source-claimed* historical events and exposes source-scan/event-list truncation. This is not new current-source collection or an activity alert.

## Scope and verification

The added Command Center tests assert the shared list/map filter contract, exact bookmark re-resolution, source-count drilldown and bounded read-only timeline wiring. Previous backend integration tests already cover county filtering, historical timeline ordering and exact candidate-preview GET against isolated SQLite. The JavaScript source parses in V8 and HTML ID uniqueness has been checked in the development pass. Automated browser interaction/visual parity and a full exact-head CI matrix must still be independently verified; neither is claimed by this document.

No release certification or `main` merge is authorized by this incremental UI integration. Outstanding defects remain tracked independently.
