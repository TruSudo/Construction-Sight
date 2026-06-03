# Real-Time Event Bus and Runtime Update Streaming Model

## Status

Accepted design direction.

## Purpose

ConstructionSight should operate as a near-real-time construction intelligence platform. Public data sources may not provide live push events, but the application should still feel alive through cached graph loading, background refresh jobs, delta detection, enrichment orchestration, event emission, and UI update streaming.

This model defines the runtime architecture that moves updates from public source refreshes to the database, relationship graph, regional pulse, opportunity layer, and frontend map/panels.

## Core Rule

ConstructionSight should provide live runtime behavior through background processing and event streaming, not by blocking the user interface while directly querying every public source.

The correct runtime pattern is:

1. load cached operational-zone graph immediately;
2. show data freshness;
3. start background source refresh jobs;
4. detect new or changed records;
5. normalize and enrich records;
6. update entities, relationships, project clusters, phases, authority, and opportunities;
7. emit graph and pulse update events;
8. stream updates to the frontend.

## Real-Time Definition

ConstructionSight's real-time behavior means near-real-time updates from its own enrichment pipeline.

The system should not claim a direct real-time government feed unless a source actually provides one.

Allowed product meaning:

- live UI updates from ConstructionSight processing;
- live graph updates when new records are detected;
- live enrichment status;
- live source refresh logs;
- live opportunity and authority updates.

Not guaranteed by default:

- millisecond source updates;
- direct push from every jurisdiction;
- immediate government portal publication;
- live updates from sources that publish only daily or irregularly.

## Runtime Components

The mature runtime should include:

- source scheduler;
- adapter runner;
- delta detector;
- normalization pipeline;
- entity resolver;
- project clusterer;
- authority enrichment engine;
- relationship engine;
- phase inference engine;
- opportunity engine;
- source verification engine;
- event bus;
- persistent event log;
- API layer;
- WebSocket or Server-Sent Events streaming layer;
- frontend map and panel subscribers.

## Startup Lifecycle

On application startup:

1. initialize backend services;
2. connect to database;
3. load source registry;
4. load cached in-zone graph snapshot;
5. return initial graph/pulse state to frontend;
6. display freshness timestamps;
7. queue active in-zone source refresh jobs;
8. emit startup events;
9. stream subsequent refresh/enrichment events to frontend.

The application should not open as an empty search-only tool.

## Cached Graph First Rule

The UI should load from cached graph data before background refresh completes.

Startup should show:

- last graph update time;
- source freshness;
- known active projects;
- known relationship graph;
- known opportunity pulse;
- known unresolved authority queue;
- source health warnings.

Then it should update as background jobs complete.

## Source Refresh Lifecycle

A source refresh should emit lifecycle events:

1. `source_refresh_queued`;
2. `source_refresh_started`;
3. `source_fetch_completed`;
4. `source_delta_detected` or `source_no_change_detected`;
5. `source_refresh_completed` or `source_refresh_failed`.

A source refresh should record:

- source identifier;
- source name;
- jurisdiction;
- operational region;
- refresh run identifier;
- start time;
- end time;
- status;
- records fetched;
- records changed;
- records unchanged;
- error reason if any;
- next scheduled refresh.

## Delta Detection Lifecycle

Delta detection should decide whether a fetched record is new, changed, unchanged, stale, or removed/unavailable.

Delta inputs may include:

- source record identifier;
- source URL;
- content hash;
- status field;
- permit status;
- inspection status;
- document hash;
- updated timestamp;
- field-level differences.

Delta events may include:

- `source_record_discovered`;
- `source_record_changed`;
- `source_record_unchanged`;
- `source_record_removed_or_unavailable`;
- `source_record_stale`.

## Enrichment Job Lifecycle

An enrichment job should emit:

1. `enrichment_queued`;
2. `enrichment_started`;
3. `normalization_completed`;
4. `entity_resolution_completed`;
5. `project_clustering_completed`;
6. `relationship_inference_completed`;
7. `authority_enrichment_completed`;
8. `opportunity_detection_completed`;
9. `enrichment_completed` or `enrichment_failed`.

Each enrichment job should preserve:

- target identifier;
- target type;
- trigger reason;
- source records used;
- output assertions;
- new entities;
- updated entities;
- new relationships;
- updated project clusters;
- confidence changes;
- failure reason if any.

## Event Bus

The event bus is the internal mechanism for moving updates across the system.

The first implementation may be in-process or database-backed. Later implementations may use Redis, PostgreSQL LISTEN/NOTIFY, Celery/RQ events, Kafka, or another queue/event system if needed.

The event bus should support:

- publish;
- subscribe;
- persistence or event-log writing;
- event ordering where required;
- event type;
- event severity;
- event source;
- event timestamp;
- event payload;
- correlation identifier;
- causation identifier;
- enrichment run identifier.

## Persistent Event Log

Events that affect intelligence state should be persisted.

Persisted events support:

