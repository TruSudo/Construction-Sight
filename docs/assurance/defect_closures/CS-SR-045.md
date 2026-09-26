# CS-SR-045 Permanent Closure Evidence

Defect: `CS-SR-045 — lawful-access-fact-authority`

## Historical root cause

Generic lawful-access profiles defaulted all restriction flags to false. An unknown
login, captcha, robots, terms, paywall, or related access state could therefore be
misinterpreted as affirmative clearance and authorize a live public-source request
without evidence that the restriction facts had actually been established.

## Resolution

Resolution implementation commit:

`e8fb0753be361bf909405cd0f452164e8912c817`

Resolution Git tree:

`4394aa0d9f704b5b08da456d4d7b3523775df005`

The corrected implementation:

- requires an affirmative reviewed-facts marker before an otherwise clear source can
  be allowed;
- requires a retained nonblank review basis;
- treats unknown access facts as REVIEW_REQUIRED rather than ALLOWED;
- preserves immediate block/review behavior for explicit captcha, login, robots,
  terms, and paywall restrictions;
- makes generic adapter preflight fail closed on unknown facts; and
- prevents SourceVerifier from executing its HTTP transport unless reviewed access
  facts are supplied.

## Regression evidence

Canonical regression coverage includes:

- `tests/test_access_policy.py`
  - unknown all-clear state requires review;
  - review flag without basis is insufficient;
  - explicit restrictions remain fail-closed.
- `tests/test_adapter_base.py`
  - generic adapter preflight rejects unknown access facts;
  - reviewed public access can proceed.
- `tests/test_source_verifier.py`
  - proves the HTTP executor is not called when access facts are unknown;
  - proves reviewed profiles permit bounded verification.

## Exact-head validation

CI run `36113498026` validated exact implementation head
`e8fb0753be361bf909405cd0f452164e8912c817`.

On Python 3.11 and Python 3.12, Ruff, mypy, compileall, full pytest, focused mutation
certification, adapter contract audit, source adapter coverage audit, Native Maximum
Assurance preflight, repository/semantic certification, diff hygiene, environment
identity checks, and isolated vulnerability audits all passed. The only failing step
was the aggregate gate that intentionally rejected the still-active defect ledger.

This closure records permanent resolution of CS-SR-045. It does not claim final
zero-active-defect certification.
