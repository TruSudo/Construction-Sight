from typer.testing import CliRunner

from constructionsight.adapters.specs import (
    AdapterFamilySpec,
    AdapterImplementationStatus,
    default_adapter_family_specs,
)
from constructionsight.models import (
    Jurisdiction,
    PlatformFamily,
    PublicSource,
    SourceType,
    VerificationStatus,
)
from constructionsight.source_readiness_cli import app
from constructionsight.source_readiness_models import (
    HttpReachabilityResult,
    SourceReadinessStatus,
)
from constructionsight.source_readiness_service import (
    _build_source_readiness_report_with_results,
    build_source_readiness_report,
)


def _source(
    *,
    name: str = "Test Source",
    platform: PlatformFamily = PlatformFamily.ACCELA_ACA,
    status: VerificationStatus = VerificationStatus.UNVERIFIED,
) -> PublicSource:
    return PublicSource(
        jurisdiction=Jurisdiction(
            name="Test City",
            county="San Bernardino",
            jurisdiction_type="city",
        ),
        source_name=name,
        source_type=SourceType.CITY_PORTAL,
        platform_family=platform,
        public_url="https://example.invalid/source",
        verification_status=status,
    )


def _reachable(source: PublicSource) -> HttpReachabilityResult:
    return HttpReachabilityResult(
        checked=True,
        reachable=True,
        status_code=200,
        method="HEAD",
        final_url=str(source.public_url),
    )


def _blocked(_source: PublicSource) -> HttpReachabilityResult:
    return HttpReachabilityResult(
        checked=True,
        reachable=False,
        status_code=403,
        method="HEAD",
    )


def _failed(_source: PublicSource) -> HttpReachabilityResult:
    return HttpReachabilityResult(
        checked=True,
        reachable=False,
        error="ConnectError",
    )


def test_source_readiness_seed_only_without_http_check() -> None:
    report = build_source_readiness_report(
        [_source()],
        default_adapter_family_specs(),
    )
    row = report.rows[0]

    assert row.readiness_status == SourceReadinessStatus.SEED_ONLY
    assert row.http_reachability.checked is False
    assert report.status_counts == {"seed_only": 1}
    assert "source remains a registry seed" in row.limitations[0]


def test_source_readiness_reachable_unverified_is_not_verified() -> None:
    source = _source(status=VerificationStatus.UNVERIFIED)
    report = _build_source_readiness_report_with_results(
        [source],
        default_adapter_family_specs(),
        http_results=(_reachable(source),),
    )
    row = report.rows[0]

    assert row.readiness_status == SourceReadinessStatus.REACHABLE
    assert row.http_reachability.status_code == 200
    assert "not equivalent to verified source coverage" in row.limitations[0]


def test_source_readiness_blocked_http_response() -> None:
    source = _source()
    report = _build_source_readiness_report_with_results(
        [source],
        default_adapter_family_specs(),
        http_results=(_blocked(source),),
    )
    row = report.rows[0]

    assert row.readiness_status == SourceReadinessStatus.BLOCKED
    assert row.http_reachability.status_code == 403
    assert "blocked or unauthorized" in row.limitations[0]


def test_source_readiness_failed_http_response() -> None:
    source = _source()
    report = _build_source_readiness_report_with_results(
        [source],
        default_adapter_family_specs(),
        http_results=(_failed(source),),
    )
    row = report.rows[0]

    assert row.readiness_status == SourceReadinessStatus.FAILED
    assert row.limitations == ["ConnectError"]


def test_source_readiness_verified_placeholder_adapter_is_partial() -> None:
    source = _source(status=VerificationStatus.VERIFIED)
    report = _build_source_readiness_report_with_results(
        [source],
        default_adapter_family_specs(),
        http_results=(_reachable(source),),
    )
    row = report.rows[0]

    assert row.adapter_status == "placeholder"
    assert row.readiness_status == SourceReadinessStatus.PARTIAL
    assert "adapter maturity prevents verified usable coverage" in row.limitations[0]


def test_source_readiness_verified_live_adapter_is_candidate() -> None:
    specs = default_adapter_family_specs()
    specs[PlatformFamily.ACCELA_ACA] = AdapterFamilySpec(
        platform_family=PlatformFamily.ACCELA_ACA,
        status=AdapterImplementationStatus.LIVE_READ_ONLY,
    )
    source = _source(status=VerificationStatus.VERIFIED)
    report = _build_source_readiness_report_with_results(
        [source],
        specs,
        http_results=(_reachable(source),),
    )
    row = report.rows[0]

    assert row.readiness_status == SourceReadinessStatus.VERIFIED_CANDIDATE
    assert row.limitations == []
    assert report.status_counts == {"verified_candidate": 1}


def test_source_readiness_cli_outputs_json_without_http_mutation(tmp_path) -> None:
    registry_path = tmp_path / "sources.json"
    registry_path.write_text(
        """
        [
          {
            "jurisdiction": {
              "name": "Test City",
              "county": "San Bernardino",
              "state": "CA",
              "jurisdiction_type": "city"
            },
            "source_name": "Test Source",
            "source_type": "city_portal",
            "platform_family": "accela_aca",
            "public_url": "https://example.invalid/source",
            "verification_status": "unverified"
          }
        ]
        """,
        encoding="utf-8",
    )
    runner = CliRunner()

    result = runner.invoke(app, ["check", str(registry_path), "--json-output"])

    assert result.exit_code == 0
    assert '"readiness_status": "seed_only"' in result.output
    assert '"checked": false' in result.output
