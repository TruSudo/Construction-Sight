# CS-SR-032 Permanent Closure Evidence

## Resolution

Production-visible CEQAnet HTTP paths deny redirects at request time through the common bounded transport and retain fail-closed redirect regressions.

Validated resolution head: `f773c926168c6284c171bfe05aac7f729c870ddc`

Resolution Git tree: `d9e084b83ee887ae65e16918592cc9410e06d87a`

Canonical CI run `36117450690` validated that exact head on Python 3.11 and Python 3.12.
Both isolated vulnerability audits passed. Ruff, mypy, compileall, full pytest, focused
mutation certification, adapter/source audits, assurance preflight,
repository/semantic certification, diff hygiene, and environment identity checks passed.
The only failing quality step was the intentional aggregate blocker for remaining active
defects.

## Evidence

- `src/constructionsight/http_transport.py`
- `src/constructionsight/ceqanet_detail_http.py`
- `src/constructionsight/ceqanet_discovery_http.py`

## Regression coverage

- `tests/test_ceqanet_discovery_http.py`
- `tests/test_ceqanet_listing_executor.py`
- `tests/test_http_transport.py`

This closure preserves the original finding and retires only its corrected root cause.
Remaining active findings and final assurance obligations are unchanged.
