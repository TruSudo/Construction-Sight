# Daily lead workflow — draft, 2026-10-13

NOT MERGEABLE FOR VISUAL ACCEPTANCE: static diagnostic pixel difference 21.52% (limit 0.5%), channel MAE 13.52 (limit 2). Native comparison is blocked: supplied reference is 1536×864, requested viewport 1672×941. Exact fonts, original logo and texture assets remain unresolved. Measured geometry/colors are in design_tokens.json; screenshot/diff test is in tests/visual and enforced by a PR visual workflow.

Implemented: capture-only daily command, saved run history and snapshots, last-good-data warning, New today/last-run filters, persistent local status/notes/contact date/loss reasons, filtered CSV, weights.json, score/outcome reporting including closed feedback outside Active, and reported developer/owner name groups. Browser feedback verification uses a separate labeled Demo fixture, never real contact/outcome claims.

Live run: 17 SMARTS requests, 698 SB + 918 Riverside rows → 660 + 903 distinct leads; 52 duplicate rows and one missing-ID row; zero new/removed identities. Fontana official historical address query: 14 records, four exact address candidates; current project identity unverified and no size/value/architect/GC/issue-date facts filled. Current Accela access returned 403. Offline-first map.json replaces the default public tile endpoint.

Checks: Phase 1 full suite after live fixes: 2,436 passed. New affected suite: 78 passed; affected Ruff/Mypy and JS syntax passed. Real-data screenshot at 1672×941 had zero JS errors. All other sidebar pages and Watchlist remain stubs. Source conditions are presented in a one-page tools view. No new governance/certification/phase documents or source writes; no automatic sending.
