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
from constructionsight.source_promotion_plan_service import (
    _build_source_promotion_plan_from_checklist,
)
from constructionsight.source_readiness_models import HttpReachabilityResult
from constructionsight.source_registry_apply_service import (
    SourceRegistryApplyError,
    apply_source_registry_update_plan,
)
from constructionsight.source_registry_integrity import source_registry_digest
from constructionsight.source_registry_update_plan_cli import app
from constructionsight.source_registry_update_plan_service import (
    _build_source_registry_update_plan_from_promotion_plan,
    build_source_registry_update_plan,
)
from constructionsight.source_verification_checklist_models import SourceVerificationObservation
from constructionsight.source_verification_checklist_service import (
    _build_source_verification_checklist_report_from_results,
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


def _other_source() -> PublicSource:
    return PublicSource(
        jurisdiction=Jurisdiction(
            name="Other City",
            county="Riverside",
            jurisdiction_type="city",
        ),
        source_name="Other Source",
        source_type=SourceType.CITY_PORTAL,
        platform_family=PlatformFamily.TYLER_ENERGOV,
        public_url="https://example.invalid/other",
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


def test_update_plan_has_no_updates_without_observations() -> None:
    source = _source()
    checklist = _build_source_verification_checklist_report_from_results(
        [source],
        default_adapter_family_specs(),
        http_results=(_reachable(source),),
        observations=None,
    )
    promotion_plan = _build_source_promotion_plan_from_checklist(checklist)
    report = _build_source_registry_update_plan_from_promotion_plan(
        [source],
        promotion_plan,
    )
    row = report.rows[0]

    assert report.update_count == 0
    assert len(report.registry_digest) == 64
    assert len(report.plan_digest) == 64
    assert row.update_required is False
    assert row.proposed_source_payload is None
    assert row.current_verification_status == "unverified"


def test_update_plan_builds_partial_payload_from_complete_placeholder_evidence() -> None:
    source = _source()
    checklist = _build_source_verification_checklist_report_from_results(
        [source],
        default_adapter_family_specs(),
        http_results=(_reachable(source),),
        observations=[_complete_observation()],
    )
    promotion_plan = _build_source_promotion_plan_from_checklist(checklist)
    report = _build_source_registry_update_plan_from_promotion_plan(
        [source],
        promotion_plan,
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

    assert first.registry_digest == second.registry_digest
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
    assert report.original_registry_digest == plan.registry_digest
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


def test_apply_rejects_tampered_action_counts() -> None:
    source = _source()
    plan = build_source_registry_update_plan(
        [source],
        default_adapter_family_specs(),
        observations=[_complete_observation()],
    )
    plan.action_counts = {"keep_unverified": 1}

    with pytest.raises(SourceRegistryApplyError, match="action counts"):
        apply_source_registry_update_plan(
            [source],
            plan,
            approved_plan_digest=plan.plan_digest,
        )


def test_apply_rejects_reordered_registry_snapshot() -> None:
    sources = [_source(), _other_source()]
    plan = build_source_registry_update_plan(
        sources,
        default_adapter_family_specs(),
        observations=[_complete_observation()],
    )

    with pytest.raises(SourceRegistryApplyError, match="current registry digest"):
        apply_source_registry_update_plan(
            list(reversed(sources)),
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

    with pytest.raises(SourceRegistryApplyError, match="current registry digest"):
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
    assert "Registry digest:" in result.stdout
    assert "Plan digest:" in result.stdout


def test_source_registry_plan_cli_refuses_registry_as_output(tmp_path) -> None:
    registry_path = tmp_path / "sources.json"
    registry_path.write_text(_registry_json(), encoding="utf-8")
    original = registry_path.read_text(encoding="utf-8")
    runner = CliRunner()

    result = runner.invoke(
        app,
        [
            "plan",
            str(registry_path),
            "--output",
            str(registry_path),
            "--overwrite",
        ],
    )

    assert result.exit_code != 0
    assert "plan output path must differ from registry input path" in result.stderr
    assert registry_path.read_text(encoding="utf-8") == original


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
            "--operator-id",
            "operator:test",
            "--authorization-reason",
            "Apply one reviewed test registry plan.",
        ],
    )

    assert apply_result.exit_code == 0
    original_payload = json.loads(registry_path.read_text(encoding="utf-8"))
    updated_payload = json.loads(updated_path.read_text(encoding="utf-8"))
    audit_payload = json.loads(audit_path.read_text(encoding="utf-8"))
    assert original_payload[0]["verification_status"] == "unverified"
    assert updated_payload[0]["verification_status"] == "partial"
    assert audit_payload["applied_count"] == 1
    # Successful audit evidence must not predate the authoritative target.
    assert updated_path.stat().st_mtime_ns <= audit_path.stat().st_mtime_ns



def test_source_registry_apply_target_failure_does_not_publish_success_audit(
    tmp_path, monkeypatch,
) -> None:
    import constructionsight.source_registry_update_plan_cli as cli

    registry_path = tmp_path / "sources.json"
    observations_path = tmp_path / "observations.json"
    plan_path = tmp_path / "plan.json"
    updated_path = tmp_path / "updated_sources.json"
    audit_path = tmp_path / "apply_audit.json"
    registry_path.write_text(_registry_json(), encoding="utf-8")
    observations_path.write_text(_observation_json(), encoding="utf-8")
    original_registry = registry_path.read_bytes()
    runner = CliRunner()
    plan_result = runner.invoke(
        app,
        [
            "plan", str(registry_path), "--observations-path", str(observations_path),
            "--output", str(plan_path),
        ],
    )
    assert plan_result.exit_code == 0
    digest = json.loads(plan_path.read_text(encoding="utf-8"))["plan_digest"]

    original_write = cli._atomic_write_text

    def fail_target(path, content, *, overwrite=True, **kwargs):
        if path == updated_path:
            raise OSError("injected authoritative registry publication failure")
        return original_write(path, content, overwrite=overwrite, **kwargs)

    monkeypatch.setattr(cli, "_atomic_write_text", fail_target)
    result = runner.invoke(
        app,
        [
            "apply", str(registry_path), str(plan_path),
            "--approved-plan-digest", digest,
            "--audit-output", str(audit_path),
            "--output", str(updated_path),
            "--apply", "--operator-id", "operator:test",
            "--authorization-reason", "Exercise late authoritative publication failure.",
        ],
    )

    assert result.exit_code != 0
    assert not audit_path.exists()
    assert not updated_path.exists()
    assert registry_path.read_bytes() == original_registry
    assert len(list(tmp_path.glob(".source-registry-*.pending.json"))) == 1

    # A retry rolls the prepared transaction forward without repeating the
    # authorization/effect service or publishing an audit before target commit.
    monkeypatch.setattr(cli, "_atomic_write_text", original_write)
    args = [
        "apply", str(registry_path), str(plan_path),
        "--approved-plan-digest", digest, "--audit-output", str(audit_path),
        "--output", str(updated_path), "--apply",
        "--operator-id", "operator:test",
        "--authorization-reason", "Exercise late authoritative publication failure.",
    ]
    retry = runner.invoke(app, args)
    assert retry.exit_code == 0, str(retry.exception)
    assert "Recovered exact pending source registry transaction." in retry.stdout
    assert (
        json.loads(updated_path.read_text(encoding="utf-8"))[0]["verification_status"]
        == "partial"
    )
    assert json.loads(audit_path.read_text(encoding="utf-8"))["applied_count"] == 1
    assert not list(tmp_path.glob(".source-registry-*.pending.json"))
    repeated = runner.invoke(app, args)
    assert repeated.exit_code != 0
    assert "Output path already exists" in repeated.stderr


def test_source_registry_apply_audit_failure_does_not_claim_success(
    tmp_path, monkeypatch,
) -> None:
    import constructionsight.source_registry_update_plan_cli as cli

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
            "plan", str(registry_path), "--observations-path", str(observations_path),
            "--output", str(plan_path),
        ],
    )
    assert plan_result.exit_code == 0
    digest = json.loads(plan_path.read_text(encoding="utf-8"))["plan_digest"]

    original_write = cli._atomic_write_text

    def fail_audit(path, content, *, overwrite=True, **kwargs):
        if path == audit_path:
            raise OSError("injected success-audit publication failure")
        return original_write(path, content, overwrite=overwrite, **kwargs)

    monkeypatch.setattr(cli, "_atomic_write_text", fail_audit)
    result = runner.invoke(
        app,
        [
            "apply", str(registry_path), str(plan_path),
            "--approved-plan-digest", digest,
            "--audit-output", str(audit_path),
            "--output", str(updated_path),
            "--apply", "--operator-id", "operator:test",
            "--authorization-reason", "Exercise late audit publication failure.",
        ],
    )

    assert result.exit_code != 0
    assert (
        json.loads(updated_path.read_text(encoding="utf-8"))[0]["verification_status"]
        == "partial"
    )
    assert not audit_path.exists()
    assert (
        "Registry target contents are published, but transaction completion failed" in result.stderr
    )
    assert "do not reapply until the target and audit are reconciled" in result.stderr
    assert "Applied 1 source registry status update(s)." not in result.stdout


    # Recover the exact committed transaction without reapplying its target.
    committed_bytes = updated_path.read_bytes()
    monkeypatch.setattr(cli, "_atomic_write_text", original_write)
    args = [
        "apply", str(registry_path), str(plan_path),
        "--approved-plan-digest", digest,
        "--audit-output", str(audit_path),
        "--output", str(updated_path),
        "--apply", "--operator-id", "operator:test",
        "--authorization-reason", "Exercise late audit publication failure.",
    ]

    # A divergent target must not be reported as a successful recovery.
    updated_path.write_bytes(b"[]\n")
    bad_retry = runner.invoke(app, args)
    assert bad_retry.exit_code != 0
    assert "manual reconciliation required" in bad_retry.stderr
    assert not audit_path.exists()
    assert updated_path.read_bytes() == b"[]\n"

    # Restoring the exact committed bytes permits audit-only replay.
    updated_path.write_bytes(committed_bytes)
    committed_mtime = updated_path.stat().st_mtime_ns
    retry = runner.invoke(app, args)
    assert retry.exit_code == 0, str(retry.exception)
    assert "Recovered exact pending source registry transaction." in retry.stdout
    assert updated_path.read_bytes() == committed_bytes
    assert updated_path.stat().st_mtime_ns == committed_mtime
    assert json.loads(audit_path.read_text(encoding="utf-8"))["applied_count"] == 1
    assert not list(tmp_path.glob(".source-registry-*.pending.json"))
    assert len(list(tmp_path.glob(".source-registry-*.lock"))) == 2




