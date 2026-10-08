from datetime import date

from sqlalchemy import func, select

from constructionsight.contractor_identity_models import (
    ContractorIdentityStatus,
    ContractorSourceKind,
)
from constructionsight.contractor_identity_service import build_contractor_identity
from constructionsight.intake_models import (
    ExtractedMaterialFact,
    FactConfidence,
    MaterialFactKind,
    UniversalIntakeRecord,
)
from constructionsight.intake_service import IntakeInspectionInput, inspect_lawful_input
from constructionsight.lead_dedupe_models import LeadDuplicateStatus
from constructionsight.lead_review_models import LeadReviewStatus
from constructionsight.lead_workflow_models import LeadWorkflowStatus
from constructionsight.opportunity_models import OpportunityReadiness
from constructionsight.permit_transition_models import PermitSnapshot
from constructionsight.permit_transition_service import detect_permit_transitions
from constructionsight.product_integration_service import (\n    build_product_integration,\n    persist_product_integration,\n)\nfrom constructionsight.site_resolution_models import SiteResolutionStatus
from constructionsight.storage.database import (
    create_database_engine,
    initialize_database,
    managed_session,
    session_factory,
)
from constructionsight.storage.lead_workflow_orm import (
    LeadDuplicateResultRecord,
    LeadFingerprintRecord,
    LeadReviewPackageRecord,
    LeadWorkflowEventRecord,
    LeadWorkflowRecordRow,
    OpportunityEnrichmentReportRecord,
)
from constructionsight.storage.parcel_site_orm import SiteResolutionResultRow


def _rich_intake(*, include_coordinate: bool) -> UniversalIntakeRecord:
    record = inspect_lawful_input(
        IntakeInspectionInput(
            content=b"""
            City of Hesperia filed SCH No. 2026061234 for warehouse construction.
            Project site: 123 Main Street. APN: 123-456-78.
            Permit No. BLD20260001 issued on 2026-06-01.
            CSLB: 123456. Estimated value: $3,000,000.
            Contact: planner@example.gov.
            """,
            source_name="representative integration record",
            source_family="permit",
        )
    )
    if not include_coordinate:
        return record
    coordinate = ExtractedMaterialFact(
        fact_id="fact:integration-coordinate",
        fact_kind=MaterialFactKind.UNKNOWN,
        value="34.5361, -117.2928",
        normalized_value="34.5361, -117.2928",
        confidence=FactConfidence.VERIFIED,
        evidence_id=record.evidence.evidence_id,
        context="verified site coordinate",
    )
    return record.model_copy(
        update={"extracted_facts": [*record.extracted_facts, coordinate]}
    )


def test_product_integration_keeps_early_outreach_score_conservative() -> None:
    report = build_product_integration(_rich_intake(include_coordinate=False))

    assert report.candidate.readiness == OpportunityReadiness.OUTREACH_READY
    assert report.site_resolution.status == SiteResolutionStatus.RESOLVED
    assert report.enrichment.lead_score == 20
    assert report.review_package.status == LeadReviewStatus.MONITOR
    assert report.workflow.status == LeadWorkflowStatus.MONITOR
    assert report.fingerprint is not None
    assert report.duplicate_result is not None
    assert report.duplicate_result.status == LeadDuplicateStatus.UNIQUE


def test_product_integration_reaches_ready_only_with_corroborating_signals() -> None:
    intake = _rich_intake(include_coordinate=True)
    site = build_product_integration(intake).site_resolution
    assert site.primary_site_key is not None
    assert site.limitations == []

    previous = PermitSnapshot(
        source_key="permit",
        source_record_id="BLD20260001",
        permit_number="BLD20260001",
        status="applied",
        site_key=site.primary_site_key,
    )
    current = PermitSnapshot(
        source_key="permit",
        source_record_id="BLD20260001",
        permit_number="BLD20260001",
        status="issued",
        issue_date=date(2026, 6, 1),
        job_value=3_000_000,
        site_key=site.primary_site_key,
    )
    transitions = detect_permit_transitions(previous, current)
    contractor = build_contractor_identity(
        display_name="Example General Contractors Inc.",
        source_kind=ContractorSourceKind.CSLB,
        license_number="123456",
        license_status=ContractorIdentityStatus.ACTIVE,
        classification="B",
    )

    report = build_product_integration(
        intake,
        site_resolution=site,
        permit_transitions=transitions,
        contractor_identity=contractor,
    )

    assert report.enrichment.lead_score >= 70
    assert report.enrichment.limitations == []
    assert report.review_package.status == LeadReviewStatus.READY
    assert report.workflow.status == LeadWorkflowStatus.READY
    assert report.duplicate_result is not None
    assert report.duplicate_result.status == LeadDuplicateStatus.UNIQUE


def test_product_integration_blocks_exact_duplicate_from_ready_workflow() -> None:
    intake = _rich_intake(include_coordinate=True)
    first = build_product_integration(intake)
    assert first.fingerprint is not None

    repeated = build_product_integration(
        intake,
        existing_fingerprints=[first.fingerprint],
    )

    assert repeated.duplicate_result is not None
    assert repeated.duplicate_result.status == LeadDuplicateStatus.DUPLICATE
    assert repeated.workflow.status == LeadWorkflowStatus.HOLD
    assert "lead fingerprint is a duplicate" in repeated.workflow.limitations


def test_persist_product_integration_commits_durable_stages_together() -> None:
    report = build_product_integration(_rich_intake(include_coordinate=False))
    engine = create_database_engine("sqlite:///:memory:")
    initialize_database(engine)
    factory = session_factory(engine)

    with managed_session(factory) as session:
        persist_product_integration(session, report)

        for model in (
            SiteResolutionResultRow,
            OpportunityEnrichmentReportRecord,
            LeadReviewPackageRecord,
            LeadFingerprintRecord,
            LeadDuplicateResultRecord,
            LeadWorkflowRecordRow,
            LeadWorkflowEventRecord,
        ):
            count = session.scalar(select(func.count()).select_from(model))
            assert count == 1
