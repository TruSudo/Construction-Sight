# CEQAnet Bounded CSV Access Policy — 2026-07-14

## Outcome

Policy status: `ready_for_explicit_evidence_collection`.

The policy authorizes only separately approved evidence runs against the official CEQAnet CSV export surface. It does not authorize production recurring collection, scheduling, persistence, source promotion, HTML automation, credentials, CAPTCHA handling, or access-control bypass.

## Evidence bindings

- Source registry digest: `a5353548592c4dd55498409139983c7eef38766ef476c17fcd72829fb68da30e`
- Maturity proposal digest: `3a8069a5dd72a921f1e4324347d00d3c5a8ee8f7100676bdff3a702d6a424088`
- Live execution digest: `9a861dcee42092eb6f2d8f5c86673f4aca4c75cd0d42beddaa930cc093221a95`
- Replay digest: `49d3aaf3357f448252ab8133e83bdfdb65175b0fe4646babfc0cc10af27f9b60`
- Policy digest: `d84e6b80234a96799593db0601cc92e6480bad15bfd016001b35568c481c1674`

Independent policy verification passed with zero findings.

## Authority window

- Effective UTC date: `2026-07-14`
- Final authorized UTC date: `2026-08-13`
- Maximum policy duration: 31 days
- Expired or not-yet-effective policies fail the execution-currentness gate.

## Per-execution controls

- Official host: `ceqanet.lci.ca.gov`
- Official path: `/Search`
- Method: `GET`
- Maximum requests: `1`
- Maximum executions per UTC day: `1`
- Retry count: `0`
- Timeout: `20` seconds
- Maximum body size: `10,000,000` bytes
- Complete response retention: required
- Independent verification: required
- Explicit per-execution authorization: required

Access-control responses `401`, `403`, `407`, `429`, or `451` halt the evidence series. No bypass is permitted.

## Evidence-series completion gate

Before another maturity review, ConstructionSight requires:

- at least 4 passing observations;
- at least 3 distinct UTC dates;
- both project and document CSV export scopes;
- complete retained bodies; and
- independent verification of every execution.

## Production boundary

The canonical source remains `partial`. Production recurring execution, persistence, registry mutation, source promotion, attachment download, and broader coverage claims remain unauthorized.
