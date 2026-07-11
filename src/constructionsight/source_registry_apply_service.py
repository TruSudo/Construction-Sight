"""Controlled source registry apply service."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from constructionsight.models import PublicSource, VerificationStatus
from constructionsight.source_registry_apply_models import (
    SourceRegistryApplyReport,
    SourceRegistryApplyRow,
)
from constructionsight.source_registry_update_plan_models import (
    SourceRegistryUpdatePlanReport,
    SourceRegistryUpdatePlanRow,
    compute_source_registry_update_plan_digest,
)
from constructionsight.source_registry_update_plan_service import source_registry_key

_ACTION_STATUS = {
    "mark_blocked_candidate": VerificationStatus.BLOCKED,
    "mark_failed_candidate": VerificationStatus.FAILED,
    "mark_partial_candidate": VerificationStatus.PARTIAL,
    "verified_candidate_review": VerificationStatus.VERIFIED,
}
_DRY_RUN_LIMITATIONS = {
    "dry-run only; source registry file is not modified",
    "this is a dry-run plan and does not mutate registry data",
}


class SourceRegistryApplyError(ValueError):
    """Raised when a source registry plan cannot be safely applied."""


def apply_source_registry_update_plan(
    sources: list[PublicSource],
    plan: SourceRegistryUpdatePlanReport,
    *,
    approved_plan_digest: str,
) -> tuple[list[PublicSource], SourceRegistryApplyReport]:
    """Apply an approved, current, evidence-backed plan in memory as one transaction."""

    _validate_plan(plan, approved_plan_digest=approved_plan_digest)
    if plan.update_count == 0:
        raise SourceRegistryApplyError("source registry update plan proposes no changes")

    source_index = _source_index(sources)
    updates: dict[str, PublicSource] = {}
    audit_rows: list[SourceRegistryApplyRow] = []

    for row in plan.rows:
        source = source_index.get(row.source_key)
        if source is None:
            raise SourceRegistryApplyError(
                f"plan source key is absent from current registry: {row.source_key}"
            )
        if row.update_required:
            updated_source = _validated_update(source, row)
            updates[row.source_key] = updated_source
            resulting_status = updated_source.verification_status.value
        else:
            resulting_status = source.verification_status.value
        audit_rows.append(
            SourceRegistryApplyRow(
                source_key=row.source_key,
                source_name=row.source_name,
                planned_action=row.planned_action,
                previous_verification_status=source.verification_status.value,
                resulting_verification_status=resulting_status,
                applied=row.update_required,
                reasons=row.reasons,
                limitations=_apply_limitations(row, applied=row.update_required),
                evidence_refs=row.evidence_refs,
            )
        )

    updated_sources = [
        updates.get(source_registry_key(source), source)
        for source in sources
    ]
    original_digest = source_registry_digest(sources)
    updated_digest = source_registry_digest(updated_sources)
    report = SourceRegistryApplyReport.from_rows(
        plan_digest=plan.plan_digest,
        original_registry_digest=original_digest,
        updated_registry_digest=updated_digest,
        rows=audit_rows,
    )
    if report.applied_count != plan.update_count:
        raise SourceRegistryApplyError("validated apply count does not match plan update count")
    if not report.registry_changed:
        raise SourceRegistryApplyError("validated source updates did not change registry content")
    return updated_sources, report


def source_registry_digest(sources: list[PublicSource]) -> str:
    """Return a deterministic SHA-256 digest for registry content and order."""

    payload = [source.model_dump(mode="json") for source in sources]
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_plan(
    plan: SourceRegistryUpdatePlanReport,
    *,
    approved_plan_digest: str,
) -> None:
    if plan.source_count != len(plan.rows):
        raise SourceRegistryApplyError("plan source count does not match plan rows")
    actual_update_count = sum(1 for row in plan.rows if row.update_required)
    if plan.update_count != actual_update_count:
        raise SourceRegistryApplyError("plan update count does not match plan rows")
    calculated_digest = compute_source_registry_update_plan_digest(plan.rows)
    if plan.plan_digest != calculated_digest:
        raise SourceRegistryApplyError("plan digest does not match plan content")
    if approved_plan_digest != plan.plan_digest:
        raise SourceRegistryApplyError("approved plan digest does not match plan digest")
    plan_keys = [row.source_key for row in plan.rows]
    if len(plan_keys) != len(set(plan_keys)):
        raise SourceRegistryApplyError("plan contains duplicate source keys")


def _source_index(sources: list[PublicSource]) -> dict[str, PublicSource]:
    index: dict[str, PublicSource] = {}
    for source in sources:
        key = source_registry_key(source)
        if key in index:
            raise SourceRegistryApplyError(f"registry contains duplicate source key: {key}")
        index[key] = source
    return index


def _validated_update(
    source: PublicSource,
    row: SourceRegistryUpdatePlanRow,
) -> PublicSource:
    current_payload = source.model_dump(mode="json")
    if current_payload != row.original_source_payload:
        raise SourceRegistryApplyError(
            f"registry source changed after plan generation: {row.source_key}"
        )
    if row.current_verification_status != source.verification_status.value:
        raise SourceRegistryApplyError(
            f"plan current status is stale for source: {row.source_key}"
        )
    if not row.evidence_refs:
        raise SourceRegistryApplyError(
            f"registry status change requires evidence references: {row.source_key}"
        )
    if row.proposed_source_payload is None or row.proposed_verification_status is None:
        raise SourceRegistryApplyError(
            f"update row lacks a proposed source payload or status: {row.source_key}"
        )

    expected_status = _ACTION_STATUS.get(row.planned_action)
    if expected_status is None:
        raise SourceRegistryApplyError(
            f"planned action is not eligible for apply: {row.planned_action}"
        )
    if row.proposed_verification_status != expected_status.value:
        raise SourceRegistryApplyError(
            f"planned action and proposed status disagree for source: {row.source_key}"
        )
    if source.verification_status == VerificationStatus.VERIFIED:
        raise SourceRegistryApplyError(
            "verified source status cannot be changed by the promotion apply workflow; "
            f"separate revocation review is required: {row.source_key}"
        )

    changed_fields = _changed_fields(
        row.original_source_payload,
        row.proposed_source_payload,
    )
    if changed_fields != {"verification_status"}:
        changed = ", ".join(sorted(changed_fields)) or "none"
        raise SourceRegistryApplyError(
            "source registry apply may change only verification_status; "
            f"observed fields for {row.source_key}: {changed}"
        )
    if row.proposed_source_payload.get("verification_status") != expected_status.value:
        raise SourceRegistryApplyError(
            f"proposed source payload status is inconsistent for source: {row.source_key}"
        )

    updated_source = PublicSource.model_validate(row.proposed_source_payload)
    if source_registry_key(updated_source) != row.source_key:
        raise SourceRegistryApplyError(
            f"proposed source payload changes canonical source identity: {row.source_key}"
        )
    return updated_source


def _changed_fields(
    original: dict[str, Any],
    proposed: dict[str, Any],
) -> set[str]:
    return {
        key
        for key in original.keys() | proposed.keys()
        if original.get(key) != proposed.get(key)
    }


def _apply_limitations(
    row: SourceRegistryUpdatePlanRow,
    *,
    applied: bool,
) -> list[str]:
    limitations = [
        limitation
        for limitation in row.limitations
        if limitation not in _DRY_RUN_LIMITATIONS
    ]
    if applied:
        limitations.append(
            "registry status apply does not establish production-grade recurring source integration"
        )
    else:
        limitations.append(
            "plan row was not applied because no registry status change was proposed"
        )
    return _unique(limitations)


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique_values: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique_values.append(value)
    return unique_values
