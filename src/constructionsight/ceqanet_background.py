"""Reviewed finite CEQAnet background acquisition, separate from manual allowances.

Only an explicitly enabled plan is eligible. Each exact window gets one durable
reservation before any request. An ambiguous crash is never retried; a retained
result can still be handed to the investigation engine after restart.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from constructionsight import data_folder, effect_consumption
from constructionsight.adapters.ceqanet_result_parser import parse_ceqanet_result_page
from constructionsight.authorization_decision import (
    build_authorization_decision,
    validate_authorization_decision,
)
from constructionsight.authorization_decision_models import AuthorizationReusePolicy
from constructionsight.ceqanet_operator_bundle import _serialized_bundle_output
from constructionsight.ceqanet_persistence_preview import build_ceqanet_persistence_preview
from constructionsight.ceqanet_recurring_run_models import (
    CeqanetRecurringRunDefinition,
    CeqanetRecurringRunExecution,
    CeqanetRecurringRunManifest,
    CeqanetRunReadiness,
    canonical_digest,
)
from constructionsight.ceqanet_recurring_run_service import (
    assert_ceqanet_definition_evidence_current,
    build_ceqanet_recurring_run_manifest,
    execute_ceqanet_recurring_run,
    verify_ceqanet_recurring_run_execution,
)
from constructionsight.effect_consumption import _execute_owned_effect
from constructionsight.effect_consumption_models import EffectReplayPolicy
from constructionsight.local_operator_authorization import (
    LocalAuthorizationResult,
    authorize_local_operator_operation,
)
from constructionsight.models import PublicSource
from constructionsight.source_verification_checklist_models import SourceVerificationChecklistReport
from constructionsight.storage.effect_consumption_store import EffectConsumptionError
from constructionsight.storage.runtime_artifacts import (
    publish_runtime_artifact,
    read_runtime_artifact,
    write_runtime_text,
)
from constructionsight.verification.source_verifier import SourceVerifier

if TYPE_CHECKING:
    from constructionsight.investigation_runtime import InvestigationRuntime

ACTION = "enable-ceqanet-background-plan"
MAX_BYTES = 2 * 1024 * 1024


def _now() -> datetime:
    return datetime.now(UTC)


def _bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _read(path: Path) -> Any:
    return json.loads(read_runtime_artifact(path, max_bytes=MAX_BYTES))


def _publish(path: Path, value: Any) -> None:
    content = _bytes(value)
    publish_runtime_artifact(path, [content], max_bytes=MAX_BYTES)


def _authority_root(root: Path) -> Path:
    # Outside the user-data backup: restoring observations cannot undo a request
    # reservation, access stop, or revocation. The existing effect ledger owns it.
    identity = canonical_digest({"directory": str(root.parent.absolute())})
    return (
        effect_consumption._CONSUMPTION_DATABASE_PATH.parent
        / "ceqa-background-authority"
        / identity
    )


def _flagged(root: Path, name: str) -> bool:
    return (root / name).exists() or (_authority_root(root) / name).exists()


def _flag(root: Path, name: str, payload: dict[str, Any]) -> None:
    for location in (_authority_root(root), root):
        path = location / name
        if not path.exists():
            _publish(path, payload)


class BackgroundWindow(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    due_at: AwareDatetime
    manifest: CeqanetRecurringRunManifest


class CeqanetBackgroundPlan(BaseModel):
    """Exact finite scope; the nested manual manifest grants no new authority."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["ceqanet_background_plan.v1"] = "ceqanet_background_plan.v1"
    definition: CeqanetRecurringRunDefinition
    registry_path: str
    checklist_path: str
    expires_at: AwareDatetime
    windows: list[BackgroundWindow] = Field(min_length=1, max_length=31)

    @model_validator(mode="after")
    def validate_scope(self) -> CeqanetBackgroundPlan:
        self.definition.assert_integrity()
        if self.definition.readiness != CeqanetRunReadiness.READY_FOR_MANUAL_EXECUTION:
            raise ValueError("background source definition is blocked")
        # One page per window bounds traffic and stops immediately on any barrier.
        if self.definition.query_template.max_pages != 1:
            raise ValueError("background acquisition permits one page per window")
        if (
            not 0 < self.definition.timeout_seconds <= 20
            or not 1 <= self.definition.max_body_chars <= 50000
        ):
            raise ValueError("background request exceeds CS-NET-002 bounds")
        for path in (self.registry_path, self.checklist_path):
            if not Path(path).is_absolute() or ".." in Path(path).parts:
                raise ValueError("current evidence paths must be canonical absolute paths")
        previous: BackgroundWindow | None = None
        for window in self.windows:
            manifest = window.manifest
            manifest.assert_integrity()
            expected = build_ceqanet_recurring_run_manifest(
                self.definition, window_start=manifest.window_start, window_end=manifest.window_end
            )
            if manifest.approval_payload() != expected.approval_payload():
                raise ValueError("background window does not match its source definition")
            if manifest.window_end > window.due_at.astimezone(UTC).date():
                raise ValueError("background window cannot collect future dates")
            if previous and (
                window.due_at - previous.due_at < timedelta(days=1)
                or manifest.window_start <= previous.manifest.window_end
            ):
                raise ValueError("background windows must be distinct and at least one day apart")
            previous = window
        if (
            not self.windows[-1].due_at
            < self.expires_at
            <= self.windows[0].due_at + timedelta(days=31)
        ):
            raise ValueError("background plan must expire within 31 days of its first window")
        return self

    @property
    def digest(self) -> str:
        return canonical_digest(self.model_dump(mode="json", round_trip=True))

    def current_evidence(self) -> tuple[list[PublicSource], SourceVerificationChecklistReport]:
        payload = _read(Path(self.registry_path))
        if not isinstance(payload, list):
            raise ValueError("current source registry must contain a list")
        sources = [PublicSource.model_validate(row) for row in payload]
        checklist = SourceVerificationChecklistReport.model_validate(
            _read(Path(self.checklist_path))
        )
        assert_ceqanet_definition_evidence_current(self.definition, sources, checklist)
        return sources, checklist


