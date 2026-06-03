# Jurisdiction Intelligence and Coverage Mapping Model

## Status

Accepted design direction.

## Purpose

ConstructionSight must know which jurisdictions exist, which sources serve each jurisdiction, what data categories are available, what obstacles exist, what coverage has been achieved, and what remains unmapped. The platform should maintain a jurisdiction-level intelligence map so the regional construction pulse is never confused with full market truth where source coverage is incomplete.

This model defines how ConstructionSight should represent counties, cities, agencies, source coverage, platform families, access conditions, coverage gaps, and source-discovery progress.

## Core Rule

ConstructionSight must distinguish construction inactivity from source coverage absence.

No results from a jurisdiction means only that no results were found from the checked sources. It does not prove no construction activity exists unless source coverage is adequate for that claim.

## Jurisdiction Entity

A `Jurisdiction` represents a government or public authority area relevant to construction activity.

Jurisdiction types may include:

- county;
- city;
- town;
- unincorporated county area;
- special district;
- planning agency;
- building department;
- fire authority;
- public works agency;
- environmental agency;
- state agency;
- regional agency.

## Initial Geographic Scope

Initial active scope:

- San Bernardino County, California;
- Riverside County, California;
- cities and unincorporated areas within those counties as source coverage is added.

Out-of-zone jurisdictions may be stored as relationship-horizon references, adjacent candidates, watchlist targets, or future expansion candidates.

## Jurisdiction Fields

Each jurisdiction should support:

- jurisdiction identifier;
- name;
- type;
- county;
- state;
- country;
- parent jurisdiction;
- child jurisdictions;
- boundary geometry where available;
- official website;
- building department URL;
- planning department URL;
- public works URL;
- GIS/open-data URL;
- agenda URL;
- source coverage status;
- monitoring status;
- coverage confidence;
- last coverage audit timestamp;
- notes;
- known limitations.

## Coverage Categories

Coverage should be tracked by data category, not as a single yes/no field.

Suggested categories:

- permit records;
- permit detail records;
- inspection records;
- planning applications;
- entitlement records;
- CEQA/environmental records;
- agenda packets;
- staff reports;
- GIS parcels;
- assessor data;
- current development projects;
- capital improvement projects;
- public works projects;
- contractor/license data;
- business/entity references;
- crime context sources;
- documents/PDFs;
- open-data exports.

## Coverage Status Values

Each category may have a status:

- `covered`: active source exists and is usable;
- `partially_covered`: source exists but coverage is incomplete;
- `discovered_unverified`: source candidate found but not verified;
- `verified_unimplemented`: source verified but no adapter or ingestion route exists yet;
- `blocked`: public access obstacle prevents automated use;
- `login_required`: public data may require account access;
- `manual_only`: information exists but only through manual public review;
- `not_found`: no source identified yet;
- `not_applicable`: category does not apply;
- `needs_review`: status unclear.

## Monitoring Status Values

Jurisdiction monitoring status should include:

- `active`;
- `watchlist`;
- `reference_only`;
- `paused`;
- `unmapped`;
- `needs_review`;
- `unsupported`;
- `rejected`.

## Platform Family Mapping

Jurisdictions may expose different platform families for different data categories.

Examples:

- Accela for permits;
- Tyler EnerGov for permits;
- eTRAKiT for permits;
- OpenGov for permits/planning;
- SmartGov for permits/planning;
- Citizenserve;
- ArcGIS FeatureServer/MapServer for GIS;
- Socrata for open data;
- Granicus for agendas;
- Laserfiche for documents;
- CEQAnet for state environmental records;
- county assessor GIS for parcels.

A jurisdiction may have multiple source systems.

## Source Coverage Record

A `SourceCoverageRecord` should connect a jurisdiction to a source and coverage category.

It should support:

- jurisdiction identifier;
- source identifier;
- coverage category;
- platform family;
- access method;
- coverage status;
- monitoring status;
- adapter availability;
- source verification result;
- coverage confidence;
- last checked timestamp;
- last successful retrieval;
- last failure reason;
- limitations;
- notes.

## Access Obstacle Tracking

