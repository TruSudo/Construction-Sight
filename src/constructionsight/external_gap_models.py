"""Models for Shovels/Regrid research-gap alignment."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator

from constructionsight.external_intelligence_models import ReferencePlatform


class GapPriority(StrEnum):
    """Priority for a knowledge or implementation gap."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EvidenceStrength(StrEnum):
    """How strongly a finding is grounded."""

    VERIFIED_PUBLIC_DOCS = "verified_public_docs"
    RESEARCH_INFERENCE = "research_inference"
    TRIAL_OR_SALES_REQUIRED = "trial_or_sales_required"
    USER_RESEARCH = "user_research"


class ImplementationRisk(StrEnum):
    """Implementation risk level for a roadmap step."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ResearchFinding(BaseModel):
    """One durable product finding from Shovels/Regrid research."""

    finding_key: str = Field(min_length=1)
    platform: ReferencePlatform
    title: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    evidence_strength: EvidenceStrength
    source_names: list[str] = Field(default_factory=list)
    construction_sight_implication: str = Field(min_length=1)

    @field_validator("source_names")
    @classmethod
    def require_unique_sources(cls, values: list[str]) -> list[str]:
        """Reject duplicate source names."""

        if len(values) != len(set(values)):
            raise ValueError("source_names must contain unique values")
        return values


class KnowledgeGap(BaseModel):
    """One actionable gap between current knowledge and implementation readiness."""

    gap_key: str = Field(min_length=1)
    platform: ReferencePlatform
    capability: str = Field(min_length=1)
    what_we_know: str = Field(min_length=1)
    what_we_do_not_know: str = Field(min_length=1)
    why_it_matters: str = Field(min_length=1)
    lawful_path_to_answer: str = Field(min_length=1)
    construction_sight_dependency: str = Field(min_length=1)
    priority: GapPriority
    suggested_pr: str = Field(min_length=1)
    acceptance_criteria: list[str] = Field(default_factory=list)

    @field_validator("acceptance_criteria")
    @classmethod
    def require_unique_acceptance_criteria(cls, values: list[str]) -> list[str]:
        """Reject duplicate acceptance criteria."""

        if len(values) != len(set(values)):
            raise ValueError("acceptance_criteria must contain unique values")
        return values


class ImplementationStep(BaseModel):
    """One recommended implementation step from the research roadmap."""

    step_key: str = Field(min_length=1)
    sequence: int = Field(ge=1)
    title: str = Field(min_length=1)
    goal: str = Field(min_length=1)
    likely_files: list[str] = Field(default_factory=list)
    required_tests: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)
    risk: ImplementationRisk
    why_it_matters: str = Field(min_length=1)
    unlocks: list[str] = Field(default_factory=list)

    @field_validator("likely_files", "required_tests", "acceptance_criteria", "unlocks")
    @classmethod
    def require_unique_values(cls, values: list[str]) -> list[str]:
        """Reject duplicate list values."""

        if len(values) != len(set(values)):
            raise ValueError("roadmap lists must contain unique values")
        return values


class GapAlignmentReport(BaseModel):
    """Summary of research findings, gaps, and roadmap steps."""

    report_id: str = Field(min_length=1)
    findings_reviewed: int = Field(ge=0)
    gaps_reviewed: int = Field(ge=0)
    roadmap_steps: int = Field(ge=0)
    critical_gaps: list[KnowledgeGap] = Field(default_factory=list)
    high_gaps: list[KnowledgeGap] = Field(default_factory=list)
    next_steps: list[ImplementationStep] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Return deterministic JSON-safe report payload."""

        return self.model_dump(mode="json")