def build_background_plan(
    definition: CeqanetRecurringRunDefinition,
    *,
    registry_path: Path,
    checklist_path: Path,
    first_due: datetime,
    days: int,
) -> CeqanetBackgroundPlan:
    """Preview consecutive daily windows without granting access or changing state."""
    if type(days) is not int or not 1 <= days <= 31:
        raise ValueError("background plan requires between 1 and 31 daily windows")
    if first_due.tzinfo is None or first_due.utcoffset() is None:
        raise ValueError("first due time must include a timezone")
    first_due = first_due.astimezone(UTC)
    windows = []
    for offset in range(days):
        due = first_due + timedelta(days=offset)
        day = due.date() - timedelta(days=1)
        windows.append(
            BackgroundWindow(
                due_at=due,
                manifest=build_ceqanet_recurring_run_manifest(
                    definition,
                    window_start=day,
                    window_end=day,
                ),
            )
        )
    plan = CeqanetBackgroundPlan(
        definition=definition,
        registry_path=str(registry_path.absolute()),
        checklist_path=str(checklist_path.absolute()),
        windows=windows,
        expires_at=first_due + timedelta(days=days),
    )
    plan.current_evidence()
    return plan


def enable_plan(
    directory: Path, plan: CeqanetBackgroundPlan, *, approved_digest: str, confirm: bool
) -> str:
    """Review and persist this finite background capability; perform no request."""
    plan = CeqanetBackgroundPlan.model_validate(plan.model_dump(mode="json", round_trip=True))
    if approved_digest != plan.digest:
        raise ValueError("reviewed background plan digest does not match")
    now = _now()
    if not plan.windows[0].due_at - timedelta(days=1) <= now < plan.expires_at:
        raise ValueError("background plan is expired or too far in the future")
    plan.current_evidence()
    root = directory / "ceqa-background"
    with _serialized_bundle_output(root):
        if (root / "active.json").exists():
            active = _active_plan(root)
            if active.digest != plan.digest and not _flagged(root, f"revoked-{active.digest}.json"):
                raise ValueError("revoke the previous background plan before replacing it")
        if _flagged(root, f"revoked-{plan.digest}.json") or _flagged(
            root, f"stopped-{plan.digest}.json"
        ):
            raise ValueError("revoked or stopped background plan requires a new review scope")
        for window in plan.windows:
            if (root / f"attempt-{window.manifest.manifest_digest}.json").exists():
                raise ValueError("a background window was already reserved; review a new window")
        authorization = authorize_local_operator_operation(
            action=ACTION,
            resource_type="ceqanet-background-plan",
            resource_id=plan.digest,
            exact_scope=(
                f"plan:{plan.digest}",
                "mode:background",
                "policy:CS-NET-002",
                "attempts-per-window:1",
                "pages-per-window:1",
                f"expires:{plan.expires_at.isoformat()}",
            ),
            current_state_identity=plan.digest,
            expected_identity=approved_digest,
            granted_authority=(
                "execute these exact finite background listing windows "
                "and retain/process their evidence",
            ),
            denied_authority=(
                "unbounded recurrence",
                "automatic network retry",
                "access-control bypass",
                "credential use",
                "document download",
                "project identity verification",
                "source promotion",
            ),
            reason="Operator reviewed the exact finite CEQAnet background plan.",
            caller_confirmation=confirm,
            limitations=(
                "local operator identity is not authentication",
                "ambiguous attempts require review and are never retried",
                "listing results remain partial source claims",
            ),
        )

        def persist(_trusted_at: object) -> dict[str, Any]:
            receipt = {
                "plan": plan.model_dump(mode="json", round_trip=True),
                "authorization": authorization.to_dict(),
                "enabled_at": now.isoformat(),
                "data_directory": str(directory.absolute()),
            }
            _publish(root / f"approved-{plan.digest}.json", receipt)
            _publish(_authority_root(root) / f"approved-{plan.digest}.json", receipt)
            return receipt

        receipt = _execute_owned_effect(
            authorization,
            allowance_identity=f"ceqanet-background-enable:{plan.digest}",
            content_identity=plan.digest,
            implementation_id="constructionsight.ceqanet_background.enable_plan",
            replay_policy=EffectReplayPolicy.EXACT,
            effect=persist,
            encode_result=lambda value: value,
            decode_result=lambda value: value,
        )
        if receipt.get("data_directory") != str(directory.absolute()):
            raise ValueError("background approval belongs to a different data directory")
        write_runtime_text(root / "active.json", _bytes(receipt).decode())
    return plan.digest


