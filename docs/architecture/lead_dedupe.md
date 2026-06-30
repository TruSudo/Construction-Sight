# Lead Dedupe

Lead dedupe prevents repeated review of the same underlying lead signal.

## Current implementation

The current implementation includes:

- `LeadFingerprint`
- `LeadDuplicateResult`
- deterministic fingerprint construction
- `unique`, `duplicate`, and `review_needed` classifications
- exact fingerprint matching
- same-site review matching
- same-source-record review matching
- model and service tests

## Match basis

The first fingerprint uses:

- site key
- source key plus source record ID
- normalized title

## Status meaning

- `unique`: no matching fingerprint was found.
- `duplicate`: the exact fingerprint already exists.
- `review_needed`: a related site or source record exists, but the fingerprint is not identical.

## Limitations

This layer is not yet persisted and has no CLI command. It is a model/service spine used by tests and future workflow layers.

## Forward requirement

When persistence is added, lead fingerprints must be stored before workflow activation so repeated public-record updates do not create duplicate operator work.