- auditability;
- replay;
- debugging;
- UI history;
- export support;
- confidence-change history;
- failure diagnostics.

Not every low-level progress event needs permanent retention, but state-changing events should be retained.

## Event Envelope

Every runtime event should use a consistent envelope.

Suggested fields:

- `event_id`;
- `event_type`;
- `severity`;
- `created_at`;
- `source_service`;
- `correlation_id`;
- `causation_id`;
- `operational_region_id`;
- `jurisdiction`;
- `entity_refs`;
- `project_cluster_refs`;
- `source_record_refs`;
- `payload`;
- `message`;
- `confidence_delta`;
- `requires_user_attention`.

## Event Severity

Suggested severity values:

- `critical`: data integrity issue, source legal/access problem, corrupted export, impossible state;
- `high`: new project, new GC/developer/director relationship, authority resolved, major phase change;
- `medium`: new trade permit, inspection activity, candidate authority found, opportunity created;
- `low`: duplicate confirmation, routine source verification, no-change refresh;
- `debug`: internal progress detail.

## Graph Update Events

Graph update events should represent meaningful relationship or project changes.

Examples:

- `entity_created`;
- `entity_updated`;
- `entity_merged`;
- `relationship_created`;
- `relationship_updated`;
- `relationship_confidence_changed`;
- `project_cluster_created`;
- `project_cluster_updated`;
- `project_phase_changed`;
- `authority_status_changed`;
- `permit_added_to_project`;
- `planning_case_added_to_project`;
- `ceqa_record_added_to_project`;
- `opportunity_signal_created`;
- `opportunity_signal_updated`;
- `crime_context_updated`.

## Frontend Streaming

The frontend should receive updates through WebSocket or Server-Sent Events.

The frontend should subscribe to:

- operational region updates;
- current map viewport updates;
- selected entity updates;
- selected project updates;
- search job updates;
- source health updates;
- opportunity updates;
- user watchlist updates.

The frontend should not poll aggressively if a streaming channel is available.

## UI Update Behavior

The UI should distinguish visual update priority.

High-severity updates may:

- highlight a map node;
- add a live feed item;
- update a project/GC/developer panel;
- show an attention marker.

Medium updates may:

- update the side panel;
- add a feed item;
- refresh counters.

Low updates may:

- update source freshness;
- refresh internal state quietly;
- appear only in detailed logs.

## Search Runtime Behavior

Search should trigger targeted enrichment jobs.

A search should:

1. create a search job;
2. load cached matches immediately;
3. queue deeper enrichment for target entities or sources;
4. emit search progress events;
5. stream discovered relationships into the map;
6. distinguish in-zone records from relationship-horizon references;
7. explain unresolved results or source failures.

## Watchlist Runtime Behavior

Watchlisted entities, projects, sources, and jurisdictions should receive prioritized refresh or enrichment.

Watchlist changes should emit events:

- `watchlist_item_added`;
- `watchlist_item_removed`;
- `watchlist_item_updated`;
- `watchlist_item_triggered`.

## Source Health Runtime Behavior

Source health changes should emit events:

- `source_health_healthy`;
- `source_health_degraded`;
- `source_health_stale`;
- `source_health_failed`;
- `source_health_blocked`;
- `source_health_needs_review`.

Source health should be visible in the UI because stale or failing sources affect trust in the live pulse.

## Failure Events

Failures should be explicit and actionable.

Failure event payloads should include:

- failure type;
- source or job identifier;
- human-readable reason;
- technical reason;
- retryable flag;
- next retry time;
- impact scope;
- suggested action;
- related source records if any.

## Staleness Rules

Real-time display must disclose staleness.

The system should track:

- data freshness by source;
- graph snapshot freshness;
- selected entity freshness;
- selected project freshness;
- opportunity freshness;
- crime context freshness.

The frontend should not present stale information as current.

## Runtime Scaling Path

Initial runtime may be simple:

- SQLite or PostgreSQL;
- in-process scheduler;
- in-process event dispatcher;
- FastAPI endpoint;
- Server-Sent Events.

Mature runtime may include:

- PostgreSQL/PostGIS;
- Redis or message queue;
- worker processes;
- FastAPI;
- WebSockets/SSE;
- graph projection cache;
- background scheduler;
- frontend state store.

The architecture should not require the mature stack before the model is useful.

## Non-Negotiable Constraints

- Do not block UI startup on full source refresh.
- Do not claim source-level live data where the source is not live.
- Do not hide source staleness.
- Do not emit graph updates without evidence references.
- Do not let low-value events overwhelm the map.
- Do not treat background refresh failure as silent.
- Do not allow search jobs to contaminate regional pulse metrics unless explicitly promoted.
- Do not stream crime context by default unless the user enables it or requests it.

## Product Meaning

The real-time event bus and runtime update streaming model is the nervous system of ConstructionSight. It allows the platform to behave like a live construction intelligence command center while preserving lawful acquisition limits, evidence, confidence, staleness, and user control.
