# CEQAnet CSV Evidence-Series Baseline — 2026-07-14

## Result

The canonical official-CSV evidence series is valid and empty.

- Status: `collecting`
- Observation count: `0`
- Successful observation count: `0`
- Ready for maturity review: `false`
- Series digest: `d8b214a5c3b381174700efa96e31ba284ff3625dd319741e2d56e6acb2559515`
- Policy digest: `d84e6b80234a96799593db0601cc92e6480bad15bfd016001b35568c481c1674`
- Independent verification: passed with 0 findings

No network request was made to create this baseline.

## Bound authority

The series binds the canonical policy effective from 2026-07-14 through
2026-08-13 inclusive. Each future evidence execution must:

- receive explicit per-execution authorization;
- perform exactly one official `/Search` CSV GET;
- use the policy timeout and body limit;
- retain the complete response body;
- preserve the full policy-bound execution envelope;
- pass independent recomputation before it can count as successful; and
- be the only execution represented for its UTC date.

The first HTTP 401, 403, 407, 429, or 451 observation ends the series without
bypass. Failed non-halt observations remain evidentiary but do not count toward
completion.

## Completion boundary

A later maturity review requires at least four independently passing
observations, at least three distinct successful UTC dates, and both project and
document export scopes. The one-execution-per-UTC-day policy means four new
passing observations necessarily span four UTC dates.

A completed series does not itself promote CEQAnet or authorize production
recurring execution. Both authority fields remain fixed to `false`.

## Canonical artifacts

- `evidence/source_verification/ceqanet_csv_evidence_series_2026-07-14.json`
- `evidence/source_verification/ceqanet_csv_evidence_series_verification_2026-07-14.json`
