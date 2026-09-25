from __future__ import annotations

from constructionsight.architecture_boundary_certification import (
    audit_architecture_boundaries,
)
from constructionsight.governance_certification_core import GovernanceFinding


def _codes(findings: list[GovernanceFinding]) -> set[str]:
    return {finding.code for finding in findings}


def test_transport_module_requires_exact_network_policy() -> None:
    findings: list[GovernanceFinding] = []

    audit_architecture_boundaries(
        layer_by_module={"constructionsight.transport": "transport"},
        graph={"constructionsight.transport": set()},
        network_contract={"policies": []},
        findings=findings,
    )

    assert "NET-BOUNDARY-002" in _codes(findings)


def test_network_policy_must_reference_transport_module() -> None:
    findings: list[GovernanceFinding] = []

    audit_architecture_boundaries(
        layer_by_module={"constructionsight.service": "application"},
        graph={"constructionsight.service": set()},
        network_contract={
            "policies": [
                {
                    "id": "CS-NET-TEST",
                    "module": "constructionsight.service",
                }
            ]
        },
        findings=findings,
    )

    assert "NET-BOUNDARY-004" in _codes(findings)


def test_low_level_http_engine_cannot_be_imported_by_application() -> None:
    findings: list[GovernanceFinding] = []

    audit_architecture_boundaries(
        layer_by_module={
            "constructionsight.service": "application",
            "constructionsight.http_transport": "transport",
        },
        graph={
            "constructionsight.service": {"constructionsight.http_transport"},
            "constructionsight.http_transport": set(),
        },
        network_contract={
            "policies": [
                {
                    "id": "CS-NET-ENGINE",
                    "module": "constructionsight.http_transport",
                }
            ]
        },
        findings=findings,
    )

    assert "ARCH-BYPASS-001" in _codes(findings)
