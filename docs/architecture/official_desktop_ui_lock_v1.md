# ConstructionSight Official Desktop UI Lock v1

**Owner-approved design contract — 2026-09-23.** The approved desktop mockup is the canonical visual reference, not a suggestion for a redesign. No significant layout, brand or visual-style departure without owner authorization.

## Exact reference

- Visual reference: owner-approved `constructionsight_command_center_dashboard.png`, 1672 × 941; SHA-256 `00a043ec464728b2275ba3372421b89e1e31d7a7a76dcdb20ced9628bea03f3f`.
- Logo source: owner-supplied `289.png`, SHA-256 `3a1093ed33a3165b22dd27196e2f9d1945a6338571ae2a2d24db39b13e7d4af6`.
- Sidebar derivative: `src/constructionsight/operator_brand.webp` is a cropped/resized emblem from the owner's image; original source image is **not** stored in this repository.
- The full owner-approved implementation blueprint is the separately supplied `ConstructionSight_Official_Desktop_UI_Lock_Spec_v1.md` (SHA-256 `77a7263dad87770704214447665cda748f0e83afdbab770cab455cd72cef0bd8`); obtain that file and source artwork from the owner before declaring pixel-accurate acceptance. Neither the screenshot nor its illustrative numbers/companies are operational source evidence.

## Desktop layout contract

At the reference viewport, sidebar x=0–316; utility bar y=0–58; hero y=59–169; five KPI cards y=180–264; central-left map x≈333–1142 y≈275–669; right dossier x≈1158–1633 y≈275–730; lower-left record/opportunity list x≈333–1142 y≈682–908; lower-right watchlist x≈1158–1633 y≈742–908. Preserve the 1.7:1 map-to-dossier width relationship, fixed navigation shell, compact charcoal panels, amber active state and owner's construction crosshair branding. Layout may scroll or responsively reflow at smaller widths without changing the desktop composition.

Sidebar order: Command Center, Project Intelligence, Site Map, Entity Network, Evidence Chains; Commercial: Lead Console, Outreach, Bid Studio, Royalty Ledger; Intelligence: Watchlist, Sources & Collection. Every destination must be reachable and report its real operational state; a clickable card is not proof of implemented capability.

## Non-negotiable functional truth

- Red/yellow/green apply to **qualified opportunities** with evidence-backed deterministic mandatory gates; new raw source observations are gray **Unassessed**. Never infer readiness from permit issuance, a score or map coordinates alone.
- Green for outreach requires appropriate timing, site/project identity, relevant current activity, actionable verified decision-maker contact and review/authorization gates. Green for outreach **does not authorize bidding**; an actual request, scope and bid-specific authorization are required.
- A watchlist bookmark is not a source watcher, a browser notification or a scheduled reminder. Runtime watch rules need persisted exact site identity, source change detection, material event deduplication and notification delivery.
- Source-record counts are not deduplicated construction projects or qualified leads; approximate geographic points are not verified parcels. Never replace unavailable data with mockup numbers, fabricated contacts or pictures.
- Maintain existing evidence/provenance, read-only and lawful-source boundaries. Live source collection, outreach, bid submission and financial posting must remain unavailable in the GUI until backend authority, tests and runtime verification exist.

## Current branch delivery (incremental, not full acceptance)

`/` serves the new read-only Command Center using the existing `/api/snapshot`, `/api/footprint`, `/api/workflows` and `/api/health` endpoints. `/workspace#records`, `#map` and `#workflow` preserve the established evidence, entity-key, parcel candidate, geographic and persisted-workflow operator views. A browser-local Watchlist stores explicitly selected source bookmarks **without live monitoring or reminders**. Unimplemented commercial and visualization destinations explain their limitations and route to available related evidence. The miniature dashboard map is a coordinate overview, **not** the screenshot's satellite/street basemap. Exact screenshot fidelity, full logo/wordmark asset replacement, backend readiness, persistent watchlist alerts and actual commercial action paths remain future, separately verifiable implementation work.

Do not merge this UI branch to `main` without explicit owner authorization.
