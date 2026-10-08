"""Governed ConstructionSight front-to-workflow integration service."""

from __future__ import annotations

from sqlalchemy.orm import Session

from constructionsight.contractor_identity_models import ContractorIdentity
from constructionsight.decision_record_models import DecisionRecord
from constructionsight.intake_models import MaterialFactKind, UniversalIntakeRecord
from constructionsight.lead_dedupe_models import LeadFingerprint
from constructionsight.lead_dedupe_service import (
    build_lead_fingerprint,
    check_lead_duplicate,
)
from constructionsight.lead_review_models import LeadReviewPackage
from constructionsight.lead_review_service import build_lead_review_package
from constructionsight.lead_workflow_service import create_lead_workflow
from constructionsight.opportunity_enrichment_service import enrich_opportunity
from constructionsight.opportunity_models import OpportunityCandidate
from constructionsight.opportunity_service import build_opportunity_candidate
from constructionsight.permit_transition_models import PermitTransition
from constructionsight.product_integration_models import ProductIntegrationReport
from constructionsight.site_resolution_models import SiteResolutionResult
from constructionsight.site_resolution_service import resolve_site_from_intake
from constructionsight.storage.lead_workflow_store import (
    store_lead_duplicate_result,
    store_lead_fingerprint,
    store_lead_review_package,
    store_lead_workflow_record,
    store_opportunity_enrichment_report,
)
from constructionsight.storage.parcel_site_store import store_site_resolution_result


def build_product_integration(
    intake: UniversalIntakeRecord,
    *,
    site_resolution: SiteResolutionResult | None = None,
    permit_transitions: list[PermitTransition] | None = None,
    contractor_identity: ContractorIdentity | None = None,
    decision_records: list[DecisionRecord] | None = None,
    existing_fingerprints: list[LeadFingerprint] | None = None,
) -> ProductIntegrationReport:
    """Carry one lawful intake record through the governed lead workflow.

    Early opportunity scoring is preserved for operator context, but downstream
    enrichment, review, dedupe, and workflow rules remain authoritative. This
    function does not authorize outreach, bids, or external effects.
    """

    candidate = build_opportunity_candidate(intake)
    resolved_site = site_resolution or resolve_site_from_intake(intake)
    enrichment = enrich_opportunity(
        base_candidate_id=candidate.candidate_id,
        site_resolution=resolved_site,
        permit_transitions=permit_transitions,
        contractor_identity=contractor_identity,
        decision_records=decision_records,
    )
    review_package = build_lead_review_package(enrichment)
    fingerprint = _build_fingerprint(
        intake=intake,
        candidate=candidate,
        site_resolution=resolved_site,
        review_package=review_package,
    )
    duplicate_result = None
    if fingerprint is not None:
        duplicate_result = check_lead_duplicate(
            fingerprint,
            existing_fingerprints or [],
        )
    workflow = create_lead_workflow(
        package=review_package,
        duplicate_result=duplicate_result,
    )
    return ProductIntegrationReport(
        candidate=candidate,
        site_resolution=resolved_site,
        enrichment=enrichment,
        review_package=review_package,
        fingerprint=fingerprint,
        duplicate_result=duplicate_result,
        workflow=workflow,
    )


def persist_product_integration(
    session: Session,
    report: ProductIntegrationReport,
) -> ProductIntegrationReport:
    """Persist the durable integration stages atomically.

    Universal intake and the initial opportunity candidate remain preserved
    evidence/derived runtime objects under the current storage contract. The
    durable site, enrichment, review, dedupe, and workflow layers are committed
    together or rolled back together.
    """

    with session.begin_nested():
        store_site_resolution_result(session, report.site_resolution)
        store_opportunity_enrichment_report(session, report.enrichment)
        store_lead_review_package(session, report.review_package)
        if report.fingerprint is not None:
            store_lead_fingerprint(session, report.fingerprint)
        if report.duplicate_result is not None:
            store_lead_duplicate_result(session, report.duplicate_result)
        store_lead_workflow_record(session, report.workflow)
        session.flush()
    return report


def _build_fingerprint(
    *,
    intake: UniversalIntakeRecord,
    candidate: OpportunityCandidate,
    site_resolution: SiteResolutionResult,
    review_package: LeadReviewPackage,
) -> LeadFingerprint | None:
    """Build dedupe identity only when a stable basis is available."""

    site_key = site_resolution.primary_site_key
    source_key = intake.evidence.source_family
    source_record_id = _source_record_id(intake)
    title = candidate.title_hint

    has_source_identity = source_key is not None and source_record_id is not None
    if site_key is None and not has_source_identity and title is None:
        return None

    return build_lead_fingerprint(
        package=review_package,
        site_key=site_key,
        source_key=source_key,
        source_record_id=source_record_id,
        title=title,
    )


def _source_record_id(intake: UniversalIntakeRecord) -> str | None:
    """Return the strongest generic source-record identity available."""

    for kind in (MaterialFactKind.PERMIT_NUMBER, MaterialFactKind.SCH_NUMBER):
        value = intake.record_hints.get(kind.value)
        if value:
            return value
    return None
