from __future__ import annotations

from pathlib import Path

from constructionsight.governance_certification_core import GovernanceFinding
from constructionsight.semantic_authorization_certification import (
    audit_semantic_authorization,
)


def _audit(tmp_path: Path, source: str) -> list[GovernanceFinding]:
    relative = Path("src/constructionsight/example_cli.py")
    absolute = tmp_path / relative
    absolute.parent.mkdir(parents=True, exist_ok=True)
    absolute.write_text(source, encoding="utf-8")
    findings: list[GovernanceFinding] = []
    audit_semantic_authorization(
        tmp_path,
        [relative],
        {"constructionsight.example_cli": "cli"},
        findings,
    )
    return findings


def _codes(findings: list[GovernanceFinding]) -> set[str]:
    return {finding.code for finding in findings}


def test_boolean_only_high_impact_cli_is_rejected(tmp_path: Path) -> None:
    findings = _audit(
        tmp_path,
        """
def execute(execute_live: bool) -> None:
    if execute_live:
        execute_transport(execute_live=execute_live)
""",
    )

    assert "AUTH-BOOLEAN-002" in _codes(findings)


def test_direct_effect_call_is_rejected_even_with_confirmation(tmp_path: Path) -> None:
    findings = _audit(
        tmp_path,
        """
def execute(execute_live: bool) -> None:
    execute_ceqanet_csv_live_request(request, execute_live=execute_live)
""",
    )

    assert "AUTH-BYPASS-001" in _codes(findings)
    assert "AUTH-BOOLEAN-002" in _codes(findings)


def test_authorized_application_service_delegation_is_accepted(tmp_path: Path) -> None:
    findings = _audit(
        tmp_path,
        """
def execute(execute_live: bool) -> None:
    execute_authorized_ceqanet_detail(caller_confirmation=execute_live)
""",
    )

    assert findings == []


def test_governed_evidence_series_service_name_is_accepted(tmp_path: Path) -> None:
    findings = _audit(
        tmp_path,
        """
def execute(execute_live: bool) -> None:
    execute_ceqanet_csv_evidence_request(execute_live=execute_live)
""",
    )

    assert findings == []


def test_non_cli_module_is_outside_cli_delegation_rule(tmp_path: Path) -> None:
    relative = Path("src/constructionsight/transport.py")
    absolute = tmp_path / relative
    absolute.parent.mkdir(parents=True, exist_ok=True)
    absolute.write_text(
        "def execute(execute_live: bool) -> None:\n    pass\n",
        encoding="utf-8",
    )
    findings: list[GovernanceFinding] = []

    audit_semantic_authorization(
        tmp_path,
        [relative],
        {"constructionsight.transport": "transport"},
        findings,
    )

    assert findings == []
