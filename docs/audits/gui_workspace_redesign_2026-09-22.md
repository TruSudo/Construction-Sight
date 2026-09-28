# Operator presentation checkpoint — 2026-09-22

The owner requested a higher-quality interface while preserving the working private,
read-only operational test drive. This batch is limited to the operator's bundled
HTML/CSS/JavaScript and a structural regression test.

## Implemented

- Top-level Project records, Map, and Lead workflow navigation.
- Independent collapsible main navigation and left-hand Map legend; Map expands
  across the available workspace when the legend is closed. Collapse preferences
  are stored locally where browser storage is available.
- Geographic SVG remains one persistent DOM element across tab switches. Zoom,
  pan, selection and current filters are not deliberately reset by changing from
  Project records to Map. A compact source-location inspector links to its
  record-evidence view, including off-page records.
- Source-record lists, selected evidence detail, and historical milestones remain
  in Project records; the map is no longer embedded there.
- A restrained dark visual system and responsive layout, with reduced-motion
  preference support; local assets only, no remote CDN or design dependencies.
- The legend describes only the markers currently supported in the renderer:
  source locations, exact stored-key co-occurrences, selected locations and
  unverified parcel centroids. It explicitly disclaims verified construction
  status and parcel boundaries.

## Important limitations

- No logo asset matching the owner's previously planned branding has been
  supplied within the checkout. The original reticle remains a **temporary**
  mark. Replace it only with the actual approved logo asset; do not invent a
  replacement or imply the approved brand has been incorporated.
- The map remains an offline coordinate map; street tiles, parcel polygons,
  county boundaries and live construction-activity claims have **not** been
  implemented in this UI pass.
- Static JavaScript parse, DOM-identifier reconciliation and repository
  structural test additions are **not** full in-browser visual acceptance.
  Fresh local pytest / browser checks must be run at this commit before
  describing it as independently runtime-qualified.
- No active defect is closed; PRs #117/#119 remain unmerged. This change does
  not alter the release-assurance contract or enable external data acquisition,
  outreach, bidding or any write through the operator HTTP interface.
