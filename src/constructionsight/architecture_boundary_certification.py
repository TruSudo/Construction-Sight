"""Cross-contract architecture boundary certification."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from constructionsight.governance_certification_core import GovernanceFinding, _finding

_LOW_LEVEL_TRANSPORT_MODULE = "constructionsight.http_transport"


def audit_architecture_boundaries(
    *,
    layer_by_module: Mapping[str, str],
    graph: Mapping[str, set[str]],
    network_contract: Mapping[str, Any],
    findings: list[GovernanceFinding],
) -> None:
    """Reject transport-policy gaps and generic low-level transport bypasses."""

    contract_path = "governance/network_contract.toml"
    raw_policies = network_contract.get("policies")
    if not isinstance(raw_policies, list):
        return
    policy_modules = {
        str(policy.get("module"))
        for policy in raw_policies
        if isinstance(policy, dict) and isinstance(policy.get("module"), str)
    }
    transport_modules = {
        module for module, layer in layer_by_module.items() if layer == "transport"
    }
    for module in sorted(transport_modules - policy_modules):
        findings.append(
            _finding(
                "NET-BOUNDARY-002",
                Path("src", *module.split(".")).with_suffix(".py"),
                "transport module lacks an exact network policy",
            )
        )
    for module in sorted(policy_modules):
        layer = layer_by_module.get(module)
        if layer is None:
            findings.append(
                _finding(
                    "NET-BOUNDARY-003",
                    contract_path,
                    f"network policy references an unknown production module: {module}",
                )
            )
        elif layer != "transport":
            findings.append(
                _finding(
                    "NET-BOUNDARY-004",
                    Path("src", *module.split(".")).with_suffix(".py"),
                    f"network policy module is classified as {layer}, not transport",
                )
            )
    for source, targets in sorted(graph.items()):
        if _LOW_LEVEL_TRANSPORT_MODULE not in targets:
            continue
        source_layer = layer_by_module.get(source)
        if source_layer != "transport":
            findings.append(
                _finding(
                    "ARCH-BYPASS-001",
                    Path("src", *source.split(".")).with_suffix(".py"),
                    "only declared transport wrappers may import the low-level HTTP engine",
                )
            )
