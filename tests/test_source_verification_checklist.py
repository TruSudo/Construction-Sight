import json

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
    _build_source_verification_checklist_report_from_results,
    build_source_observation_templates,
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


def test_checklist_without_observations_stays_entry_reachable_only() -> None:
    source = _source()
    report = _build_source_verification_checklist_report_from_results(
        [source],
        default_adapter_family_specs(),
        http_results=(_reachable(source),),
        observations=None,
    )
    row = report.rows[0]

    assert row.checklist_status == SourceVerificationChecklistStatus.PUBLIC_ENTRY_REACHABLE
    assert row.public_entry_page == ChecklistItemStatus.OBSERVED
    assert row.query_behavior == ChecklistItemStatus.NOT_CHECKED
    assert "entry reachability is not query/list/detail evidence" in row.limitations


def test_checklist_observation_can_record_query_and_detail_behavior() -> None:
    source = _source()
    report = _build_source_verification_checklist_report_from_results(
        [source],
        default_adapter_family_specs(),
        http_results=(_reachable(source),),
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


def test_source_observation_template_defaults_to_unknowns() -> None:
    templates = build_source_observation_templates([_source()])
    template = templates[0]

    assert template.source_name == "Test Source"
    assert template.public_entry_observed is None
    assert template.query_behavior_observed is None
    assert template.result_list_observed is None
    assert template.detail_page_observed is None
    assert template.access_barrier_observed is None
    assert template.terms_review_observed is None
    assert template.instructions
    assert template.to_observation().source_key == template.source_key


def test_checklist_cli_outputs_json(tmp_path) -> None:
    registry_path = tmp_path / "sources.json"
    registry_path.write_text(_registry_json(), encoding="utf-8")
    runner = CliRunner()

    result = runner.invoke(app, ["checklist", str(registry_path), "--json-output"])

    assert result.exit_code == 0
    assert '"source_count": 1' in result.output
    assert '"needs_manual_review": 1' in result.output


def test_observation_template_cli_writes_file(tmp_path) -> None:
    registry_path = tmp_path / "sources.json"
    output_path = tmp_path / "observations.template.json"
    registry_path.write_text(_registry_json(), encoding="utf-8")
    runner = CliRunner()

    result = runner.invoke(
        app,
        ["observation-template", str(registry_path), "--output", str(output_path)],
    )

    assert result.exit_code == 0
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload[0]["source_name"] == "Test Source"
    assert payload[0]["query_behavior_observed"] is None
    assert payload[0]["evidence_refs"] == []
