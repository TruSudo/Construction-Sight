# User Workspace, Watchlists, Alerts, and Investigation Model

## Status

Accepted design direction.

## Purpose

ConstructionSight should not overwhelm users with every live construction update. Users need workspaces, watchlists, saved searches, alerts, pinned entities, investigation boards, and attention controls so they can focus on the projects, contractors, developers, directors, jurisdictions, opportunities, and sources that matter to them.

This model defines how users organize the live intelligence stream into actionable workspaces and investigations.

## Core Rule

The intelligence engine discovers and updates broadly, but the user workspace controls what receives attention.

ConstructionSight should support both:

- automatic regional construction pulse;
- user-directed focus through watchlists, saved searches, alerts, and investigations.

## Workspace

A `Workspace` represents a user's operational environment.

A workspace should support:

- workspace identifier;
- workspace name;
- operational regions;
- default map view;
- default filters;
- selected opportunity categories;
- selected jurisdictions;
- saved searches;
- watchlists;
- pinned entities;
- alert preferences;
- export preferences;
- display preferences;
- created timestamp;
- updated timestamp.

## Default Workspace Behavior

On startup, a workspace should:

1. load the configured operational-zone construction pulse;
2. load cached relationship graph data;
3. apply default filters;
4. keep crime context off by default;
5. show watchlist updates prominently;
6. stream live updates into the event feed;
7. avoid cluttering the map with low-priority events.

## Watchlist

A `Watchlist` represents a user-selected set of objects receiving enhanced attention.

Watchlist item types may include:

- developer;
- director;
- project executive;
- general contractor;
- owner;
- applicant;
- architect;
- engineer;
- project cluster;
- site;
- parcel;
- permit;
- jurisdiction;
- source;
- opportunity category;
- trade scope;
- search query;
- out-of-zone entity footprint;
- expansion candidate jurisdiction.

## Watchlist Behavior

Watchlisted items may receive:

- prioritized refresh;
- prioritized enrichment;
- prominent event feed placement;
- alert eligibility;
- dashboard summaries;
- stale-data warnings;
- export/report inclusion.

Watchlisting should not automatically promote out-of-zone references into active monitoring unless explicitly configured.

## Watchlist Status Values

Suggested values:

- `active`;
- `paused`;
- `stale`;
- `triggered`;
- `needs_review`;
- `archived`.

## Alert

An `Alert` represents a user-facing notification rule.

Alert triggers may include:

- new project discovered;
- project phase changed;
- new GC relationship discovered;
- new developer/director relationship discovered;
- authority resolved;
- authority conflict detected;
- project enters active construction phase;
- high-value permit detected;
- opportunity signal created;
- watched GC appears on new project;
- watched developer enters jurisdiction;
- watched jurisdiction has new major project;
- source health failure;
- source data stale;
- export verification failure;
- relationship confidence changed.

## Alert Severity

Suggested values:

- `critical`;
- `high`;
- `medium`;
- `low`;
- `info`.

Alert severity should be based on user preferences, event severity, watchlist relevance, confidence, and operational-zone status.

## Alert Delivery

Initial delivery may be in-app only.

Future delivery may include:

- in-app notification;
- dashboard badge;
- email digest;
- daily summary;
- weekly summary;
- webhook;
- mobile notification if a mobile client exists.

No external alert channel should be required for the first implementation.

## Saved Search

A `SavedSearch` preserves a user query and its filters.

Saved search targets may include:

- GC;
- developer;
- director;
- project;
- address;
- APN;
- jurisdiction;
- opportunity type;
- trade scope;
- phase;
- unknown authority;
- source health;
- crime context summary where enabled.

Saved searches may be watchlisted and refreshed on a schedule.

## Investigation

An `Investigation` is a user-organized case or board for deeper analysis.

An investigation may contain:

- project clusters;
- entities;
- relationships;
- source records;
- evidence records;
- opportunities;
- notes;
- exports;
- alerts;
- unresolved questions;
- relationship graph snapshots;
- timeline snapshots.

## Investigation Status Values

Suggested values:

- `open`;
- `active`;
- `waiting_for_enrichment`;
- `needs_review`;
- `resolved`;
- `archived`.

## Pinned Items

Users should be able to pin important entities or projects.

Pinned items should appear in workspace panels and may include:

- pinned GC;
- pinned developer;
- pinned director;
- pinned project;
- pinned jurisdiction;
- pinned opportunity;
- pinned source;
- pinned search.

## Attention Routing

Not every event deserves the user's attention.

Attention routing should consider:

- event severity;
- watchlist membership;
- workspace filters;
- confidence score;
- operational-zone status;
- opportunity category;
- source health;
- user mute rules;
- event freshness.

## Mute and Suppression Rules

Users should be able to mute low-value streams.

Examples:

- mute low-confidence opportunity signals;
- mute out-of-zone references;
- mute minor permit updates;
- mute specific source health warnings temporarily;
- hide crime context unless enabled;
- hide stale opportunities.

Muted events should remain auditable but should not dominate the UI.

## Workspace Filter Defaults

Default filters should favor:

- in-zone data;
- active project clusters;
- recent updates;
- high/medium confidence relationships;
- watchlist hits;
- unresolved authority needing attention;
- active opportunities;
- source health issues.

Default filters should exclude or hide:

- out-of-zone references unless selected;
- crime context unless toggled on;
- low-value duplicate confirmations;
- stale opportunities;
- rejected candidates.

## User Notes

Users should be able to attach notes to:

- project clusters;
- entities;
- relationships;
- opportunities;
- investigations;
- sources;
- exports.

Notes should preserve:

- author;
- timestamp;
- target reference;
- note content;
- optional tags;
- update history if edited.

## Human Review Queue

Some automated results should require human review.

Review candidates may include:

- conflicting authority candidates;
- uncertain identity merges;
- high-value project clusters with weak evidence;
- out-of-zone promotion candidates;
- source coverage failures;
- opportunity signals with low confidence but high value;
- crime context summaries intended for advertising language.

Review status values:

- `pending`;
- `accepted`;
- `rejected`;
- `needs_more_evidence`;
- `deferred`.

## Workspace Export

A user should be able to export workspace or investigation material.

Exports may include:

- selected project summaries;
- relationship graph snapshot;
- opportunity list;
- watchlist updates;
- evidence package;
- investigation report;
- source health report.

Exports should preserve metadata, evidence, confidence, limitations, and integrity checks.

## Privacy and Access Control

Future multi-user workspaces should support permissions.

Potential permission levels:

- owner;
- editor;
- analyst;
- viewer;
- export-only;
- read-only.

Initial local/single-user implementation may not require full permissions, but the model should not block future access control.

## Runtime Integration

Workspace and watchlist state should influence runtime behavior.

Examples:

- watchlisted entities receive higher enrichment priority;
- watchlisted jurisdictions may refresh more often;
- saved searches may run periodically;
- alerts subscribe to graph update events;
- investigation items may trigger source freshness checks;
- muted streams are suppressed in UI but retained in event log.

## Non-Negotiable Constraints

- Do not overwhelm users with every low-value event.
- Do not hide auditable history when events are muted.
- Do not promote out-of-zone references automatically because they are watchlisted unless explicitly configured.
- Do not treat user notes as source facts.
- Do not treat accepted review as public-record proof unless evidence supports it.
- Do not let alerts fire without explaining the event basis.
- Do not expose crime context by default.

## Product Meaning

The user workspace, watchlist, alert, and investigation model turns ConstructionSight from a live data engine into a usable intelligence workspace. It gives users control over what they follow, what they ignore, what they investigate, and what they export while preserving evidence and runtime auditability.