@pytest.mark.parametrize("interrupted_at", ["backup", "audit"])
def test_in_place_apply_replays_prepared_backup_and_committed_target(
    tmp_path, monkeypatch, interrupted_at,
) -> None:
    import constructionsight.source_registry_update_plan_cli as cli

    registry = tmp_path / "sources.json"
    observations = tmp_path / "observations.json"
    plan = tmp_path / "plan.json"
    backup = tmp_path / "sources.backup.json"
    audit = tmp_path / "sources.audit.json"
    registry.write_text(_registry_json(), encoding="utf-8")
    observations.write_text(_observation_json(), encoding="utf-8")
    before = registry.read_bytes()
    runner = CliRunner()
    prepared = runner.invoke(
        app,
        [
            "plan", str(registry), "--observations-path", str(observations),
            "--output", str(plan),
        ],
    )
    assert prepared.exit_code == 0
    approved = json.loads(plan.read_text(encoding="utf-8"))["plan_digest"]
    args = [
        "apply", str(registry), str(plan),
        "--approved-plan-digest", approved, "--audit-output", str(audit),
        "--in-place", "--backup-output", str(backup), "--apply",
        "--operator-id", "operator:test",
        "--authorization-reason", "Rehearse recoverable in-place registry apply.",
    ]
    original_write = cli._atomic_write_text

    def interrupted_write(path, content, *, overwrite=True, **kwargs):
        if path == (backup if interrupted_at == "backup" else audit):
            raise OSError("injected interruption before transaction finalization")
        return original_write(path, content, overwrite=overwrite, **kwargs)

    monkeypatch.setattr(cli, "_atomic_write_text", interrupted_write)
    first = runner.invoke(app, args)
    assert first.exit_code != 0
    assert not audit.exists()
    if interrupted_at == "backup":
        assert registry.read_bytes() == before
        assert not backup.exists()
    else:
        assert backup.read_bytes() == before
        assert (
            json.loads(registry.read_text(encoding="utf-8"))[0]["verification_status"]
            == "partial"
        )
    assert len(list(tmp_path.glob(".source-registry-*.pending.json"))) == 1

    monkeypatch.setattr(cli, "_atomic_write_text", original_write)
    recovered = runner.invoke(app, args)
    assert recovered.exit_code == 0, str(recovered.exception)
    assert "Recovered exact pending source registry transaction." in recovered.stdout
    assert json.loads(registry.read_text(encoding="utf-8"))[0]["verification_status"] == "partial"
    assert backup.read_bytes() == before
    assert json.loads(audit.read_text(encoding="utf-8"))["applied_count"] == 1
    assert not list(tmp_path.glob(".source-registry-*.pending.json"))




