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
from constructionsight.source_verification_checklist_cli import app
from constructionsight.source_verification_checklist_models import (
    ChecklistItemStatus,
    SourceVerificationChecklistStatus,
    SourceVerificationObservation,
)
from constructionsight.source_verification_checklist_service import (
    build_source_verification_checklist_report,
)


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


def _reachable(source: PublicSource) -> HttpReachabilityResult:
    return HttpReachabilityResult(
        checked=True,
        reachable=True,
        status_code=200,
        method="HEAD",
        final_url=str(source.public_url),
    )


def test_checklist_without_observations_stays_entry_reachable_only() -> None:
    report = build_source_verification_checklist_report(
        [_source()],
        default_adapter_family_specs(),
        check_http=True,
        http_checker=_reachable,
    )
    row = report.rows[0]

    assert row.checklist_status == SourceVerificationChecklistStatus.PUBLIC_ENTRY_REACHABLE
    assert row.public_entry_page == ChecklistItemStatus.OBSERVED
    assert row.query_behavior == ChecklistItemStatus.NOT_CHECKED
    assert "entry reachability is not query/list/detail verification" in row.limitations


def test_checklist_observation_can_record_query_and_detail_behavior() -> None:
    report = build_source_verification_checklist_report(
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
                evidence_refs=["manual:test"],
            )
        ],
    )
    row = report.rows[0]

    assert row.checklist_status == SourceVerificationChecklistStatus.DETAIL_BEHAVIOR_OBSERVED
    assert row.detail_page == ChecklistItemStatus.OBSERVED
    assert row.access_barrier == ChecklistItemStatus.NOT_OBSERVED
    assert row.evidence_refs == ["manual:test"]


def test_checklist_cli_outputs_json(tmp_path) -> None:
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

    result = runner.invoke(app, ["checklist", str(registry_path), "--json-output"])

    assert result.exit_code == 0
    assert '"source_count": 1' in result.output
    assert '"needs_manual_review": 1' in result.output
