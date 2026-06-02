# ConstructionSight Product UI, Branding, and Linux Packaging Standard

## Status

Canonical product requirement.

ConstructionSight must not remain a terminal-only research utility. The finished product must feel like a legitimate official desktop intelligence application with a refined graphical interface, Linux installer, desktop launcher, and branded icon system.

## Product Experience Requirement

ConstructionSight must provide:

1. A polished graphical user interface.
2. A visually refined, modern, uncluttered layout.
3. A branded application icon.
4. A Linux installer path.
5. A desktop launcher entry.
6. A local database-backed workflow.
7. A professional first-run experience.
8. Clear separation between verified data, unverified assumptions, inferred relationships, confidence scoring, and provenance.

The GUI must not feel like a rough script wrapper. It must feel like a real installed program.

## Preferred Desktop Architecture

Initial preferred stack:

- Python backend/core engine
- PySide6 / Qt GUI frontend
- SQLite local development database
- Future PostgreSQL option for production-scale deployments
- AppImage and/or `.deb` installer packaging for Linux
- `.desktop` launcher integration
- PNG/SVG icon assets generated from the approved logo

Reasoning:

- PySide6 keeps the GUI inside the Python ecosystem.
- Qt provides mature native desktop widgets and professional layout control.
- SQLite keeps the early installer lightweight.
- AppImage provides broad Linux compatibility.
- `.deb` packaging can support Debian, Ubuntu, Zorin, Kali, and related distributions.

## GUI Modules

The GUI should eventually include these major screens:

1. Dashboard
   - source verification status
   - new high-value leads
   - ingestion health
   - current database status

2. Source Registry
   - jurisdictions
   - portals
   - platform family
   - verification status
   - confidence score
   - extraction difficulty

3. Verification Console
   - URL reachability
   - detected portal type
   - login/captcha/paywall/access-control warnings
   - evidence snapshot
   - verification notes

4. Lead Intelligence
   - project name
   - jurisdiction
   - address/APN
   - project phase
   - estimated lead value
   - security opportunity score
   - source provenance

5. Relationship Graph
   - developers
   - owners
   - contractors
   - applicants
   - engineers
   - architects
   - parcels
   - permits
   - planning cases
   - CEQA records
   - agenda items

6. Evidence / Provenance Viewer
   - source URL
   - capture time
   - adapter used
   - raw evidence snippet
   - normalized record
   - confidence and uncertainty fields

7. Settings
   - database path
   - lawful-access controls
   - rate-limit settings
   - export settings
   - appearance/theme settings

## Visual Direction

ConstructionSight should look:

- clean
- sharp
- restrained
- modern
- official
- premium
- investigation-grade
- data-dense without being cluttered

Avoid:

- toy-like styling
- excessive neon
- hacker-cliche visuals
- cluttered dashboards
- raw terminal dumps in the primary interface
- unstyled default widgets where custom styling is needed

## Branding and Logo Requirement

The application must use the user-provided ConstructionSight logo as the canonical source asset.

The logo asset should be committed under:

```text
assets/brand/logo_original/
```

Generated application icon outputs should later be stored under:

```text
assets/brand/generated/
```

Expected generated outputs:

```text
assets/brand/generated/constructionsight.svg
assets/brand/generated/constructionsight_16.png
assets/brand/generated/constructionsight_32.png
assets/brand/generated/constructionsight_64.png
assets/brand/generated/constructionsight_128.png
assets/brand/generated/constructionsight_256.png
assets/brand/generated/constructionsight_512.png
```

The installer and desktop launcher must use the approved generated icon.

## Linux Installer Requirement

ConstructionSight must eventually provide at least one official Linux installation artifact.

Preferred sequence:

1. Local developer launch command.
2. Desktop launcher file.
3. AppImage package.
4. `.deb` package.
5. Optional Flatpak later.

Expected Linux desktop files:

```text
packaging/linux/constructionsight.desktop
packaging/linux/appimage/
packaging/linux/deb/
```

## Packaging Acceptance Criteria

A release-ready Linux package must:

1. Install or launch without requiring the user to manually run Python commands.
2. Display the ConstructionSight icon in the application launcher.
3. Open a graphical desktop window.
4. Initialize or locate the local database.
5. Provide access to source registry records.
6. Preserve lawful-access controls.
7. Provide clear error messages when dependencies or source access checks fail.
8. Avoid writing generated databases into the Git repository.

## Development Rule

The GUI and packaging system must not be treated as cosmetic afterthoughts. They are core product requirements and must be designed into the architecture before the ingestion system becomes too complex.
