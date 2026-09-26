# ADR-0006: Temporary CEQAnet live-discovery compatibility re-export

- Status: Accepted with expiry
- Date: 2026-07-15
- Expires: 2026-10-15
- Owners: ConstructionSight maintainers

## Context

The legacy CLI and tests import `CeqanetLiveDiscovery` and `CeqanetDiscoveryResult` from `constructionsight.adapters.ceqanet`. Network execution has been removed from that adapter and placed in the approved `constructionsight.ceqanet_discovery_http` transport module.

## Decision

The adapter may temporarily re-export those two symbols. The exception is one exact import edge. Adapter methods do not call transport, receive a client, or execute network operations. The live implementation remains policy-bound, one-attempt, redirect-denying, response-bounded, and independently testable.

## Risk and compensating control

The re-export makes a transport type visible through an adapter namespace and could encourage future coupling. Architecture certification permits only the exact source/target edge, the regression test proves the public API and typed transport behavior, and the exception expires automatically. New adapter-to-transport edges remain prohibited.

## Removal condition

Move all callers to `constructionsight.ceqanet_discovery_http`, remove the re-export, and delete the architecture exception before 2026-10-15.
