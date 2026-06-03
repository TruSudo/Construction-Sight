# GUI Interaction and View-State Model

## Status

Accepted design direction.

## Purpose

ConstructionSight's GUI should function as a construction intelligence command center. The interface should make live construction activity, project clusters, entity relationships, authority status, opportunities, source coverage, and evidence accessible without overwhelming the user.

This model defines the intended user experience, startup behavior, map modes, panels, overlays, view states, live update behavior, and UI constraints.

## Core Rule

The primary interface is a live construction relationship map, not a static permit table.

The GUI should show:

- who is building what;
- where projects are located;
- which directors, developers, owners, applicants, and GCs are connected;
- which sites are active, planned, unknown, or stale;
- what changed recently;
- what evidence supports each conclusion;
- what still needs enrichment.

## Startup Behavior

On startup, the GUI should:

1. load the last cached operational-zone graph immediately;
2. display regional construction pulse metrics;
3. show source freshness status;
4. show active project clusters by default;
5. show the relationship map as the main view;
6. start receiving live update events;
7. apply workspace default filters;
8. keep crime context off by default;
9. keep out-of-zone relationship-horizon references hidden by default;
10. avoid opening as a blank search-only tool.

## Primary Layout

Suggested command-center layout:

- top command/search bar;
- left filter/source/navigation panel;
- central relationship map and geographic graph canvas;
- right entity/project detail panel;
- bottom live event/update feed;
- optional drawer for evidence/provenance;
- optional drawer for exports/reports.

## Primary View Modes

The GUI should support multiple views without losing the same underlying graph state.

Suggested view modes:

- `all_projects_view`;
- `relationship_map_view`;
- `developer_director_view`;
- `general_contractor_view`;
- `site_project_view`;
- `project_timeline_view`;
- `opportunity_view`;
- `coverage_dashboard_view`;
- `workspace_watchlist_view`;
- `investigation_view`.

## Relationship Map View

The relationship map is the default primary experience.

It should show nodes such as:

- project clusters;
- sites;
- parcels;
- developers;
- owners;
- directors;
- project executives;
- applicants;
- general contractors;
- architects;
- engineers;
- agencies;
- jurisdictions.

It should show relationship edges such as:

- developer of;
- owner of;
- director of;
- general contractor for;
- applicant for;
- architect for;
- engineer for;
- permit for;
- located at;
- located on parcel;
- issued by.

Edges should visually distinguish confirmed, probable, possible, conflicting, stale, and unresolved relationships.

## Map and Graph Integration

The map should combine geography and relationship intelligence.

The user should be able to:

- see project/site locations geographically;
- expand a site into its relationship graph;
- select a GC and see all sites connected to that GC;
- select a developer or director and see all known sites;
- filter by jurisdiction, phase, confidence, opportunity category, or authority status;
- hide low-confidence or stale relationships;
- toggle out-of-zone footprint references where relevant.

## Developer / Director View

The developer/director view should show:

- all sites tied to the selected developer/director;
- active projects;
- planned projects;
- historical projects;
- known GCs used;
- known architects/engineers;
- known jurisdictions;
- out-of-zone references in a clearly separated footprint section;
- authority confidence;
- relationship evidence;
- last enrichment update;
- unresolved fields.

## General Contractor View

The GC view should show:

- all active sites worked by the selected GC;
- historical sites;
- developers/directors connected to the GC;
- permit scopes;
- project phase distribution;
- geographic footprint;
- opportunity signals;
- relationship confidence;
- source evidence;
- out-of-zone references separated from in-zone pulse data.

## Site / Project View

The site/project panel should show:

- project name;
- address;
- APN;
- jurisdiction;
- coverage status;
- monitoring status;
- project cluster status;
- lifecycle phase;
- major-project probability;
- standalone probability;
- known authority roles;
- missing authority roles;
- unresolved authority reason;
- related permits;
- related planning cases;
- related CEQA records;
- related documents;
- related entities;
- opportunity signals;
- evidence summary;
- confidence values;
- last update time.

## Unknown Authority UI

Unknown authority should be shown as a structured state, not as a blank.

The UI should show:

- what authority roles are known;
- what roles are missing;
- why they are missing;
- what enrichment has been attempted;
- what enrichment is queued;
- candidate authorities if any;
- conflicts requiring review.

## Project Timeline View

The timeline view should show project lifecycle evidence over time:

