import json

import pytest
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
from constructionsight.source_registry_apply_service import (
    SourceRegistryApplyError,
    apply_source_registry_update_plan,
)
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


def _observation_json() -> str:
    return """
    [
      {
        "source_name": "Test Source",
        "public_entry_observed": true,
        "query_behavior_observed": true,
        "result_list_observed": true,
        "detail_page_observed": true,
        "access_barrier_observed": false,
        "terms_review_observed": true,
        "evidence_refs": ["manual:test"]
      }
    ]
    """


def _complete_observation() -> SourceVerificationObservation:
    return SourceVerificationObservation(
        source_name="Test Source",
        public_entry_observed=True,
        query_behavior_observed=True,
        result_list_observed=True,
        detail_page_observed=True,
        access_barrier_observed=False,
        terms_review_observed=True,
        evidence_refs=["manual:test"],
    )


def _reachable(source: PublicSource) -> HttpReachabilityResult:
    return HttpReachabilityResult(
        checked=True,
        reachable=True,
        status_code=200,
        method="HEAD",
        final_url=str(source.public_url),
    )


def _partial_plan() -> tuple[PublicSource, object]:
    source = _source()
    plan = build_source_registry_update_plan(
        [source],
        default_adapter_family_specs(),
        check_http=True,
        http_checker=_reachable,
        observations=[_complete_observation()],
    )
    return source, plan


def test_update_plan_has_no_updates_without_observations() -> None:
    report = build_source_registry_update_plan(
        [_source()],
        default_adapter_family_specs(),
        check_http=True,
        http_checker=_reachable,
    )
    row = report.rows[0]

    assert report.update_count == 0
    assert len(report.plan_digest) == 64
    assert row.update_required is False
    assert row.proposed_source_payload is None
    assert row.current_verification_status == "unverified"


def test_update_plan_builds_partial_payload_from_complete_placeholder_evidence() -> None:
    report = build_source_registry_update_plan(
        [_source()],
        default_adapter_family_specs(),
        check_http=True,
        http_checker=_reachable,
        observations=[_complete_observation()],
    )
    row = report.rows[0]

    assert report.update_count == 1
    assert row.update_required is True
    assert row.proposed_verification_status == "partial"
    assert row.proposed_source_payload is not None
    assert row.proposed_source_payload["verification_status"] == "partial"
    assert row.original_source_payload["verification_status"] == "unverified"
    assert row.evidence_refs == ["manual:test"]


def test_plan_digest_excludes_generation_timestamps() -> None:
    first = build_source_registry_update_plan(
        [_source()],
        default_adapter_family_specs(),
        observations=[_complete_observation()],
    )
    second = build_source_registry_update_plan(
        [_source()],
        default_adapter_family_specs(),
        observations=[_complete_observation()],
    )

    assert first.plan_digest == second.plan_digest


def test_apply_updates_only_the_approved_status_change() -> None:
    source = _source()
    plan = build_source_registry_update_plan(
        [source],
        default_adapter_family_specs(),
        observations=[_complete_observation()],
    )

    updated, report = apply_source_registry_update_plan(
        [source],
        plan,
        approved_plan_digest=plan.plan_digest,
    )

    assert updated[0].verification_status == VerificationStatus.PARTIAL
    assert report.applied_count == 1
    assert report.registry_changed is True
    assert report.original_registry_digest != report.updated_registry_digest
    assert report.rows[0].evidence_refs == ["manual:test"]


def test_apply_rejects_tampered_plan_content() -> None:
    source = _source()
    plan = build_source_registry_update_plan(
        [source],
        default_adapter_family_specs(),
        observations=[_complete_observation()],
    )
    plan.rows[0].reasons.append("tampered after approval")

    with pytest.raises(SourceRegistryApplyError, match="plan digest"):
        apply_source_registry_update_plan(
            [source],
            plan,
            approved_plan_digest=plan.plan_digest,
        )


def test_apply_rejects_stale_registry_source() -> None:
    source = _source()
    plan = build_source_registry_update_plan(
        [source],
        default_adapter_family_specs(),
        observations=[_complete_observation()],
    )
    changed_source = source.model_copy(update={"confidence_score": 20})

    with pytest.raises(SourceRegistryApplyError, match="changed after plan generation"):
        apply_source_registry_update_plan(
            [changed_source],
            plan,
            approved_plan_digest=plan.plan_digest,
        )


def test_apply_rejects_status_change_without_evidence_references() -> None:
    source = _source()
    plan = build_source_registry_update_plan(
        [source],
        default_adapter_family_specs(),
        observations=[
            SourceVerificationObservation(
                source_name="Test Source",
                query_behavior_observed=True,
            )
        ],
    )

    with pytest.raises(SourceRegistryApplyError, match="requires evidence references"):
        apply_source_registry_update_plan(
            [source],
            plan,
            approved_plan_digest=plan.plan_digest,
        )


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
    assert "Plan digest:" in result.stdout


def test_source_registry_apply_cli_writes_separate_registry_and_audit(tmp_path) -> None:
    registry_path = tmp_path / "sources.json"
    observations_path = tmp_path / "observations.json"
    plan_path = tmp_path / "plan.json"
    updated_path = tmp_path / "updated_sources.json"
    audit_path = tmp_path / "apply_audit.json"
    registry_path.write_text(_registry_json(), encoding="utf-8")
    observations_path.write_text(_observation_json(), encoding="utf-8")
    runner = CliRunner()

    plan_result = runner.invoke(
        app,
        [
            "plan",
            str(registry_path),
            "--observations-path",
            str(observations_path),
            "--output",
            str(plan_path),
        ],
    )
    assert plan_result.exit_code == 0
    plan_payload = json.loads(plan_path.read_text(encoding="utf-8"))

    apply_result = runner.invoke(
        app,
        [
            "apply",
            str(registry_path),
            str(plan_path),
            "--approved-plan-digest",
            plan_payload["plan_digest"],
            "--audit-output",
            str(audit_path),
            "--output",
            str(updated_path),
            "--apply",
        ],
    )

    assert apply_result.exit_code == 0
    original_payload = json.loads(registry_path.read_text(encoding="utf-8"))
    updated_payload = json.loads(updated_path.read_text(encoding="utf-8"))
    audit_payload = json.loads(audit_path.read_text(encoding="utf-8"))
    assert original_payload[0]["verification_status"] == "unverified"
    assert updated_payload[0]["verification_status"] == "partial"
    assert audit_payload["applied_count"] == 1


def test_source_registry_apply_cli_requires_explicit_apply_flag(tmp_path) -> None:
    registry_path = tmp_path / "sources.json"
    observations_path = tmp_path / "observations.json"
    plan_path = tmp_path / "plan.json"
    updated_path = tmp_path / "updated_sources.json"
    audit_path = tmp_path / "apply_audit.json"
    registry_path.write_text(_registry_json(), encoding="utf-8")
    observations_path.write_text(_observation_json(), encoding="utf-8")
    runner = CliRunner()
    runner.invoke(
        app,
        [
            "plan",
            str(registry_path),
            "--observations-path",
            str(observations_path),
            "--output",
            str(plan_path),
        ],
    )
    plan_payload = json.loads(plan_path.read_text(encoding="utf-8"))

    result = runner.invoke(
        app,
        [
            "apply",
            str(registry_path),
            str(plan_path),
            "--approved-plan-digest",
            plan_payload["plan_digest"],
            "--audit-output",
            str(audit_path),
            "--output",
            str(updated_path),
        ],
    )

    assert result.exit_code != 0
    assert "Explicit --apply authorization is required" in result.stdout
