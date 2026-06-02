# Phase 3 — Source Verification Engine

## Objective

Create a conservative public-source verification engine that confirms source reachability and detects basic public portal traits without bypassing authentication, captchas, paywalls, rate limits, access controls, or terms-of-service restrictions.

## Added Components

- `src/constructionsight/verification/source_verifier.py`
  - lightweight HTTP reachability checks
  - portal-family hint detection
  - public search hint detection
  - login/captcha/paywall warning detection
  - permit, agenda, PDF, and party-field hint detection
  - compact evidence snapshot capture
  - conservative confidence scoring

- `src/constructionsight/verification/__init__.py`
  - verification package export

- `src/constructionsight/storage/orm.py`
  - `VerificationRecord` ORM table
  - relationship between persisted sources and verification results

- `src/constructionsight/storage/verification_store.py`
  - verification-result persistence
  - latest-result listing
  - automatic source status/confidence update based on verification result

- `src/constructionsight/cli.py`
  - `verify-sources` command

- `tests/test_source_verifier.py`
  - detector and error-path tests

- `tests/test_verification_store.py`
  - persistence and source-status update test

## Local Validation Commands

```bash
git pull origin main
source .venv/bin/activate
python -m pytest
constructionsight init-db
constructionsight load-sources data/source_registry.seed.json
constructionsight verify-sources --limit 2
constructionsight list-sources
```

## Legal / Access Boundary

The Phase 3 verifier is intentionally limited. It checks public URLs, response status, visible text hints, and response metadata only. It does not:

- bypass login gates
- bypass captchas
- bypass paywalls
- evade rate limits
- use hidden credentials
- access non-public data
- perform deep scraping behind restricted workflows

## Known Limitations

- Portal detection is heuristic and must be treated as evidence, not certainty.
- Verification does not yet inspect `robots.txt` directly.
- Verification does not yet download PDFs or parse agenda packets.
- Existing local SQLite databases may need to be deleted/recreated if they were created before the `source_verifications` table existed.

## Phase 3 Completion Criteria

Phase 3 is locally validated only when:

1. `python -m pytest` passes.
2. `constructionsight verify-sources --limit 2` stores verification records.
3. `constructionsight list-sources` shows updated verification status and confidence for checked sources.
4. Any SQLite migration/table issue is resolved before proceeding.
