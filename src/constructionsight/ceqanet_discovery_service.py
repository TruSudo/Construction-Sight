"""Application boundary for CEQAnet public-search discovery."""

from __future__ import annotations

from constructionsight.ceqanet_discovery_http import (
    CeqanetDiscoveryResult,
    CeqanetLiveDiscovery,
)


def discover_ceqanet_public_search() -> CeqanetDiscoveryResult:
    """Execute one bounded CEQAnet discovery through the owned transport boundary."""

    return CeqanetLiveDiscovery().discover()