def test_registry_apply_process_death_after_target_commit_replays_audit(tmp_path) -> None:
    import multiprocessing
    import os

    registry = tmp_path / "sources.json"
    observations = tmp_path / "observations.json"
    plan = tmp_path / "plan.json"
    target = tmp_path / "updated_sources.json"
    audit = tmp_path / "apply_audit.json"
    registry.write_text(_registry_json(), encoding="utf-8")
    observations.write_text(_observation_json(), encoding="utf-8")
    runner = CliRunner()
    prepared = runner.invoke(
        app,
        [
            "plan", str(registry), "--observations-path", str(observations),
            "--output", str(plan),
        ],
    )
    assert prepared.exit_code == 0
    digest = json.loads(plan.read_text(encoding="utf-8"))["plan_digest"]
    args = [
        "apply", str(registry), str(plan),
        "--approved-plan-digest", digest, "--audit-output", str(audit),
        "--output", str(target), "--apply", "--operator-id", "operator:test",
        "--authorization-reason", "Recover a terminated registry apply process.",
    ]

    if os.name != "posix":
        result = runner.invoke(app, args)
        assert result.exit_code != 0
        assert not target.exists()
        assert not audit.exists()
        return

    def terminated_apply() -> None:
        import constructionsight.source_registry_update_plan_cli as cli

        original_write = cli._atomic_write_text

        def exit_after_commit(path, content, *, overwrite=True, **kwargs):
            original_write(path, content, overwrite=overwrite, **kwargs)
            if path == target:
                os._exit(73)

        cli._atomic_write_text = exit_after_commit
        CliRunner().invoke(app, args)
        os._exit(74)

    process = multiprocessing.get_context("fork").Process(target=terminated_apply)
    process.start()
    process.join(timeout=25)
    if process.is_alive():
        process.terminate()
        process.join(timeout=5)
    assert process.exitcode == 73
    committed = target.read_bytes()
    assert not audit.exists()
    assert len(list(tmp_path.glob(".source-registry-*.pending.json"))) == 1

    retry = runner.invoke(app, args)
    assert retry.exit_code == 0, str(retry.exception)
    assert "Recovered exact pending source registry transaction." in retry.stdout
    assert target.read_bytes() == committed
    assert json.loads(audit.read_text(encoding="utf-8"))["applied_count"] == 1
    assert not list(tmp_path.glob(".source-registry-*.pending.json"))




