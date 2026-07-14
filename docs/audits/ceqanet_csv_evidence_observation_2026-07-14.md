# CEQAnet Governed CSV Evidence Observation 1 — 2026-07-14

## Result

The first observation under policy
`d84e6b80234a96799593db0601cc92e6480bad15bfd016001b35568c481c1674`
completed successfully.

- Export scope: `project`
- SCH number: `2026030377`
- Request URL:
  `https://ceqanet.lci.ca.gov/Search?OutputFormat=CSV&Sch=2026030377`
- Authorized/executed UTC date: `2026-07-14`
- HTTP requests: `1`
- HTTP status: `200`
- Retries: `0`
- Timeout: `20.0` seconds
- Maximum body: `10,000,000` bytes
- Complete retained body: `true`
- Retained body length: `7,832` bytes
- Body SHA-256:
  `5b1bc503c81d12ed0f00e52539edb437b42ae4c3a539a25e1c82a02b84273163`
- Content type: `text/csv`
- Encoding: `windows-1252`
- Parsed source rows: `2`
- Inspection digest:
  `e6888864835947ef758b22b5c3f8533fafa848a310e9b54acc94fd45fd5add07`
- Evidence-execution digest:
  `57c2c3a64f65f6cd7ca8e512c862d02fe92b04fcaa7cc1bb6eaeb7b091857f10`
- Independent live verification: passed with `0` findings

No attachment was downloaded, no domain persistence was mutated, no retry was
attempted, and no access-control bypass was attempted.

## Pre-request environment diagnostic

The first CLI invocation stopped before HTTP client construction because the
approved execution environment used a SOCKS proxy and lacked the `socksio`
transport package. It created no execution artifact and issued no HTTP request.
After the transport dependency was installed in the isolated staging
environment, the same governed command performed the single request recorded
above.

This pre-request failure is not counted as an HTTP retry because the client was
never constructed and no request reached CEQAnet.

## Append-only series result

The observation was incorporated offline into sequence 1.

- Series sequence: `1`
- Predecessor series digest:
  `b2a18770ec5ca28dfb907ce74b0b5ba120e6bb028ee35e3acd5188d42c182634`
- Observation digest:
  `562490071332c4db8b39dae435dad9fc0ce03fa87feb14f356d13bbf64e67f38`
- Series digest:
  `a6f6e548d675ee9716822fef87cc02d8a4d169f16ab151bae0f297321b8c07df`
- Observation count: `1`
- Successful observation count: `1`
- Successful UTC dates: `2026-07-14`
- Successful export scopes: `project`
- Status: `collecting`
- Ready for maturity review: `false`
- Independent series verification: passed with `0` findings

Source promotion and production recurring execution remain fixed to `false`.

## Canonical artifacts

- `evidence/source_verification/ceqanet_csv_evidence_execution_2026-07-14_project.json`
- `evidence/source_verification/ceqanet_csv_evidence_series_2026-07-14_sequence_1.json`
- `evidence/source_verification/ceqanet_csv_evidence_series_verification_2026-07-14_sequence_1.json`

## Remaining gate

No further CEQAnet evidence execution is permitted on UTC 2026-07-14.

At least three additional successful observations on later unused UTC dates are
required. The remaining series must cover the `document` export scope. Every
later execution remains separately authorized, one-request, zero-retry, fully
retained, independently verified, and subject to terminal access-control halt
rules.

This single new observation does not establish recurring availability,
completeness, verified usable coverage, or production readiness. CEQAnet remains
`partial`.