ConstructionSight should explicitly track obstacles.

Obstacle types may include:

- CAPTCHA/access friction;
- login required;
- unsupported JavaScript-heavy portal;
- no official API found;
- incomplete search interface;
- missing date filters;
- missing geographic filters;
- poor record detail visibility;
- rate limiting;
- broken portal;
- stale public data;
- PDF-only data;
- agenda-only visibility;
- manual-only records;
- unclear legal access status.

## Coverage Confidence

Coverage confidence should answer:

- how sure are we that we know where this jurisdiction publishes relevant data;
- how complete is the data category coverage;
- how recently was coverage verified;
- how reliable is the source;
- are there known blind spots.

Suggested values:

- `high`;
- `medium`;
- `low`;
- `unknown`.

Numeric confidence from 0 to 100 may also be used.

## Coverage Gap Model

A `CoverageGap` identifies missing or incomplete jurisdiction intelligence.

Coverage gaps may include:

- missing permit source;
- missing planning source;
- missing agenda packet source;
- missing GIS/parcel source;
- missing inspection source;
- source found but adapter missing;
- source verified but not monitored;
- source stale;
- source blocked;
- source requires manual review.

Coverage gaps should be visible in the UI and audit exports.

## Jurisdiction Discovery Workflow

Discovery workflow:

1. identify jurisdiction;
2. locate official website;
3. locate building/permit access paths;
4. locate planning/current development access paths;
5. locate GIS/open-data access paths;
6. locate agenda/staff report access paths;
7. locate CEQA/environmental paths;
8. locate assessor/parcel source;
9. verify source access;
10. classify platform family;
11. record coverage category status;
12. create adapter requirement where needed;
13. add to source registry or coverage backlog.

## Regional Coverage Dashboard

The UI should eventually show a coverage dashboard.

Dashboard metrics may include:

- total jurisdictions in operational region;
- jurisdictions fully mapped;
- jurisdictions partially mapped;
- jurisdictions unmapped;
- permit coverage percentage;
- planning coverage percentage;
- GIS/parcel coverage percentage;
- agenda/staff report coverage percentage;
- source health warnings;
- adapter gaps;
- blocked/manual-only sources;
- stale source count.

## Pulse Reliability Rule

The regional construction pulse should disclose coverage limitations.

Example:

- Active project clusters: 412.
- Permit coverage: 18 of 24 jurisdictions active.
- Planning coverage: 12 of 24 jurisdictions active.
- Unmapped jurisdictions: 3.
- Source health warnings: 2.

Do not present the pulse as complete when coverage is incomplete.

## Out-of-Zone Jurisdiction Rule

Out-of-zone jurisdictions discovered through entity footprint should be classified as relationship-horizon references unless promoted.

They should not be included in active coverage metrics unless they become watchlist or active operational zones.

## Search Integration

When a user searches a jurisdiction, the system should show:

- construction activity records if available;
- source coverage status;
- source gaps;
- known portals;
- monitoring status;
- last checked time;
- unmapped categories;
- suggested next source-discovery actions.

## Enrichment Integration

Jurisdiction coverage affects enrichment confidence.

If source coverage is weak, the system should not overstate missing data.

Example:

- authority unknown because current permit source lacks party fields;
- planning source not yet mapped;
- agenda source manual-only;
- therefore authority remains unresolved with coverage limitation.

## Non-Negotiable Constraints

- Do not confuse no results with no activity.
- Do not hide coverage gaps.
- Do not claim complete regional coverage without source evidence.
- Do not let unmapped jurisdictions silently disappear from dashboards.
- Do not treat one source category as full jurisdiction coverage.
- Do not promote out-of-zone jurisdictions automatically.
- Do not ignore manual-only or PDF-only sources; classify them.
- Do not bypass access controls to fill coverage gaps.

## Product Meaning

The jurisdiction intelligence and coverage mapping model makes ConstructionSight honest about what it knows, where it knows it, and where coverage remains incomplete. It prevents false confidence in the regional construction pulse and gives the platform a disciplined path to map every city, county, source, gap, and expansion candidate.
