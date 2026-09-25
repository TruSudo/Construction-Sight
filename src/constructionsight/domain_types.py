"""Shared domain enumerations for ConstructionSight."""

from __future__ import annotations

from enum import StrEnum


class ProjectPhase(StrEnum):
    """Lifecycle phase for a construction or development project."""

    UNKNOWN = "unknown"
    CONCEPT = "concept"
    ENTITLEMENT = "entitlement"
    ENVIRONMENTAL_REVIEW = "environmental_review"
    DESIGN_REVIEW = "design_review"
    APPROVED = "approved"
    PLAN_CHECK = "plan_check"
    PERMIT_ISSUED = "permit_issued"
    GRADING = "grading"
    UNDER_CONSTRUCTION = "under_construction"
    FINAL = "final"


class PartyRole(StrEnum):
    """Role played by a named entity in a public record."""

    UNKNOWN = "unknown"
    OWNER = "owner"
    DEVELOPER = "developer"
    APPLICANT = "applicant"
    CONTRACTOR = "contractor"
    GENERAL_CONTRACTOR = "general_contractor"
    ARCHITECT = "architect"
    ENGINEER = "engineer"
    CIVIL_ENGINEER = "civil_engineer"
    AGENCY = "agency"
    REPRESENTATIVE = "representative"


class RelationshipType(StrEnum):
    """Directed relationship type between normalized entities."""

    RELATED_TO = "related_to"
    OWNS = "owns"
    APPLIES_FOR = "applies_for"
    CONTRACTED_FOR = "contracted_for"
    DESIGNED_BY = "designed_by"
    ENGINEERED_BY = "engineered_by"
    LOCATED_AT = "located_at"
    ASSOCIATED_WITH = "associated_with"
    DERIVED_FROM = "derived_from"


class ConfidenceBand(StrEnum):
    """Human-readable confidence band for normalized assertions."""

    UNKNOWN = "unknown"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    VERIFIED = "verified"


def confidence_band(score: int, *, verified: bool = False) -> ConfidenceBand:
    """Convert confidence to a band without conflating score and verification."""

    if verified:
        return ConfidenceBand.VERIFIED
    if score >= 75:
        return ConfidenceBand.HIGH
    if score >= 50:
        return ConfidenceBand.MODERATE
    if score > 0:
        return ConfidenceBand.LOW
    return ConfidenceBand.UNKNOWN
