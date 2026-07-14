# CEQAnet Source-Maturity Proposal

## Purpose

ConstructionSight can now build and independently verify one report-only CEQAnet source-maturity proposal from the canonical source registry and the retained CSV evidence chain.

The proposal does not promote CEQAnet. Its only supported decision is `keep_partial`.

## Bound evidence

The builder validates and binds:

- the complete source-registry digest;
- the original one-request live execution digest and response-body SHA-256;
- the Windows-1252 replay digest and inspection digest; and
- the independently recomputed replay-verification result.

The current canonical evidence is:

- `data/source_registry.seed.json`;
- `evidence/source_verification/ceqanet_csv_live_execution_2026-07-12.json`;
- `evidence/source_verification/ceqanet_csv_windows1252_replay_2026-07-12.json`; and
- `evidence/source_verification/ceqanet_csv_windows1252_replay_verification_2026-07-12.json`.

The canonical outputs are:

- `evidence/source_verification/ceqanet_source_maturity_proposal_2026-07-13.json`;
- `evidence/source_verification/ceqanet_source_maturity_proposal_verification_2026-07-13.json`; and
- `docs/audits/ceqanet_source_maturity_proposal_2026-07-13.md`.

## Decision boundary

A valid proposal records that one official CSV response returned HTTP 200 and that the exact retained body independently replays as Windows-1252. It also preserves all current blockers:

- one point-in-time response does not establish recurring availability;
- retained evidence does not authorize recurring automated access;
- the canonical registry remains `partial`;
- the HTML automated-access barrier remains outside the CSV proof; and
- no scheduler, cadence, retry policy, or recurring success series exists.

The proposal schema fixes network execution, persistence mutation, registry-mutation authority, and recurring-execution authority to `false`.

## Operator commands

```text
constructionsight-ceqanet-maturity build \
  data/source_registry.seed.json \
  evidence/source_verification/ceqanet_csv_live_execution_2026-07-12.json \
  evidence/source_verification/ceqanet_csv_windows1252_replay_2026-07-12.json \
  evidence/source_verification/ceqanet_csv_windows1252_replay_verification_2026-07-12.json \
  --output <proposal.json>

constructionsight-ceqanet-maturity verify \
  data/source_registry.seed.json \
  evidence/source_verification/ceqanet_csv_live_execution_2026-07-12.json \
  evidence/source_verification/ceqanet_csv_windows1252_replay_2026-07-12.json \
  evidence/source_verification/ceqanet_csv_windows1252_replay_verification_2026-07-12.json \
  <proposal.json> \
  --output <verification.json>
```

Both commands are offline. Neither command mutates the source registry.

## Next gate

A bounded official-CSV evidence policy, the empty governed baseline, and sequence 1 with one independently verified project observation are now committed. The remaining gate is three additional separately authorized passing observations on later unused UTC dates, including the document export scope. Promotion, production scheduling, retries, domain persistence, and broader coverage remain unauthorized.
