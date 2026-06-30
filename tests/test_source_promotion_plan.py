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
from constructionsight.source_promotion_plan_cli import app
from constructionsight.source_promotion_plan_models import SourcePromotionPlanAction
from constructionsight.source_promotion_plan_service import build_source_promotion_plan
from constructionsight.source_readiness_models import HttpReachabilityResult
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


def test_plan_keeps_unverified_without_manual_evidence() -> None:
    report = build_source_promotion_plan(
        [_source()],
        default_adapter_family_specs(),
        check_http=True,
        http_checker=_reachable,
    )
    row = report.rows[0]

    assert row.planned_action == SourcePromotionPlanAction.KEEP_UNVERIFIED
    assert row.proposed_registry_status is None
    assert "checklist evidence is insufficient" in row.reasons[-1]


def test_plan_marks_partial_for_placeholder_adapter_with_complete_evidence() -> None:
    report = build_source_promotion_plan(
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

    assert row.planned_action == SourcePromotionPlanAction.MARK_PARTIAL_CANDIDATE
    assert row.proposed_registry_status == "partial"


def test_plan_marks_verified_candidate_for_mature_adapter_with_complete_evidence() -> None:
    specs = default_adapter_family_specs()
    specs[PlatformFamily.ACCELA_ACA] = AdapterFamilySpec(
        platform_family=PlatformFamily.ACCELA_ACA,
        status=AdapterImplementationStatus.LIVE_READ_ONLY,
    )
    report = build_source_promotion_plan(
        [_source()],
        specs,
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

    assert row.planned_action == SourcePromotionPlanAction.VERIFIED_CANDIDATE_REVIEW
    assert row.proposed_registry_status == "verified"


def test_plan_marks_blocked_candidate_when_barrier_observed() -> None:
    report = build_source_promotion_plan(
        [_source()],
        default_adapter_family_specs(),
        observations=[
            SourceVerificationObservation(
                source_name="Test Source",
                access_barrier_observed=True,
                evidence_refs=["manual:block"],
            )
        ],
    )
    row = report.rows[0]

    assert row.planned_action == SourcePromotionPlanAction.MARK_BLOCKED_CANDIDATE
    assert row.proposed_registry_status == "blocked"


def test_source_promotion_plan_cli_outputs_json(tmp_path) -> None:
    registry_path = tmp_path / "sources.json"
    registry_path.write_text(_registry_json(), encoding="utf-8")
    runner = CliRunner()

    result = runner.invoke(app, ["plan", str(registry_path), "--json-output"])

    assert result.exit_code == 0
    assert '"source_count": 1' in result.output
    assert '"keep_unverified": 1' in result.output