def revoke_plan(directory: Path) -> str:
    """Revoke future requests; retained observations and jobs remain available."""
    root = directory / "ceqa-background"
    with _serialized_bundle_output(root):
        plan = _active_plan(root)
        _flag(
            root,
            f"revoked-{plan.digest}.json",
            {"plan_digest": plan.digest, "revoked_at": _now().isoformat()},
        )
        return plan.digest


def _active_plan(root: Path) -> CeqanetBackgroundPlan:
    receipt = _read(root / "active.json")
    if (
        not isinstance(receipt, dict)
        or "plan" not in receipt
        or not isinstance(receipt.get("authorization"), dict)
    ):
        raise ValueError("background approval receipt is malformed")
    plan = CeqanetBackgroundPlan.model_validate(receipt["plan"])
    if receipt.get("data_directory") != str(root.parent.absolute()):
        raise ValueError("background approval belongs to a different data directory")
    authorization = receipt["authorization"]
    if authorization.get("action") != ACTION or authorization.get("resource_id") != plan.digest:
        raise ValueError("background approval does not bind to this plan")
    if (
        _read(root / f"approved-{plan.digest}.json") != receipt
        or _read(_authority_root(root) / f"approved-{plan.digest}.json") != receipt
    ):
        raise ValueError("background approval receipt changed")
    return plan


class BackgroundListingEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["ceqanet_background_evidence.v1"] = "ceqanet_background_evidence.v1"
    plan_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    captured_at: AwareDatetime
    definition: CeqanetRecurringRunDefinition
    manifest: CeqanetRecurringRunManifest
    execution: CeqanetRecurringRunExecution

    @model_validator(mode="after")
    def validate_execution(self) -> BackgroundListingEvidence:
        self.execution.assert_integrity()
        verification = verify_ceqanet_recurring_run_execution(
            self.definition, self.manifest, self.execution
        )
        if not verification.passed:
            raise ValueError(
                "retained background execution failed verification: "
                + "; ".join(verification.findings)
            )
        metadata = self.execution.execution_report["metadata"]
        if metadata.get("allowed") is not True:
            raise ValueError("retained background listing was not allowed")
        for snapshot in self.execution.execution_report["snapshots"]:
            if (
                "error" not in snapshot
                or "failure_kind" not in snapshot
                or "status_code" not in snapshot
            ):
                raise ValueError("retained background response classification is missing")
            status = snapshot["status_code"]
            if status is not None and (type(status) is not int or not 100 <= status <= 599):
                raise ValueError("retained response status is invalid")
        return self

    def response_failed(self) -> bool:
        snapshots = self.execution.execution_report["snapshots"]
        return len(snapshots) != 1 or any(
            s["error"]
            or s["failure_kind"] != "none"
            or s["body_truncated"]
            or not 200 <= (s["status_code"] or 0) < 300
            or any(
                SourceVerifier._detect_access_flags(
                    s["body_text"].lower(), s["status_code"] or 0
                ).values()
            )
            for s in snapshots
        )

    def normalized_records(self) -> list[dict[str, Any]]:
        if self.response_failed():
            return []
        rows: list[dict[str, Any]] = []
        for snapshot in self.execution.execution_report["snapshots"]:
            if (
                snapshot["error"]
                or snapshot["failure_kind"] != "none"
                or snapshot["body_truncated"]
                or not 200 <= (snapshot["status_code"] or 0) < 300
            ):
                continue
            parsed = parse_ceqanet_result_page(
                snapshot["body_text"], source_url=snapshot["request_url"]
            )
            if parsed.record_count > self.definition.query_template.page_size:
                raise ValueError("parsed listing exceeds the reviewed record bound")
            rows.extend(
                {**row.to_dict(), "raw_result_text": row.raw_text} for row in parsed.records
            )
        records = []
        for row in rows:
            preview = build_ceqanet_persistence_preview({"enrichment": {"records": [row]}})
            if not preview.ceqa_records:
                continue
            record = preview.ceqa_records[0]
            row_digest = canonical_digest(
                {key: value for key, value in row.items() if key != "source_url"}
            )
            key = f"ceqa:ceqanet:listing:{record.state_clearinghouse_number}:{row_digest[:24]}"
            # Stable capture time makes offline replay identical. No filter value
            # is substituted for a missing observed county, address or identity.
            provenance = [
                p.model_copy(
                    update={
                        "captured_at": self.captured_at,
                        "notes": (
                            "Partial CEQAnet listing source claim; detail, identity, "
                            "activity and completeness unverified."
                        ),
                    }
                )
                for p in record.provenance
            ]
            records.append(
                record.model_copy(update={"ceqa_key": key, "provenance": provenance}).model_dump(
                    mode="json", round_trip=True
                )
            )
        return records


def _execute_window(
    root: Path,
    plan: CeqanetBackgroundPlan,
    window: BackgroundWindow,
    sources: list[PublicSource],
    checklist: SourceVerificationChecklistReport,
) -> BackgroundListingEvidence:
    """Derive worker authority only from the separately approved finite plan."""
    receipt = _read(root / "active.json")
    now = _now()
    identity = window.manifest.manifest_digest
    action = "execute-approved-ceqanet-background-window"
    actor = "ceqanet-background-worker"
    state = canonical_digest({"plan": plan.digest, "manifest": identity})
    scope = tuple(
        sorted(
            (
                f"plan:{plan.digest}",
                f"manifest:{identity}",
                "mode:background",
                "attempts:1",
                "policy:CS-NET-002",
            ),
            key=str.casefold,
        )
    )
    # This is delegated worker authority, not a new foreground confirmation.
    # The retained activation decision and exact current scope are its parent.
    decision = build_authorization_decision(
        actor_id=actor,
        action=action,
        resource_type="ceqanet-background-window",
        resource_id=identity,
        exact_scope=scope,
        current_state_identity=state,
        expected_identity=state,
        granted_authority=("execute one window in the reviewed finite background plan",),
        denied_authority=("access bypass", "automatic network retry", "manual allowance reuse"),
        reason="Execute a due window in the separately reviewed background plan.",
        issued_at=now,
        not_before=now,
        expires_at=min(plan.expires_at, now + timedelta(minutes=5)),
        reuse_policy=AuthorizationReusePolicy.SINGLE_USE,
        revocation_identity=state,
        audit_identity=canonical_digest(
            {"parent": receipt["authorization"]["decision_id"], "state": state}
        ),
        caller_confirmation=True,
        limitations=(
            "authority derives from a retained finite plan approval",
            "local identity is not authentication",
        ),
    )
    preflight = validate_authorization_decision(
        decision,
        actor_id=actor,
        action=action,
        resource_type="ceqanet-background-window",
        resource_id=identity,
        exact_scope=scope,
        current_state_identity=state,
        current_revocation_identity=state,
        checked_at=now,
    )

    def acquire(_trusted_at: object) -> BackgroundListingEvidence:
        execution = execute_ceqanet_recurring_run(
            plan.definition,
            window.manifest,
            sources,
            checklist,
            attempt_sequence=1,
            execute_live=True,
        )
        retained = {
            "schema_version": "ceqanet_background_evidence.v1",
            "plan_digest": plan.digest,
            "captured_at": _now().isoformat(),
            "definition": plan.definition.model_dump(mode="json", round_trip=True),
            "manifest": window.manifest.model_dump(mode="json", round_trip=True),
            "execution": execution.model_dump(mode="json", round_trip=True),
        }
        _flag(root, f"result-{identity}.json", retained)
        return BackgroundListingEvidence.model_validate(retained)

    return _execute_owned_effect(
        LocalAuthorizationResult(decision, preflight),
        allowance_identity=f"ceqanet-background-window:{identity}",
        content_identity=state,
        implementation_id="constructionsight.ceqanet_background.acquire_window",
        replay_policy=EffectReplayPolicy.EXACT,
        effect=acquire,
        encode_result=lambda evidence: evidence.model_dump(mode="json", round_trip=True),
        decode_result=lambda payload: BackgroundListingEvidence.model_validate(payload),
    )