- source record discovered;
- planning application filed;
- CEQA record filed;
- agenda item heard;
- permit applied;
- permit issued;
- inspection scheduled;
- inspection passed;
- revision filed;
- authority discovered;
- phase changed;
- final inspection;
- certificate of occupancy;
- opportunity created or expired.

## Opportunity View

The opportunity view should show:

- opportunity category;
- project/site;
- related entities;
- phase basis;
- timing window;
- evidence;
- confidence;
- status;
- freshness;
- limitations;
- export/report action.

Security opportunities may include optional crime context only when toggled or requested.

## Coverage Dashboard View

The coverage dashboard should show:

- total jurisdictions in operational region;
- mapped jurisdictions;
- unmapped jurisdictions;
- permit coverage;
- planning coverage;
- GIS/parcel coverage;
- agenda/staff report coverage;
- source health;
- stale sources;
- blocked/manual-only sources;
- adapter gaps;
- coverage confidence.

The dashboard must distinguish no activity from no coverage.

## Crime Context Overlay

Crime context is optional, contextual, and off by default.

Default behavior:

- crime overlay off on startup;
- crime legend hidden on startup;
- crime incidents not shown in relationship graph by default;
- crime context excluded from local pulse unless explicitly enabled;
- crime context summarized as aggregate counts where used.

When enabled, the UI should show:

- radius;
- time window;
- source;
- categories;
- count summary;
- limitations;
- legend.

## Out-of-Zone Footprint UI

Out-of-zone relationship-horizon references should be hidden from the default map and local pulse.

They may appear in:

- entity profile footprint section;
- expansion candidate view;
- targeted search results;
- watchlist view if user enabled it.

They must be labeled clearly as out-of-zone or relationship-horizon references.

## Search Bar

Search should be global and enrichment-aware.

Search targets may include:

- GC;
- developer;
- director;
- owner;
- applicant;
- address;
- APN;
- permit number;
- planning case;
- CEQA/SCH number;
- project name;
- jurisdiction;
- opportunity type;
- trade scope.

Search should return cached results immediately and then stream deeper enrichment updates when applicable.

## Live Event Feed

The bottom or side event feed should show:

- new records;
- new project clusters;
- relationship updates;
- authority updates;
- phase changes;
- source health changes;
- enrichment failures;
- opportunity signals;
- watchlist hits.

Events should be filtered by severity and workspace preferences.

## Evidence Drawer

Every major panel should allow evidence drill-down.

Evidence drawer should show:

- source record;
- source URL;
- evidence field;
- evidence text;
- retrieved timestamp;
- confidence contribution;
- normalized value;
- inference path;
- contradictions;
- export option.

## View-State Persistence

The GUI should preserve user view state.

Persistent state may include:

- selected workspace;
- map bounds;
- active filters;
- selected entity/project;
- open panels;
- active view mode;
- overlay toggles;
- crime overlay state;
- out-of-zone footprint toggle;
- confidence filters;
- watchlist filters;
- muted streams.

Default persisted crime overlay state should remain off unless the user explicitly changes it.

## UI Update Severity

The UI should route updates by severity.

High-severity updates may highlight nodes, add feed items, and refresh panels.

Medium-severity updates may refresh counters, panels, and feed items.

Low-severity updates may update timestamps or logs quietly.

Debug/progress events should not clutter the normal analyst view.

## Visual Design Direction

The UI should be polished, clean, professional, and premium.

Design goals:

- uncluttered;
- high information density without chaos;
- clear hierarchy;
- strong evidence/provenance affordances;
- readable map and graph layers;
- confidence and uncertainty visible but not overwhelming;
- modern desktop-quality feel.

## Non-Negotiable Constraints

- Do not open as an empty search-only interface.
- Do not show crime context by default.
- Do not clutter the relationship graph with irrelevant overlays.
- Do not hide source freshness.
- Do not hide confidence or uncertainty.
- Do not treat unresolved authority as blank.
- Do not include out-of-zone references in local pulse by default.
- Do not let low-value events visually overwhelm the user.
- Do not show inferred relationships without evidence access.

## Product Meaning

The GUI interaction and view-state model turns ConstructionSight's intelligence engine into a usable command center. It gives the user a live relationship map, focused panels, evidence drill-down, workspace control, and optional overlays while preserving clarity, trust, and operational focus.
