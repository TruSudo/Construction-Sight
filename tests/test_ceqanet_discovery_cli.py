from typer.testing import CliRunner

import constructionsight.operator_services.ceqanet_discovery_service as discovery_operator
from constructionsight import cli
from constructionsight.ceqanet_discovery_http import CeqanetDiscoveryResult

runner = CliRunner()


def _successful_discovery() -> CeqanetDiscoveryResult:
    return CeqanetDiscoveryResult(
        url="https://ceqanet.lci.ca.gov/Search/Advanced",
        reachable=True,
        status_code=200,
        advanced_search_available=True,
        sch_number_field_detected=True,
        document_type_field_detected=True,
        date_field_detected=True,
        lead_agency_field_detected=True,
        notes="Synthetic successful CLI discovery.",
    )


def _unreachable_discovery() -> CeqanetDiscoveryResult:
    return CeqanetDiscoveryResult(
        url="https://ceqanet.lci.ca.gov/Search/Advanced",
        reachable=False,
        status_code=None,
        advanced_search_available=False,
        sch_number_field_detected=False,
        document_type_field_detected=False,
        date_field_detected=False,
        lead_agency_field_detected=False,
        notes="Synthetic unreachable CLI discovery.",
    )


def test_discover_ceqanet_cli_renders_successful_discovery(monkeypatch) -> None:
    monkeypatch.setattr(
        discovery_operator, "discover_ceqanet_public_search", _successful_discovery
    )

    result = runner.invoke(
        cli.app,
        [
            "discover-ceqanet",
            "--execute-live",
            "--operator-id",
            "operator:test",
            "--authorization-reason",
            "Review the bounded CEQAnet discovery surface.",
        ],
    )

    assert result.exit_code == 0
    assert "CEQAnet Public Search Discovery" in result.output
    assert "https://ceqanet.lci.ca.gov/Search/Advanced" in result.output
    assert "Reachable" in result.output
    assert "True" in result.output
    assert "Advanced search" in result.output
    assert "SCH number field" in result.output
    assert "Document type field" in result.output
    assert "Lead/public agency field" in result.output
    assert "Confidence" in result.output
    assert "95" in result.output


def test_discover_ceqanet_cli_exits_nonzero_when_unreachable(monkeypatch) -> None:
    monkeypatch.setattr(
        discovery_operator, "discover_ceqanet_public_search", _unreachable_discovery
    )

    result = runner.invoke(
        cli.app,
        [
            "discover-ceqanet",
            "--execute-live",
            "--operator-id",
            "operator:test",
            "--authorization-reason",
            "Review the bounded CEQAnet discovery surface.",
        ],
    )

    assert result.exit_code == 1
    assert "CEQAnet Public Search Discovery" in result.output
    assert "Reachable" in result.output
    assert "False" in result.output
    assert "Status code" in result.output
    assert "None" in result.output
    assert "Confidence" in result.output
    assert "0" in result.output



def test_discover_ceqanet_requires_explicit_live_authority(monkeypatch) -> None:
    calls = 0

    def unexpected_discovery() -> CeqanetDiscoveryResult:
        nonlocal calls
        calls += 1
        return _successful_discovery()

    monkeypatch.setattr(
        discovery_operator, "discover_ceqanet_public_search", unexpected_discovery
    )
    result = runner.invoke(
        cli.app,
        [
            "discover-ceqanet",
            "--operator-id",
            "operator:test",
            "--authorization-reason",
            "Attempt without live confirmation.",
        ],
    )

    assert result.exit_code != 0
    assert calls == 0
