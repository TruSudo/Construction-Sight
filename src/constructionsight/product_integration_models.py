"""Whole-product integration report models."""

from __future__ import annotations

from pydantic import BaseModel, model_validator

from constructionsight.lead_dedupe_models import LeadDuplicateResult, LeadFingerprint
from constructionsight.lead_review_models import LeadReviewPackage
from constructionsight.lead_workflow_models import LeadWorkflowRecord
from constructionsight.opportunity_enrichment_models import OpportunityEnrichmentReport
from constructionsight.opportunity_models import OpportunityCandidate
from constructionsight.site_resolution_models import SiteResolutionResult


class ProductIntegrationReport(BaseModel):
    """One governed front-to-workflow ConstructionSight integration result."""

    candidate: OpportunityCandidate
    site_resolution: SiteResolutionResult
    enrichment: OpportunityEnrichmentReport
    review_package: LeadReviewPackage
    fingerprint: LeadFingerprint | None = None
    duplicate_result: LeadDuplicateResult | None = None
    workflow: LeadWorkflowRecord

    @model_validator(mode="after")
    def require_cross_stage_identity(self) -> ProductIntegrationReport:
        """Require every derived stage to retain the same candidate identity."""

        candidate_id = self.candidate.candidate_id
        if self.enrichment.base_candidate_id != candidate_id:
            raise ValueError("enrichment candidate identity does not match opportunity candidate")
        if self.review_package.base_candidate_id != candidate_id:
            raise ValueError(\n                "review package candidate identity does not match opportunity candidate"\n            )
        if self.workflow.base_candidate_id != candidate_id:
            raise ValueError("workflow candidate identity does not match opportunity candidate")
        if self.workflow.package_id != self.review_package.package_id:
            raise ValueError("workflow package identity does not match review package")
        if self.fingerprint is not None and self.fingerprint.base_candidate_id != candidate_id:
            raise ValueError(\n                "lead fingerprint candidate identity does not match opportunity candidate"\n            )
        if self.duplicate_result is not None:
            if self.fingerprint is None:
                raise ValueError("duplicate result requires a lead fingerprint")
            if (
                self.duplicate_result.candidate.fingerprint_key
                != self.fingerprint.fingerprint_key
            ):
                raise ValueError("duplicate result does not match the lead fingerprint")
        return self