def test_registry_apply_cleanup_failure_does_not_misreport_audit_state(
    tmp_path, monkeypatch,
) -> None:
    import constructionsight.source_registry_update_plan_cli as cli

    registry = tmp_path / "sources.json"
    observations = tmp_path / "observations.json"
    plan = tmp_path / "plan.json"
    target = tmp_path / "updated_sources.json"
    audit = tmp_path / "apply_audit.json"
    registry.write_text(_registry_json(), encoding="utf-8")
    observations.write_text(_observation_json(), encoding="utf-8")
    runner = CliRunner()
    prepared = runner.invoke(
        app,
        [
            "plan", str(registry), "--observations-path", str(observations),
            "--output", str(plan),
        ],
    )
    assert prepared.exit_code == 0
    digest = json.loads(plan.read_text(encoding="utf-8"))["plan_digest"]
    original_unlink, original_fsync = cli.os.unlink, cli.os.fsync
    journal_removed = False
    injected = False

    def detect_journal_cleanup(path, *args, **kwargs):
        nonlocal journal_removed
        result = original_unlink(path, *args, **kwargs)
        if isinstance(path, str) and path.endswith(".pending.json"):
            journal_removed = True
        return result

    def fail_cleanup_fsync(fd):
        nonlocal injected
        if journal_removed and not injected:
            injected = True
            raise OSError("injected journal cleanup directory-sync error")
        return original_fsync(fd)

    monkeypatch.setattr(cli.os, "unlink", detect_journal_cleanup)
    monkeypatch.setattr(cli.os, "fsync", fail_cleanup_fsync)
    args = [
        "apply", str(registry), str(plan),
        "--approved-plan-digest", digest, "--audit-output", str(audit),
        "--output", str(target), "--apply",
        "--operator-id", "operator:test",
        "--authorization-reason", "Report uncertain cleanup without a false audit failure.",
    ]
    result = runner.invoke(app, args)
    assert result.exit_code != 0
    assert injected
    assert "Registry and audit contents match the prepared record" in result.stderr
    assert json.loads(target.read_text(encoding="utf-8"))[0]["verification_status"] == "partial"
    assert json.loads(audit.read_text(encoding="utf-8"))["applied_count"] == 1
    assert not list(tmp_path.glob(".source-registry-*.pending.json"))


