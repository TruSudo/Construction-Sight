"""Phase 8: feed exact canonical evidence through existing lead-review rules.

A preview neither persists a lead nor authorizes outreach, pricing or bids.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from constructionsight.command_center_investigations import investigation_view
from constructionsight.command_center_legacy_events import (
    verified_original_workflow_events,
)
from constructionsight.command_center_legacy_lineage import _outcome_revision
from constructionsight.command_center_legacy_review import verified_original_review_package
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
from constructionsight.lead_workflow_models import LeadWorkflowStatus
from constructionsight.lead_workflow_rules import LEAD_WORKFLOW_TRANSITION_RULES
from constructionsight.lead_workflow_service import create_lead_workflow
from constructionsight.operator_results import (
    MAX_REVISIONS_PER_WORKFLOW,
    read_validated_result_history,
)
from constructionsight.operator_services.lead_workflow_transition_service import (
    apply_authorized_lead_workflow_transition,
)
from constructionsight.operator_services.result_authority_apply_service import (
    apply_authorized_authoritative_result,
)
from constructionsight.product_integration_models import ProductIntegrationReport
from constructionsight.product_integration_service import (
    build_product_integration,
    persist_product_integration,
)
from constructionsight.result_ledger_models import ResultLedgerStatus
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


def canonical_lead_preview(
    directory: Path, investigation_id: str, *,
    original_database: Path | None = None,
) -> dict[str, Any]:
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
    resolved_site_key = report.site_resolution.primary_site_key
    collisions = canonical_lead_collisions(
        directory, source_family=evidence["source_family"],
        source_record_id=anchor["source_record_id"],
        resolved_site_key=resolved_site_key,
        canonical_investigation_id=investigation_id,
        original_database=original_database,
    )
    return {
        "schema_version": "constructionsight.canonical-lead-review/v1",
        "existing_native_handoff": existing,
        "existing_source_or_site_matches": collisions,
        "can_retain_review_candidate": existing is None and not collisions["matches"],
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
    directory: Path, payload: dict[str, Any], *,
    original_database: Path | None = None,
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
            reviewed = canonical_lead_preview(
                directory, identity, original_database=original_database,
            )
            if (
                reviewed["current_evidence_id"] != payload["expected_evidence_id"]
                or reviewed["current_evidence_sha256"]
                != payload["expected_evidence_sha256"]
                or reviewed["event_anchor"] != payload["expected_event_anchor"]
            ):
                raise ValueError("evidence changed; repeat canonical lead review")
            if reviewed["existing_native_handoff"] is not None:
                raise ValueError("canonical investigation already has a retained lead handoff")
            # Query in the same locked writer transaction so another local
            # candidate cannot race the exact source/site comparison.
            source_identity = investigation_view(
                directory, investigation_id=identity,
            )["source_membership"]
            anchors = [m for m in source_identity if m["membership_basis"] == "source_anchor"]
            if len(anchors) != 1:
                raise ValueError("canonical source anchor changed; repeat lead review")
            current_product = ProductIntegrationReport.model_validate(
                reviewed["original_product_integration"]
            )
            local_matches = _fingerprint_matches(
                session, source_family=anchors[0]["source_family"],
                source_record_id=anchors[0]["source_record_id"],
                resolved_site_key=current_product.site_resolution.primary_site_key,
                exclude_canonical=identity, store_name="native",
            )
            if local_matches or reviewed["existing_source_or_site_matches"]["matches"]:
                raise ValueError(
                    "existing original or canonical lead matches exact source/site; "
                    "review and reconcile before creating another commercial candidate"
                )
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
            # SQLite's legacy driver does not begin a snapshot for SELECTs.
            # Keep workflow, review and every result/share revision in one read.
            session.connection().exec_driver_sql("BEGIN")
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
                retained_fingerprint = LeadFingerprint.model_validate_json(
                    fingerprint.payload_json
                )
                if (
                    retained_fingerprint.fingerprint_key != fingerprint.fingerprint_key
                    or retained_fingerprint.base_candidate_id != fingerprint.base_candidate_id
                    or retained_fingerprint.source_key != fingerprint.source_key
                    or retained_fingerprint.source_record_id != fingerprint.source_record_id
                    or retained_fingerprint.site_key != fingerprint.site_key
                    or retained_fingerprint.normalized_title != fingerprint.normalized_title
                    or retained_fingerprint.lead_score != fingerprint.lead_score
                    or retained_fingerprint.created_at.isoformat()
                    != fingerprint.observed_created_at
                ):
                    raise ValueError("canonical lead fingerprint index and payload disagree")
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
                if workflow.base_candidate_id != retained_fingerprint.base_candidate_id:
                    raise ValueError("canonical lead fingerprint and workflow candidate disagree")
                verified_original_review_package(
                    session, package_id=workflow.package_id,
                    candidate_key=workflow.base_candidate_id,
                )
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
                validated = read_validated_result_history(session, workflow.workflow_id)
                if validated is not None and validated["package_id"] != workflow.package_id:
                    raise ValueError("canonical result and workflow package disagree")
                revisions = [
                    _outcome_revision(record)
                    for record in validated["history"]
                ] if validated is not None else []
                revisions.sort(key=lambda record: record["revision"])
                for revision in revisions:
                    # Browser JSON numbers cannot retain all SQLite integer cents.
                    # Preserve the original helper's exact units as decimal strings.
                    for field in ("gross_value_minor", "calculated_share_minor"):
                        if revision[field] is not None:
                            revision[field] = str(revision[field])
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
                    "original_package_id": workflow.package_id,
                    "original_candidate_key": workflow.base_candidate_id,
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
                    "historical_result": {
                        "workflow_id": workflow.workflow_id,
                        "package_id": workflow.package_id,
                        "has_retained_outcome": validated is not None,
                        "history_integrity_validated": validated is not None,
                        "revision_count": len(revisions),
                        "current_revision": revisions[-1] if revisions else None,
                        "revision_history": revisions,
                        "money_unit_encoding": "decimal_integer_string",
                        "latest_revision_only_is_current": True,
                        "past_revisions_must_not_be_summed": True,
                        "award_verified": False,
                        "contract_verified": False,
                        "share_entitlement_verified": False,
                        "payment_received_verified": False,
                    },
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


def _fingerprint_matches(
    session: Session, *, source_family: str, source_record_id: str,
    resolved_site_key: str | None, exclude_canonical: str,
    store_name: str,
) -> list[dict[str, str]]:
    """Compare original indexed identities, not names, scores or fuzzy titles."""
    same_source = (
        (LeadFingerprintRecord.source_key == source_family)
        & (LeadFingerprintRecord.source_record_id == source_record_id)
    )
    predicate = (
        or_(same_source, LeadFingerprintRecord.site_key == resolved_site_key)
        if resolved_site_key else same_source
    )
    rows = session.scalars(
        select(LeadFingerprintRecord).where(predicate)
        .order_by(LeadFingerprintRecord.id).limit(101)
    ).all()
    if len(rows) > 100:
        raise ValueError("existing source/site lead matches exceed bounded review limit")
    results: list[dict[str, str]] = []
    for row in rows:
        # Validate the stored fingerprint; forged index fields cannot certify
        # a missing/false match, and must not silently allow another lead.
        fingerprint = LeadFingerprint.model_validate(json.loads(row.payload_json))
        if (
            fingerprint.fingerprint_key != row.fingerprint_key
            or fingerprint.source_key != row.source_key
            or fingerprint.source_record_id != row.source_record_id
            or fingerprint.site_key != row.site_key
        ):
            raise ValueError("persisted lead fingerprint index and payload disagree")
        if (
            store_name == "native"
            and fingerprint.source_key == "canonical_investigation"
            and fingerprint.source_record_id == exclude_canonical
        ):
            continue
        exact_source = (
            fingerprint.source_key == source_family
            and fingerprint.source_record_id == source_record_id
        )
        same_site = (
            resolved_site_key is not None
            and fingerprint.site_key == resolved_site_key
        )
        if not exact_source and not same_site:
            raise ValueError("source/site match index disagrees with payload")
        results.append({
            "store": store_name,
            "fingerprint_key": fingerprint.fingerprint_key,
            "match_basis": (
                "exact_source_family_and_record" if exact_source
                else "same_resolved_site_requires_identity_review"
            ),
            "existing_base_candidate_id": fingerprint.base_candidate_id,
        })
    return results


def canonical_lead_collisions(
    directory: Path, *, source_family: str, source_record_id: str,
    resolved_site_key: str | None, canonical_investigation_id: str,
    original_database: Path | None,
) -> dict[str, Any]:
    """Inspect original and native lead identity indexes, never infer title matches.

    An unconfigured original DB cannot be declared duplicate-free. A configured
    original DB is inspected read-only and must be physically separate.
    """
    canonical_db = prepare_private_database(
        directory / "investigations.sqlite3", create=False,
    )
    engine = create_operator_read_engine(canonical_db)
    try:
        with Session(engine, autoflush=False) as session:
            local = _fingerprint_matches(
                session, source_family=source_family,
                source_record_id=source_record_id,
                resolved_site_key=resolved_site_key,
                exclude_canonical=canonical_investigation_id, store_name="native",
            )
    finally:
        engine.dispose()
    external: list[dict[str, str]] = []
    if original_database is not None:
        if original_database.is_symlink() or not original_database.is_file():
            raise ValueError("original lead workflow database must be an existing regular file")
        if original_database.samefile(canonical_db):
            raise ValueError("original lead database must remain separate from canonical store")
        engine = create_operator_read_engine(original_database)
        try:
            with Session(engine, autoflush=False) as session:
                external = _fingerprint_matches(
                    session, source_family=source_family,
                    source_record_id=source_record_id,
                    resolved_site_key=resolved_site_key,
                    exclude_canonical=canonical_investigation_id,
                    store_name="original",
                )
        finally:
            engine.dispose()
    return {
        "original_store_scanned": original_database is not None,
        "native_store_scanned": True,
        "matches": [*local, *external],
        "review_required": bool(local or external),
        "identity_independently_verified": False,
        "commercial_authority_granted": False,
    }


_REVIEW_ONLY_STATUSES = frozenset({
    LeadWorkflowStatus.HOLD,
    LeadWorkflowStatus.MONITOR,
    LeadWorkflowStatus.REVIEW,
})


def transition_retained_canonical_review(
    directory: Path, payload: dict[str, Any], *,
    original_database: Path | None = None,
) -> dict[str, Any]:
    """Reuse original authorized append-only transitions, never qualify commerce.

    This entry point is deliberately narrower than the underlying original
    service. READY/ACTIVE/outcomes require independent verified lead, contact
    and commercial authority and are not exposed by the canonical UI.
    """
    if set(payload) != {
        "investigation_id", "workflow_id", "expected_status", "next_status",
        "expected_evidence_id", "reason", "caller_confirmation",
    }:
        raise ValueError("exact canonical workflow review transition fields required")
    identity, workflow_id = payload["investigation_id"], payload["workflow_id"]
    reason = payload["reason"]
    if (
        not isinstance(identity, str) or not 1 <= len(identity) <= 255
        or not isinstance(workflow_id, str) or not 1 <= len(workflow_id) <= 255
        or not isinstance(reason, str) or not 10 <= len(reason.strip()) <= 2000
        or not isinstance(payload["expected_evidence_id"], str)
        or not payload["expected_evidence_id"]
        or payload["caller_confirmation"] is not True
    ):
        raise ValueError("explicit exact-source operator review confirmation required")
    try:
        expected_status = LeadWorkflowStatus(payload["expected_status"])
        next_status = LeadWorkflowStatus(payload["next_status"])
    except (ValueError, TypeError) as exc:
        raise ValueError("unknown original workflow review status") from exc
    if (
        expected_status not in _REVIEW_ONLY_STATUSES
        or next_status not in _REVIEW_ONLY_STATUSES
        or next_status not in LEAD_WORKFLOW_TRANSITION_RULES[expected_status]
    ):
        raise ValueError(
            "only original matrix-valid hold/monitor/review transitions are permitted"
        )
    engine = create_private_database_engine(
        directory / "investigations.sqlite3", create=False,
    )
    try:
        with managed_session(session_factory(engine)) as session:
            session.connection().exec_driver_sql("BEGIN IMMEDIATE")
            preview = canonical_lead_preview(
                directory, identity, original_database=original_database,
            )
            current = preview["existing_native_handoff"]
            if current is None or current["workflow_id"] != workflow_id:
                raise ValueError("workflow is not the existing canonical investigation handoff")
            if preview["existing_source_or_site_matches"]["review_required"]:
                raise ValueError("existing source/site collision requires reconciliation")
            if preview["current_evidence_id"] != payload["expected_evidence_id"]:
                raise ValueError("retained source changed; re-review before transition")
            workflow = load_persisted_lead_workflow(session, workflow_id)
            verified_original_workflow_events(session, workflow)
            evidence_notes = [
                note.removeprefix("Original source evidence: ")
                for note in workflow.notes
                if note.startswith("Original source evidence: ")
            ]
            if (
                len(evidence_notes) != 1
                or evidence_notes[0] != preview["current_evidence_id"]
                or "Canonical investigation: " + identity not in workflow.notes
            ):
                raise ValueError("retained workflow source evidence is stale or inconsistent")
            if workflow.status != expected_status:
                raise ValueError("workflow status changed; re-open the native lead console")
            authorized = apply_authorized_lead_workflow_transition(
                session, workflow_id=workflow_id,
                expected_current_status=expected_status,
                next_status=next_status, reason=reason.strip(),
                caller_confirmation=True,
            )
            updated = load_persisted_lead_workflow(session, workflow_id)
            checked = verified_original_workflow_events(session, updated)
            if (
                checked["current_status"] != next_status.value
                or checked["event_count"] != len(workflow.events) + 1
            ):
                raise ValueError("durable original event history transition mismatch")
            return {
                "schema_version": "constructionsight.canonical-review-transition/v1",
                "canonical_investigation_id": identity,
                "workflow_id": workflow_id,
                "previous_status": expected_status.value,
                "current_status": next_status.value,
                "event_id": authorized.report.event_id,
                "history_integrity_validated": True,
                "event_count": checked["event_count"],
                "authorization_audit_identity": (
                    authorized.authorization.decision.audit_identity
                ),
                "source_evidence_id": preview["current_evidence_id"],
                "review_only": True,
                "outreach_authorized": False,
                "bid_authorized": False,
                "commercial_authority_granted": False,
            }
    except SQLAlchemyError as exc:
        raise ValueError("canonical workflow review transition could not be committed") from exc
    finally:
        engine.dispose()


_RESULT_REVIEW_STATUSES = frozenset({
    ResultLedgerStatus.OPEN,
    ResultLedgerStatus.UNKNOWN,
})


def apply_retained_canonical_result_review(
    directory: Path, payload: dict[str, Any], *,
    original_database: Path | None = None,
) -> dict[str, Any]:
    """Record an original open/unknown result for one retained canonical workflow.

    This deliberately does not qualify commercial outcomes, shares or payments.
    The original authorized result service owns every immutable ledger write.
    """
    required = {
        "investigation_id", "workflow_id", "expected_workflow_status",
        "expected_evidence_id", "expected_current_ledger_id", "result_status",
        "reason", "caller_confirmation",
    }
    if set(payload) != required:
        raise ValueError("exact canonical result review fields required")
    identity = payload["investigation_id"]
    workflow_id = payload["workflow_id"]
    reason = payload["reason"]
    expected_ledger_id = payload["expected_current_ledger_id"]
    if (
        not isinstance(identity, str) or not 1 <= len(identity) <= 255
        or not isinstance(workflow_id, str) or not 1 <= len(workflow_id) <= 255
        or not isinstance(reason, str) or not 10 <= len(reason.strip()) <= 2000
        or not isinstance(payload["expected_evidence_id"], str)
        or not payload["expected_evidence_id"]
        or (
            expected_ledger_id is not None
            and (not isinstance(expected_ledger_id, str)
                 or not 1 <= len(expected_ledger_id) <= 255)
        )
        or payload["caller_confirmation"] is not True
    ):
        raise ValueError("explicit exact-source result review confirmation required")
    try:
        expected_status = LeadWorkflowStatus(payload["expected_workflow_status"])
        result_status = ResultLedgerStatus(payload["result_status"])
    except (TypeError, ValueError) as exc:
        raise ValueError("unknown retained workflow/result status") from exc
    if (
        expected_status not in _REVIEW_ONLY_STATUSES
        or result_status not in _RESULT_REVIEW_STATUSES
    ):
        raise ValueError("unverified review workflows allow only open/unknown results")
    engine = create_private_database_engine(
        directory / "investigations.sqlite3", create=False,
    )
    try:
        with managed_session(session_factory(engine)) as session:
            session.connection().exec_driver_sql("BEGIN IMMEDIATE")
            preview = canonical_lead_preview(
                directory, identity, original_database=original_database,
            )
            handoff = preview["existing_native_handoff"]
            if handoff is None or handoff["workflow_id"] != workflow_id:
                raise ValueError("result workflow is not the exact canonical handoff")
            if preview["existing_source_or_site_matches"]["review_required"]:
                raise ValueError("original source/site collision requires reconciliation")
            if preview["current_evidence_id"] != payload["expected_evidence_id"]:
                raise ValueError("source evidence changed; repeat original result review")
            workflow = load_persisted_lead_workflow(session, workflow_id)
            verified_original_workflow_events(session, workflow)
            verified_original_review_package(
                session, package_id=workflow.package_id,
                candidate_key=workflow.base_candidate_id,
            )
            evidence_notes = [
                note.removeprefix("Original source evidence: ")
                for note in workflow.notes
                if note.startswith("Original source evidence: ")
            ]
            if (
                workflow.status != expected_status
                or workflow.fingerprint_key != handoff["fingerprint_key"]
                or len(evidence_notes) != 1
                or evidence_notes[0] != preview["current_evidence_id"]
                or "Canonical investigation: " + identity not in workflow.notes
            ):
                raise ValueError("canonical workflow status or source lineage is stale")
            validated = read_validated_result_history(session, workflow_id)
            current_id = (
                validated["current"]["ledger_id"] if validated is not None else None
            )
            if current_id != expected_ledger_id:
                raise ValueError("result revision changed; reload the native lead console")
            if (
                validated is not None
                and validated["revision_count"] >= MAX_REVISIONS_PER_WORKFLOW
            ):
                raise ValueError("result correction exceeds retained inspection limit")
            previous_count = validated["revision_count"] if validated else 0
            authorized = apply_authorized_authoritative_result(
                session,
                workflow_id=workflow_id,
                expected_current_ledger_id=expected_ledger_id,
                status=result_status,
                authorization_reason=reason.strip(),
                caller_confirmation=True,
                outcome_reasons=[reason.strip()],
            )
            checked = read_validated_result_history(session, workflow_id)
            if (
                checked is None
                or checked["revision_count"] != previous_count + 1
                or checked["current"]["ledger_id"] != authorized.report.current.ledger_id
                or checked["current"]["status"] != result_status.value
                or checked["current"]["gross_value"] is not None
            ):
                raise ValueError("authorized result write/history integrity disagreement")
            return {
                "schema_version": "constructionsight.canonical-result-review/v1",
                "canonical_investigation_id": identity,
                "workflow_id": workflow_id,
                "source_evidence_id": preview["current_evidence_id"],
                "previous_ledger_id": current_id,
                "current_ledger_id": authorized.report.current.ledger_id,
                "result_status": result_status.value,
                "revision_count": checked["revision_count"],
                "authorization_audit_identity": (
                    authorized.authorization.decision.audit_identity
                ),
                "history_integrity_validated": True,
                "review_only": True,
                "commercial_authority_granted": False,
                "award_verified": False,
                "contract_verified": False,
                "share_entitlement_verified": False,
                "payment_received_verified": False,
                "outreach_authorized": False,
                "bid_authorized": False,
            }
    except SQLAlchemyError as exc:
        raise ValueError("canonical result review could not be committed") from exc
    finally:
        engine.dispose()