def poll_background(runtime: InvestigationRuntime) -> dict[str, int]:
    """Run at most one due window and recover retained handoffs without refetching."""
    root = runtime.directory / "ceqa-background"
    if not (root / "active.json").exists():
        return {"ceqa_acquired": 0, "ceqa_failed": 0}
    # Same pinned cross-process lock guards activation, revocation and collection.
    # Acquisition is deliberately independent of SQLite knowledge transactions.
    with _serialized_bundle_output(root):
        plan = _active_plan(root)
        revoked = _flagged(root, f"revoked-{plan.digest}.json")
        stop_name = f"stopped-{plan.digest}.json"
        now = _now()
        last_capture: datetime | None = None
        for window in plan.windows:
            identity = window.manifest.manifest_digest
            for name in (f"result-{identity}.json", f"attempt-{identity}.json"):
                protected = _authority_root(root) / name
                if protected.exists():
                    content = read_runtime_artifact(protected, max_bytes=MAX_BYTES)
                    local = root / name
                    if not local.exists():
                        publish_runtime_artifact(local, [content], max_bytes=MAX_BYTES)
                    elif read_runtime_artifact(local, max_bytes=MAX_BYTES) != content:
                        raise ValueError("background receipt differs from its protected identity")
            result_path = root / f"result-{identity}.json"
            handed_off = root / f"handed-off-{identity}.json"
            if result_path.exists():
                prior = BackgroundListingEvidence.model_validate(_read(result_path))
                last_capture = (
                    max(last_capture, prior.captured_at) if last_capture else prior.captured_at
                )
            if result_path.exists() and not handed_off.exists():
                # This step is offline and remains useful after expiry/revocation.
                content = read_runtime_artifact(result_path, max_bytes=MAX_BYTES)
                evidence = BackgroundListingEvidence.model_validate_json(content)
                if (
                    evidence.manifest.manifest_digest != identity
                    or evidence.plan_digest != plan.digest
                ):
                    raise ValueError("retained background result is bound to another plan/window")
                if evidence.response_failed():
                    _flag(
                        root,
                        stop_name,
                        {
                            "plan_digest": plan.digest,
                            "error_code": "retained_access_or_response_failure",
                        },
                    )
                records = evidence.normalized_records()
                if records:
                    job = runtime.enqueue_bytes(content, "ceqa-listing-execution")
                    job_id: str | None = job.job_id
                else:
                    job_id = None
                _publish(
                    handed_off,
                    {"job_id": job_id, "record_count": len(records), "completeness": "partial"},
                )
        for window in plan.windows:
            identity = window.manifest.manifest_digest
            reservation = root / f"attempt-{identity}.json"
            if (
                reservation.exists()
                and _read(reservation).get("status") == "reserved"
                and not (root / f"result-{identity}.json").exists()
                and not _flagged(root, stop_name)
            ):
                _flag(
                    root,
                    stop_name,
                    {
                        "plan_digest": plan.digest,
                        "error_code": "ambiguous_attempt_requires_review",
                    },
                )
        if revoked or _flagged(root, stop_name) or now >= plan.expires_at:
            return {"ceqa_acquired": 0, "ceqa_failed": int(_flagged(root, stop_name))}
        if last_capture is not None and now < last_capture + timedelta(days=1):
            return {"ceqa_acquired": 0, "ceqa_failed": 0}
        try:
            sources, checklist = plan.current_evidence()
            for window in plan.windows:
                identity = window.manifest.manifest_digest
                reservation = root / f"attempt-{identity}.json"
                if now < window.due_at or reservation.exists():
                    continue
                if now >= window.due_at + timedelta(days=1):
                    # Do not produce a burst of stale catch-up network requests.
                    _flag(root, reservation.name, {"status": "missed", "plan_digest": plan.digest})
                    continue
                _flag(
                    root,
                    reservation.name,
                    {
                        "status": "reserved",
                        "plan_digest": plan.digest,
                        "started_at": now.isoformat(),
                    },
                )
                evidence = _execute_window(root, plan, window, sources, checklist)
                result_path = root / f"result-{identity}.json"
                if not result_path.exists():
                    _publish(result_path, evidence.model_dump(mode="json", round_trip=True))
                if evidence.response_failed():
                    raise ValueError("CEQAnet response was incomplete or access was denied")
                # Next poll can recover this handoff if the process exits here.
                content = read_runtime_artifact(result_path, max_bytes=MAX_BYTES)
                records = evidence.normalized_records()
                handoff = (
                    runtime.enqueue_bytes(content, "ceqa-listing-execution") if records else None
                )
                _publish(
                    root / f"handed-off-{identity}.json",
                    {
                        "job_id": handoff.job_id if handoff else None,
                        "record_count": len(records),
                        "completeness": "partial",
                    },
                )
                return {"ceqa_acquired": 1, "ceqa_failed": 0}
        except (ValueError, OSError, EffectConsumptionError) as exc:
            if not _flagged(root, stop_name):
                _flag(
                    root,
                    stop_name,
                    {
                        "plan_digest": plan.digest,
                        "error_code": type(exc).__name__,
                        "stopped_at": _now().isoformat(),
                    },
                )
            return {"ceqa_acquired": 0, "ceqa_failed": 1}
    return {"ceqa_acquired": 0, "ceqa_failed": 0}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True, type=Path)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("preview", "enable"):
        command = commands.add_parser(name)
        command.add_argument("--plan", required=True, type=Path)
        if name == "enable":
            command.add_argument("--approved-digest", required=True)
            command.add_argument("--confirm-background", action="store_true")
    build = commands.add_parser("build")
    build.add_argument("--definition", required=True, type=Path)
    build.add_argument("--registry", required=True, type=Path)
    build.add_argument("--checklist", required=True, type=Path)
    build.add_argument("--first-due", required=True, type=datetime.fromisoformat)
    build.add_argument("--days", required=True, type=int)
    commands.add_parser("revoke")
    args = parser.parse_args(argv)
    directory = data_folder.resolve_folder(args.data_dir.absolute())
    if args.command == "build":
        plan = build_background_plan(
            CeqanetRecurringRunDefinition.model_validate(_read(args.definition)),
            registry_path=args.registry,
            checklist_path=args.checklist,
            first_due=args.first_due,
            days=args.days,
        )
        print(plan.model_dump_json(indent=2, round_trip=True))
    elif args.command == "revoke":
        print(json.dumps({"revoked": revoke_plan(directory)}))
    else:
        plan = CeqanetBackgroundPlan.model_validate(_read(args.plan))
        plan.current_evidence()
        if args.command == "enable":
            enable_plan(
                directory,
                plan,
                approved_digest=args.approved_digest,
                confirm=args.confirm_background,
            )
        print(
            json.dumps(
                {
                    "plan_digest": plan.digest,
                    "request_limit": len(plan.windows),
                    "expires_at": plan.expires_at.isoformat(),
                    "mode": "background",
                    "network_executed": False,
                }
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
