# Command Center — 2026-10-13

Run `./run-command-center.sh`; it captures official SMARTS Active rows and opens http://127.0.0.1:8765. Use `--offline` for the last complete real capture or `--demo` for the labeled fixture preview.

Two complete live runs: 17 requests each, 698 San Bernardino + 918 Riverside source rows; 1,563 unique ranked leads (660 + 903), 52 duplicate rows, one row without usable source IDs. Second run: 30.6 seconds, zero new/missing identities. All original pages retained in the existing evidence journal. Security fit uses one weights dict, name keywords, reported dates, and repeat-developer counts; unknown/conflicting fields remain unknown.

Validation: full suite 2,435 passed before the live-data fixes; 70 affected tests passed after them. Real-data browser checks passed for search, county filtering, list/dossier selection and stub navigation, with zero JS errors. Map tiles require browser HTTPS access to tile.openstreetmap.org; offline coordinate-grid fallback works.

All other sidebar destinations and Watchlist & Reminders are Coming soon. Parcel/permit/CEQA corroboration, project photos, size/value/architect/GC enrichment, outreach, bids, royalties and automation are not part of this slice. Lawful read-only access and no outbound sending remain in place.
