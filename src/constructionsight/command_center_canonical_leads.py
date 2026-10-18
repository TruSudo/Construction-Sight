"""Phase 8: feed exact canonical evidence through existing lead-review rules.

A preview neither persists a lead nor authorizes outreach, pricing or bids.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from constructionsight.command_center_investigations import investigation_view
from constructionsight.command_center_legacy_events import (
    verified_original_workflow_events,
)
from constructionsight.intake_models import (
    DigitalFormatFamily,
    ExtractedMaterialFact,
    FactConfidence,
    FormatDetection,
    IntakeEvidenceRef,
    IntakeRouting,
    IntakeUnderstandingStatus,
    MaterialFactKind,
    UniversalIntakeRecord,
)
from constructionsight.lead_dedupe_models import LeadFingerprint
from constructionsight.lead_dedupe_service import (
    build_lead_fingerprint,
    check_lead_duplicate,
)
from constructionsight.lead_operator_service import load_persisted_lead_workflow
from constructionsight.lead_workflow_service import create_lead_workflow
from constructionsight.product_integration_models import ProductIntegrationReport
from constructionsight.product_integration_service import (
    build_product_integration,
    persist_product_integration,
)
from constructionsight.storage.database import (
    create_private_database_engine,
    managed_session,
    prepare_private_database,
    session_factory,
)
from constructionsight.storage.lead_workflow_orm import (
    LeadFingerprintRecord,
    LeadWorkflowRecordRow,
)
from constructionsight.storage.operator_read_store import create_operator_read_engine

_ARTIFACT_FACTS = {
    "apn": MaterialFactKind.APN,
    "exact_site_address": MaterialFactKind.ADDRESS,
    "ceqa_sch_number": MaterialFactKind.SCH_NUMBER,
    "permit_number": MaterialFactKind.PERMIT_NUMBER,
}


def canonical_lead_preview(directory: Path, investigation_id: str) -> dict[str, Any]:
    """Review one current source anchor, never guessed cross-source project facts."""
    if not isinstance(investigation_id, str) or not 1 <= len(investigation_id) <= 255:
        raise ValueError("one exact canonical investigation required")
    dossier = investigation_view(directory, investigation_id=investigation_id)
    if dossier["investigation"]["project_cluster_id"] != investigation_id:
        raise ValueError("investigation identity changed; reopen the current dossier")
    if dossier["pending_association_reviews"] or any(dossier.get(key) for key in (
        "sources_truncated", "evidence_truncated", "relationships_truncated",
        "parties_truncated", "candidate_links_truncated",
    )):
        raise ValueError("investigation has unresolved or truncated source context")
    anchors = [
        m for m in dossier["source_membership"] if m["membership_basis"] == "source_anchor"
    ]
    if len(anchors) != 1:
        raise ValueError("source anchor absent or ambiguous; source review required")
    anchor = anchors[0]
    current = [
        value for value in dossier["source_observations"]
        if value["evidence"]["evidence_id"] == anchor["current_evidence_id"]
        and value["evidence"]["source_record_id"] == anchor["source_record_id"]
        and value["evidence"]["source_family"] == anchor["source_family"]
    ]
    if len(current) != 1:
        raise ValueError("current source evidence no longer matches the canonical anchor")
    record = current[0]
    evidence = record["evidence"]
    digest = evidence.get("content_hash")
    if not isinstance(digest, str) or len(digest) != 64:
        raise ValueError("original evidence has no exact retained integrity digest")
    artifacts = record.get("artifacts", {})
    if not isinstance(artifacts, dict):
        raise ValueError("source artifacts require review")
    facts: list[ExtractedMaterialFact] = []
    title = record.get("title")
    if isinstance(title, str) and title.strip():
        facts.append(ExtractedMaterialFact(
            fact_id="source-title:" + digest,
            fact_kind=MaterialFactKind.PROJECT_TITLE,
            value=title, evidence_id=evidence["evidence_id"],
            confidence=FactConfidence.SOURCE_CLAIMED, source_field="title",
        ))
    for key, kind in _ARTIFACT_FACTS.items():
        values = artifacts.get(key, [])
        if not isinstance(values, list) or len(values) > 1 or any(
            not isinstance(v, str) or not v.strip() for v in values
        ):
            raise ValueError("ambiguous source artifacts must be reviewed")
        for value in values:
            facts.append(ExtractedMaterialFact(
                fact_id=f"source-{key}:" + digest, fact_kind=kind,
                value=value, evidence_id=evidence["evidence_id"],
                confidence=FactConfidence.SOURCE_CLAIMED, source_field=key,
                context="source claim; not independently confirmed",
            ))
    if not facts:
        raise ValueError("no current source facts for original lead assessment")
    normalized = json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
    hints = {
        kind.value: artifacts[key][0]
        for key, kind in (
            ("ceqa_sch_number", MaterialFactKind.SCH_NUMBER),
            ("permit_number", MaterialFactKind.PERMIT_NUMBER),
        ) if artifacts.get(key)
    }
    intake = UniversalIntakeRecord(
        intake_id="canonical-intake:" + digest,
        evidence=IntakeEvidenceRef(
            evidence_id=evidence["evidence_id"],
            source_name=evidence["source_name"],
            source_family=evidence["source_family"],
            source_url=evidence.get("source_url"),
            observed_at=evidence["observed_at"] or evidence["retrieved_at"],
            byte_count=len(normalized), sha256=digest,
            access_method="retained_normalized_projection",
            lawful_basis="already_retained_public_source_evidence",
            limitations=[
                "Projection byte count is not original source byte length.",
                "Source content integrity does not verify site identity or contact authority.",
            ],
        ),
        format_detection=FormatDetection(format_family=DigitalFormatFamily.JSON),
        understanding_status=IntakeUnderstandingStatus.STRUCTURED,
        routing=IntakeRouting.HUMAN_REVIEW,
        extracted_facts=facts, record_hints=hints,
        source_hints={
            "canonical_investigation_id": investigation_id,
            "source_entity_id": anchor["source_id"],
            "source_record_id": anchor["source_record_id"],
        },
        next_action="Independent operator review required before any commerce.",
    )
    report = build_product_integration(intake)
    if report.workflow.status.value not in {"hold", "monitor", "review"}:
        raise ValueError("source claims cannot enter an actionable workflow")
    existing = existing_canonical_handoff(directory, investigation_id)
    return {
        "schema_version": "constructionsight.canonical-lead-review/v1",
        "existing_native_handoff": existing,
        "canonical_investigation_id": investigation_id,
        "source_entity_id": anchor["source_id"],
        "current_evidence_id": evidence["evidence_id"],
        "current_evidence_sha256": digest,
        "source_record_id": anchor["source_record_id"],
        "event_anchor": dossier["event_anchor"],
        "original_product_integration": report.model_dump(mode="json"),
        "lead_review_status": report.review_package.status.value,
        "provisional_workflow_status": report.workflow.status.value,
        "persisted": False,
        "dedupe_against_persisted_leads_complete": False,
        "commercial_authority_granted": False,
        "outreach_authorized": False,
        "bid_authorized": False,
        "limitations": [
            "Read-only original pipeline assessment, not a qualified commercial lead.",
            "Persisted lead duplicates and authority remain subject to operator review.",
        ],
    }


def existing_canonical_handoff(
    directory: Path, investigation_id: str,
) -> dict[str, Any] | None:
    """Read the original persisted workflow link; canonical identity never guesses by title."""
    database = prepare_private_database(
        directory / "investigations.sqlite3", create=False,
    )
    engine = create_operator_read_engine(database)
    try:
        with Session(engine, autoflush=False) as session:
            fingerprints = session.scalars(
                select(LeadFingerprintRecord).where(
                    LeadFingerprintRecord.source_key == "canonical_investigation",
                    LeadFingerprintRecord.source_record_id == investigation_id,
                ).limit(2)
            ).all()
            if len(fingerprints) > 1:
                raise ValueError("conflicting canonical lead handoffs require review")
            if not fingerprints:
                return None
            workflow = session.scalars(
                select(LeadWorkflowRecordRow).where(
                    LeadWorkflowRecordRow.fingerprint_key
                    == fingerprints[0].fingerprint_key
                ).limit(2)
            ).all()
            if len(workflow) != 1:
                raise ValueError("canonical lead fingerprint/workflow lineage is incomplete")
            return {
                "workflow_id": workflow[0].workflow_id,
                "workflow_status": workflow[0].status,
                "fingerprint_key": fingerprints[0].fingerprint_key,
                "source_claim_only": True,
                "commercial_authority_granted": False,
            }
    finally:
        engine.dispose()


def retain_reviewed_canonical_candidate(
    directory: Path, payload: dict[str, Any],
) -> dict[str, Any]:
    """Persist the original governed lead stages atomically after explicit review.

    A SQLite IMMEDIATE transaction serializes checks against concurrent original
    worker updates and other operators. Neither source history nor commercial
    authority is mutated.
    """
    if set(payload) != {
        "investigation_id", "expected_evidence_id", "expected_evidence_sha256",
        "expected_event_anchor", "reason", "caller_confirmation",
    }:
        raise ValueError("exact canonical lead review fields required")
    identity = payload["investigation_id"]
    reason = payload["reason"]
    if (
        not isinstance(identity, str) or not 1 <= len(identity) <= 255
        or not isinstance(reason, str) or not 1 <= len(reason.strip()) <= 2000
        or payload["caller_confirmation"] is not True
        or not isinstance(payload["expected_evidence_id"], str)
        or not isinstance(payload["expected_evidence_sha256"], str)
        or not isinstance(payload["expected_event_anchor"], str)
    ):
        raise ValueError("explicit review, exact identity and evidence receipt required")
    engine = create_private_database_engine(
        directory / "investigations.sqlite3", create=False,
    )
    try:
        with managed_session(session_factory(engine)) as session:
            # The worker and every duplicate reviewer share this single private
            # DB, so lock it before inspecting the current retained evidence.
            session.connection().exec_driver_sql("BEGIN IMMEDIATE")
            reviewed = canonical_lead_preview(directory, identity)
            if (
                reviewed["current_evidence_id"] != payload["expected_evidence_id"]
                or reviewed["current_evidence_sha256"]
                != payload["expected_evidence_sha256"]
                or reviewed["event_anchor"] != payload["expected_event_anchor"]
            ):
                raise ValueError("evidence changed; repeat canonical lead review")
            if reviewed["existing_native_handoff"] is not None:
                raise ValueError("canonical investigation already has a retained lead handoff")
            rows = session.scalars(select(LeadFingerprintRecord).limit(5001)).all()
            if len(rows) > 5000:
                raise ValueError("persisted duplicate scan exceeds review bound")
            existing = [
                LeadFingerprint.model_validate(json.loads(row.payload_json))
                for row in rows
            ]
            product = ProductIntegrationReport.model_validate(
                reviewed["original_product_integration"]
            )
            # A stable canonical identity survives a source/title revision.
            # Same-site evidence still invokes the original REVIEW_NEEDED dedupe.
            fingerprint = build_lead_fingerprint(
                package=product.review_package,
                site_key=product.site_resolution.primary_site_key,
                source_key="canonical_investigation",
                source_record_id=identity,
            )
            duplicate = check_lead_duplicate(fingerprint, existing)
            workflow = create_lead_workflow(
                package=product.review_package, duplicate_result=duplicate,
            ).model_copy(update={"notes": [
                "Canonical investigation: " + identity,
                "Operator retained candidate for human review: " + reason.strip(),
                "Original source evidence: " + reviewed["current_evidence_id"],
            ]})
            if workflow.status.value not in {"hold", "monitor", "review"}:
                raise ValueError("unverified claims cannot be promoted to actionable lead")
            retained = ProductIntegrationReport.model_validate(
                product.model_copy(update={
                    "fingerprint": fingerprint,
                    "duplicate_result": duplicate,
                    "workflow": workflow,
                }).model_dump(mode="json")
            )
            persist_product_integration(session, retained)
            result: dict[str, Any] = {
                "schema_version": "constructionsight.canonical-lead-retention/v1",
                "canonical_investigation_id": identity,
                "source_entity_id": reviewed["source_entity_id"],
                "source_evidence_id": reviewed["current_evidence_id"],
                "workflow_id": retained.workflow.workflow_id,
                "workflow_status": retained.workflow.status.value,
                "duplicate_status": duplicate.status.value,
                "lead_review_status": retained.review_package.status.value,
                "persisted": True,
                "human_review_required": True,
                "outreach_authorized": False,
                "bid_authorized": False,
                "commercial_authority_granted": False,
                "source_claim_only": True,
            }
        return result
    except SQLAlchemyError as exc:
        raise ValueError("canonical review workflow could not be committed") from exc
    finally:
        engine.dispose()


def retained_canonical_lead_workflows(
    directory: Path, *, limit: int = 25, offset: int = 0,
) -> dict[str, Any]:
    """Read existing governed lead records into the native console, without copying them.

    Pagination is over durable canonical-source fingerprints, not a second lead
    inventory. Current source evidence is rechecked separately; stale or missing
    sources cannot silently look ready to the operator.
    """
    if type(limit) is not int or not 1 <= limit <= 50:
        raise ValueError("canonical lead page limit must be between 1 and 50")
    if type(offset) is not int or not 0 <= offset <= 10000:
        raise ValueError("canonical lead page offset is invalid")
    database_path = directory / "investigations.sqlite3"
    if not database_path.exists() and not database_path.is_symlink():
        # No worker run has established this store. Never initialize or claim
        # that zero leads were scanned; do not emit an expected HTTP 409 either.
        return {
            "schema_version": "constructionsight.canonical-lead-console/v1",
            "available": False,
            "rows": [],
            "total": None,
            "limit": limit,
            "offset": offset,
            "has_more": False,
            "read_only": True,
            "source_claim_only": True,
            "commercial_authority_granted": False,
        }
    database = prepare_private_database(database_path, create=False)
    engine = create_operator_read_engine(database)
    try:
        with Session(engine, autoflush=False) as session:
            predicate = LeadFingerprintRecord.source_key == "canonical_investigation"
            total = session.scalar(
                select(func.count()).select_from(LeadFingerprintRecord).where(predicate)
            ) or 0
            fingerprints = session.scalars(
                select(LeadFingerprintRecord)
                .where(predicate)
                .order_by(LeadFingerprintRecord.id)
                .offset(offset).limit(limit)
            ).all()
            rows: list[dict[str, Any]] = []
            for fingerprint in fingerprints:
                identity = fingerprint.source_record_id
                if not identity:
                    raise ValueError("canonical lead fingerprint has no investigation ID")
                # Detect ambiguous duplicate canonical handoffs, including on other pages.
                repeated = session.scalars(
                    select(LeadFingerprintRecord.fingerprint_key).where(
                        predicate,
                        LeadFingerprintRecord.source_record_id == identity,
                    ).limit(2)
                ).all()
                if len(repeated) != 1:
                    raise ValueError("multiple workflows claim the same canonical investigation")
                persisted = session.scalars(
                    select(LeadWorkflowRecordRow.workflow_id).where(
                        LeadWorkflowRecordRow.fingerprint_key
                        == fingerprint.fingerprint_key
                    ).limit(2)
                ).all()
                if len(persisted) != 1:
                    raise ValueError("canonical lead workflow linkage is incomplete")
                workflow = load_persisted_lead_workflow(session, persisted[0])
                history = verified_original_workflow_events(session, workflow)
                notes = [
                    note.removeprefix("Original source evidence: ")
                    for note in workflow.notes
                    if note.startswith("Original source evidence: ")
                ]
                if (
                    workflow.fingerprint_key != fingerprint.fingerprint_key
                    or len(notes) != 1 or not notes[0]
                    or "Canonical investigation: " + identity not in workflow.notes
                ):
                    raise ValueError("retained lead source provenance is inconsistent")
                current_evidence_id: str | None = None
                current_state = "unavailable_needs_source_review"
                title: str | None = None
                try:
                    dossier = investigation_view(directory, investigation_id=identity)
                    project = dossier["investigation"]
                    if project["project_cluster_id"] != identity:
                        raise ValueError("canonical investigation identity moved")
                    title = project["project_name"]
                    anchors = [
                        m for m in dossier["source_membership"]
                        if m["membership_basis"] == "source_anchor"
                    ]
                    if not dossier["sources_truncated"] and len(anchors) == 1:
                        current_evidence_id = anchors[0]["current_evidence_id"]
                        current_state = (
                            "current_source_observation"
                            if current_evidence_id == notes[0]
                            else "source_revision_requires_review"
                        )
                except (ValueError, OSError, RuntimeError):
                    pass  # Failure stays visibly unreviewed; no commercial readiness inferred.
                rows.append({
                    "canonical_investigation_id": identity,
                    "title": title,
                    "workflow_id": workflow.workflow_id,
                    "workflow_status": workflow.status.value,
                    "lead_score": workflow.lead_score,
                    "original_source_evidence_id": notes[0],
                    "current_source_evidence_id": current_evidence_id,
                    "source_evidence_state": current_state,
                    "source_claim_only": True,
                    "commercial_authority_granted": False,
                    "outreach_authorized": False,
                    "bid_authorized": False,
                    "transition_count": history["event_count"],
                    "recent_transitions": history["transitions"][-10:],
                    "transitions_truncated": history["event_count"] > 10,
                    "history_integrity_validated": history["history_integrity_validated"],
                    "limitations": workflow.limitations,
                })
            return {
                "schema_version": "constructionsight.canonical-lead-console/v1",
                "available": True,
                "rows": rows,
                "total": total,
                "limit": limit,
                "offset": offset,
                "has_more": offset + len(rows) < total,
                "read_only": True,
                "source_claim_only": True,
                "commercial_authority_granted": False,
            }
    finally:
        engine.dispose()
