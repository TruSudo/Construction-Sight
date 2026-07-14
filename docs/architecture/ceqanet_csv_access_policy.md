# CEQAnet Bounded CSV Access Policy

## Purpose

ConstructionSight defines a digest-bound, expiring policy for controlled evidence collection from the official CEQAnet CSV export surface.

The policy does not authorize production recurring collection. It permits only separately approved evidence executions that satisfy every bound control.

## Bound evidence

The canonical policy binds:

- the complete source registry digest;
- the keep-partial maturity proposal digest;
- the original live CSV execution digest; and
- the verified Windows-1252 replay digest.

Canonical artifacts:

- `evidence/source_verification/ceqanet_csv_access_policy_2026-07-14.json`;
- `evidence/source_verification/ceqanet_csv_access_policy_verification_2026-07-14.json`; and
- `docs/audits/ceqanet_csv_access_policy_2026-07-14.md`.

## Authority window

The canonical policy is effective from `2026-07-14` through `2026-08-13`, inclusive, in UTC.

Policy authority cannot exceed 31 days. Not-yet-effective or expired policies fail the currentness gate and cannot support an evidence execution.

## Exact execution controls

Each separately authorized execution is restricted to:

- official host `ceqanet.lci.ca.gov`;
- official path `/Search`;
- project or document CSV export shape;
- one `GET`;
- one execution per UTC day;
- zero retries;
- 20-second timeout;
- 10,000,000-byte maximum body;
- complete response retention; and
- independent offline verification.

Any HTTP `401`, `403`, `407`, `429`, or `451` response halts the evidence series. No bypass is permitted.

## Forbidden behavior

The policy fixes the following authority to `false`:

- HTML automation;
- credentials or CAPTCHA handling;
- access-control bypass;
- attachment download;
- persistence mutation;
- registry mutation;
- source promotion; and
- production recurring execution.

## Evidence-series completion criteria

A later maturity review requires at least four passing observations across at least three distinct UTC dates, covering both project and document CSV exports. Every observation must retain the complete body and pass independent verification.

## Operator commands

```text
constructionsight-ceqanet-access-policy build \
  data/source_registry.seed.json \
  evidence/source_verification/ceqanet_csv_live_execution_2026-07-12.json \
  evidence/source_verification/ceqanet_csv_windows1252_replay_2026-07-12.json \
  evidence/source_verification/ceqanet_csv_windows1252_replay_verification_2026-07-12.json \
  evidence/source_verification/ceqanet_source_maturity_proposal_2026-07-13.json \
  evidence/source_verification/ceqanet_source_maturity_proposal_verification_2026-07-13.json \
  --effective-date 2026-07-14 \
  --expires-on 2026-08-13 \
  --output <policy.json>

constructionsight-ceqanet-access-policy verify \
  <registry> <execution> <replay> <replay-verification> \
  <maturity-proposal> <maturity-verification> <policy> \
  --output <policy-verification.json>

constructionsight-ceqanet-access-policy check-current \
  <policy> --as-of-date <YYYY-MM-DD>
```

All policy commands are offline. They produce or validate governance artifacts and make no network request.

## Governed evidence-series gate

The separate [CEQAnet evidence-series architecture](ceqanet_csv_evidence_series.md)
now supplies the policy-bound execution envelope, immutable ledger, independent
recomputation, daily limit, and access-control halt enforcement. Its canonical
baseline is valid, empty, and `collecting`; creating it made no network request.

## Next gate

Perform one separately authorized official-CSV evidence execution on an unused
UTC date, commit its complete policy-bound artifact, and independently rebuild
the series. The policy and ledger do not promote CEQAnet, authorize a scheduler,
or establish verified usable coverage.