def test_source_registry_apply_cli_refuses_output_equal_to_registry(tmp_path) -> None:
    registry_path = tmp_path / "sources.json"
    observations_path = tmp_path / "observations.json"
    plan_path = tmp_path / "plan.json"
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
            str(registry_path),
            "--apply",
            "--overwrite",
        ],
    )

    assert result.exit_code != 0
    assert "updated registry output path must differ from registry input path" in result.stderr


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
    assert "Explicit --apply caller confirmation is required" in result.stderr


def _recovery_case(tmp_path, monkeypatch, *, interrupted_at="target"):
    import constructionsight.source_registry_update_plan_cli as cli

    registry = tmp_path / "sources.json"
    plan = tmp_path / "plan.json"
    observations = tmp_path / "observations.json"
    output_dir = tmp_path / "outputs"
    output_dir.mkdir(mode=0o700)
    target = output_dir / "target.json"
    audit = output_dir / "audit.json"
    registry.write_text(_registry_json())
    observations.write_text(_observation_json())
    runner = CliRunner()
    planned = runner.invoke(app, ["plan", str(registry), "--observations-path",
                                  str(observations), "--output", str(plan)])
    assert planned.exit_code == 0, str(planned.exception)
    approved = json.loads(plan.read_text())["plan_digest"]
    args = ["apply", str(registry), str(plan), "--approved-plan-digest", approved,
            "--audit-output", str(audit), "--output", str(target), "--apply",
            "--operator-id", "operator:test", "--authorization-reason", "Recovery adversary."]
    original = cli._atomic_write_text

    def interrupted(path, content, *, overwrite=True, **kwargs):
        if path == (target if interrupted_at == "target" else audit):
            raise OSError("injected publication interruption")
        original(path, content, overwrite=overwrite, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(cli, "_atomic_write_text", interrupted)
        result = runner.invoke(app, args)
    assert result.exit_code != 0
    journal, = output_dir.glob(".source-registry-*.pending.json")
    return runner, args, registry, plan, target, audit, journal


@pytest.mark.parametrize("field", ["reasons", "source_name", "update_count"])
def test_recovery_revalidates_plan_contents(tmp_path, monkeypatch, field):
    runner, args, _, plan, target, audit, journal = _recovery_case(tmp_path, monkeypatch)
    payload = json.loads(plan.read_text())
    if field == "update_count":
        payload[field] = 0
    elif field == "reasons":
        payload["rows"][0][field] = ["unapproved replacement evidence"]
    else:
        payload["rows"][0][field] = "unapproved replacement name"
    plan.write_text(json.dumps(payload))
    result = runner.invoke(app, args)
    assert result.exit_code != 0
    assert not target.exists()
    assert not audit.exists()
    assert journal.exists()


@pytest.mark.parametrize("alteration", ["audit_count", "audit_rows", "target_identity"])
def test_recovery_revalidates_prepared_result(tmp_path, monkeypatch, alteration):
    import constructionsight.source_registry_update_plan_cli as cli

    runner, args, _, _, target, audit, journal = _recovery_case(tmp_path, monkeypatch)
    record = json.loads(journal.read_text())
    report = json.loads(record["audit_text"])
    if alteration == "audit_count":
        report["applied_count"] = 0
    elif alteration == "audit_rows":
        report["rows"][0]["evidence_refs"] = ["invented evidence"]
    else:
        sources = json.loads(record["target_text"])
        sources[0]["source_name"] = "unauthorized identity replacement"
        record["target_text"] = json.dumps(sources)
        record["updated_target_sha"] = cli._digest_bytes(record["target_text"].encode())
        report["updated_registry_digest"] = source_registry_digest(
            [PublicSource.model_validate(item) for item in sources]
        )
    record["audit_text"] = json.dumps(report)
    journal.write_text(cli._pending_text(record))
    result = runner.invoke(app, args)
    assert result.exit_code != 0
    assert not target.exists()
    assert not audit.exists()
    assert journal.exists()


def test_recovery_syncs_existing_target_before_success_audit(tmp_path, monkeypatch):
    import os
    import stat

    import constructionsight.source_registry_update_plan_cli as cli

    runner, args, _, _, target, audit, journal = _recovery_case(
        tmp_path, monkeypatch, interrupted_at="audit",
    )
    target_inode = target.stat().st_ino
    original = os.fsync
    synced = False

    def fail_target_sync(fd):
        nonlocal synced
        info = os.fstat(fd)
        if stat.S_ISREG(info.st_mode) and info.st_ino == target_inode:
            synced = True
            raise OSError("target durability unavailable")
        original(fd)

    monkeypatch.setattr(cli.os, "fsync", fail_target_sync)
    result = runner.invoke(app, args)
    assert synced
    assert result.exit_code != 0
    assert not audit.exists()
    assert journal.exists()


def test_registry_apply_does_not_publish_into_replaced_parent(tmp_path, monkeypatch):
    import constructionsight.source_registry_update_plan_cli as cli

    runner, args, _, _, target, audit, _ = _recovery_case(tmp_path, monkeypatch)
    original = cli._recover_pending_registry_apply
    old_parent = target.parent.with_name("retained-parent")

    def replace_parent(**kwargs):
        target.parent.rename(old_parent)
        target.parent.mkdir(mode=0o700)
        return original(**kwargs)

    monkeypatch.setattr(cli, "_recover_pending_registry_apply", replace_parent)
    result = runner.invoke(app, args)
    assert result.exit_code != 0
    assert not target.exists()
    assert not audit.exists()
    assert not list(target.parent.glob(".source-registry-*.pending.json"))
    assert list(old_parent.glob(".source-registry-*.pending.json"))


@pytest.mark.parametrize("replacement", ["unlink", "chmod", "symlink"])
def test_registry_rejects_altered_lock_before_recovery(tmp_path, monkeypatch, replacement):
    import os

    import constructionsight.source_registry_update_plan_cli as cli

    runner, args, _, _, target, audit, journal = _recovery_case(tmp_path, monkeypatch)
    original = cli._recover_pending_registry_apply

    def alter_lock(**kwargs):
        lock = target.with_name(cli._transaction_names(target)[0])
        if replacement == "chmod":
            lock.chmod(0o644)
        else:
            lock.unlink()
            if replacement == "symlink":
                os.symlink(tmp_path / "elsewhere", lock)
        return original(**kwargs)

    monkeypatch.setattr(cli, "_recover_pending_registry_apply", alter_lock)
    result = runner.invoke(app, args)
    assert result.exit_code != 0
    assert not target.exists()
    assert not audit.exists()
    assert journal.exists()


def test_registry_writers_sharing_audit_are_serialized_across_processes(tmp_path):
    import multiprocessing
    import os

    import constructionsight.source_registry_update_plan_cli as cli

    if os.name != "posix":
        with (
            pytest.raises(ValueError, match="locking is unavailable"),
            cli._serialized_registry_target(tmp_path / "target", inputs=(), outputs=()),
        ):
            pytest.fail("unsupported locking must fail closed")
        return
    context = multiprocessing.get_context("fork")
    first_entered, second_entered = context.Event(), context.Event()
    release = context.Event()
    shared_audit = tmp_path / "audit"

    def writer(name, entered, hold):
        target = tmp_path / name
        with cli._serialized_registry_target(
            target, inputs=(), outputs=(target, shared_audit),
        ):
            entered.set()
            if hold:
                assert release.wait(10)

    first = context.Process(target=writer, args=("first", first_entered, True))
    second = context.Process(target=writer, args=("second", second_entered, False))
    first.start()
    try:
        assert first_entered.wait(5)
        second.start()
        assert not second_entered.wait(0.2)
        release.set()
        assert second_entered.wait(5)
    finally:
        release.set()
        for process in (first, second):
            if process.pid is not None:
                process.join(5)
                if process.is_alive():
                    process.terminate()
                    process.join(5)
    assert first.exitcode == second.exitcode == 0


@pytest.mark.parametrize("artifact", ["journal", "target", "audit"])
def test_registry_recovers_publication_with_failed_directory_sync(tmp_path, monkeypatch, artifact):
    import constructionsight.source_registry_update_plan_cli as cli

    runner, args, _, _, target, audit, journal = _recovery_case(tmp_path, monkeypatch)
    if artifact == "journal":
        journal.unlink()
    selected = {"journal": journal, "target": target, "audit": audit}[artifact]
    original = cli._atomic_write_text

    def publication_sync_failure(path, content, **kwargs):
        original(path, content, **kwargs)
        if path == selected:
            raise OSError("injected after publication durability boundary")

    with monkeypatch.context() as patch:
        patch.setattr(cli, "_atomic_write_text", publication_sync_failure)
        first = runner.invoke(app, args)
    assert first.exit_code != 0
    assert journal.exists()
    result = runner.invoke(app, args)
    assert result.exit_code == 0, str(result.exception)
    assert json.loads(target.read_text())[0]["verification_status"] == "partial"
    assert json.loads(audit.read_text())["applied_count"] == 1
    assert not journal.exists()
