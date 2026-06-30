from typer.testing import CliRunner

from constructionsight.adapters.specs import default_adapter_family_specs
from constructionsight.models import (
    Jurisdiction,
    PlatformFamily,
    PublicSource,
    SourceType,
    VerificationStatus,
)
from constructionsight.source_readiness_models import HttpReachabilityResult
from constructionsight.source_registry_update_plan_cli import app
from constructionsight.source_registry_update_plan_service import (
    build_source_registry_update_plan,
)
from constructionsight.source_verification_checklist_models import SourceVerificationObservation


def _source() -> PublicSource:
    return PublicSource(
        jurisdiction=Jurisdiction(
            name="Test City",
            county="San Bernardino",
            jurisdiction_type="city",
        ),
        source_name="Test Source",
        source_type=SourceType.CITY_PORTAL,
        platform_family=PlatformFamily.ACCELA_ACA,
        public_url="https://example.invalid/source",
        verification_status=VerificationStatus.UNVERIFIED,
    )


def _registry_json() -> str:
    return """
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
    """


def _reachable(source: PublicSource) -> HttpReachabilityResult:
    return HttpReachabilityResult(
        checked=True,
        reachable=True,
        status_code=200,
        method="HEAD",
        final_url=str(source.public_url),
    )


def test_update_plan_has_no_updates_without_observations() -> None:
    report = build_source_registry_update_plan(
        [_source()],
        default_adapter_family_specs(),
        check_http=True,
        http_checker=_reachable,
    )
    row = report.rows[0]

    assert report.update_count == 0
    assert row.update_required is False
    assert row.proposed_source_payload is None
    assert row.current_verification_status == "unverified"


def test_update_plan_builds_partial_payload_from_complete_placeholder_evidence() -> None:
    report = build_source_registry_update_plan(
        [_source()],
        default_adapter_family_specs(),
        check_http=True,
        http_checker=_reachable,
        observations=[
            SourceVerificationObservation(
                source_name="Test Source",
                public_entry_observed=True,
                query_behavior_observed=True,
                result_list_observed=True,
                detail_page_observed=True,
                access_barrier_observed=False,
                terms_review_observed=True,
                evidence_refs=["manual:test"],
            )
        ],
    )
    row = report.rows[0]

    assert report.update_count == 1
    assert row.update_required is True
    assert row.proposed_verification_status == "partial"
    assert row.proposed_source_payload is not None
    assert row.proposed_source_payload["verification_status"] == "partial"
    assert row.original_source_payload["verification_status"] == "unverified"


def test_source_registry_update_plan_cli_writes_json(tmp_path) -> None:
    registry_path = tmp_path / "sources.json"
    output_path = tmp_path / "registry_update_plan.json"
    registry_path.write_text(_registry_json(), encoding="utf-8")
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["plan", str(registry_path), "--output", str(output_path)],
    )

    assert result.exit_code == 0
    assert output_path.exists()
    assert '"source_count": 1' in output_path.read_text(encoding="utf-8")
