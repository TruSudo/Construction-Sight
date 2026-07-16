"""Opportunity candidate derivation from universal lawful intake records."""

from __future__ import annotations

from collections.abc import Iterable

from constructionsight.domain_types import confidence_band
from constructionsight.intake_models import (
    ExtractedMaterialFact,
    FactConfidence,
    IntakeRouting,
    MaterialFactKind,
    UniversalIntakeRecord,
)
from constructionsight.opportunity_models import (
    OpportunityCandidate,
    OpportunityPriority,
    OpportunityReadiness,
    OpportunityTransitionEvent,
    OpportunityTransitionKind,
)

_CONTEXT_ISSUED_TERMS = ("issued", "permit issued", "issuance")
_CONTEXT_APPLICATION_TERMS = ("applied", "application", "submitted", "filed", "received")
_CONTEXT_CONTRACTOR_TERMS = ("contractor", "general contractor", "builder", "license")
_CONTEXT_INSPECTION_TERMS = ("inspection", "inspected", "correction", "passed", "failed")
_CONTEXT_FINAL_TERMS = ("final", "finaled", "expired", "expiration", "closed")
_CEQA_KEYWORDS = {
    "environmental impact report",
    "mitigated negative declaration",
    "notice of preparation",
}
_SCOPE_KEYWORDS = {
    "construction",
    "warehouse",
    "industrial",
    "logistics",
    "distribution",
    "site security",
    "grading",
    "entitlement",
}
_SITE_HINT_KINDS = {MaterialFactKind.ADDRESS, MaterialFactKind.APN}
_CONTACT_HINT_KINDS = {MaterialFactKind.EMAIL, MaterialFactKind.PHONE, MaterialFactKind.URL}


def build_opportunity_candidate(intake: UniversalIntakeRecord) -> OpportunityCandidate:
    """Convert one universal intake record into a deterministic opportunity candidate."""

    transition_events = build_transition_events(intake)
    lead_score = score_transition_events(transition_events)
    readiness = readiness_for_score(lead_score)
    priority = priority_for_score(lead_score)
    reasons = reasons_for_events(transition_events)
    limitations = limitations_for_intake(intake)

    return OpportunityCandidate(
        candidate_id=f"candidate:{intake.evidence.evidence_id.removeprefix('evidence:')}",
        intake_id=intake.intake_id,
        evidence_id=intake.evidence.evidence_id,
        source_name=intake.evidence.source_name,
        source_url=intake.evidence.source_url,
        title_hint=title_hint(intake.extracted_facts),
        jurisdiction_hint=jurisdiction_hint(intake.extracted_facts),
        site_hints=site_hints(intake.extracted_facts),
        contact_hints=contact_hints(intake.extracted_facts),
        source_hints=intake.source_hints,
        transition_events=transition_events,
        lead_score=lead_score,
        readiness=readiness,
        priority=priority,
        confidence_band=confidence_band(lead_score),
        recommended_action=recommended_action(readiness),
        reasons=reasons,
        limitations=limitations,
    )


def build_transition_events(intake: UniversalIntakeRecord) -> list[OpportunityTransitionEvent]:
    """Build lead-producing transition signals from extracted intake facts."""

    candidates: list[_EventDraft] = [
        _EventDraft(
            kind=OpportunityTransitionKind.SOURCE_OBSERVED,
            label="Lawful source record observed",
            facts=[],
            score_delta=5,
            rationale="The lawful intake layer preserved a source record for monitoring.",
        )
    ]

    for fact in intake.extracted_facts:
        candidates.extend(_drafts_for_fact(fact))

    merged = _merge_event_drafts(candidates)
    evidence_id = intake.evidence.evidence_id
    evidence_suffix = evidence_id.removeprefix("evidence:")
    events: list[OpportunityTransitionEvent] = []
    for event_number, draft in enumerate(merged, start=1):
        confidence = _event_confidence(draft.facts)
        events.append(
            OpportunityTransitionEvent(
                event_id=f"transition:{evidence_suffix}:{event_number:03d}",
                event_kind=draft.kind,
                label=draft.label,
                evidence_id=evidence_id,
                fact_ids=[fact.fact_id for fact in draft.facts],
                confidence=confidence,
                score_delta=draft.score_delta,
                rationale=draft.rationale,
            )
        )
    return events


def score_transition_events(events: Iterable[OpportunityTransitionEvent]) -> int:
    """Return capped lead score from transition events."""

    return min(100, sum(event.score_delta for event in events))


def readiness_for_score(score: int) -> OpportunityReadiness:
    """Classify lead readiness from a deterministic score."""

    if score >= 70:
        return OpportunityReadiness.OUTREACH_READY
    if score >= 50:
        return OpportunityReadiness.RESEARCH_READY
    if score >= 25:
        return OpportunityReadiness.MONITOR
    return OpportunityReadiness.NOT_QUALIFIED


def priority_for_score(score: int) -> OpportunityPriority:
    """Classify operational priority from a deterministic score."""

    if score >= 75:
        return OpportunityPriority.HIGH
    if score >= 50:
        return OpportunityPriority.MEDIUM
    if score >= 25:
        return OpportunityPriority.LOW
    return OpportunityPriority.HOLD


def recommended_action(readiness: OpportunityReadiness) -> str:
    """Return the next operational action for the sales workflow."""

    if readiness == OpportunityReadiness.OUTREACH_READY:
        return "Enrich owner/developer/GC contacts, deduplicate, and prepare outreach preview."
    if readiness == OpportunityReadiness.RESEARCH_READY:
        return "Enrich parcel, entity, permit, agenda, and contractor context before outreach."
    if readiness == OpportunityReadiness.MONITOR:
        return "Keep monitoring for issuance, contractor, valuation, inspection, or CEQA movement."
    return "Archive as preserved evidence unless future transition events appear."


def title_hint(facts: list[ExtractedMaterialFact]) -> str | None:
    """Return the best available project title hint."""

    for fact in facts:
        if fact.fact_kind == MaterialFactKind.PROJECT_TITLE:
            return fact.normalized_value or fact.value
    return None


def jurisdiction_hint(facts: list[ExtractedMaterialFact]) -> str | None:
    """Return the best available jurisdiction or agency hint."""

    for fact in facts:
        if fact.fact_kind == MaterialFactKind.AGENCY:
            return fact.normalized_value or fact.value
    return None


def site_hints(facts: list[ExtractedMaterialFact]) -> dict[str, str]:
    """Return APN/address site hints from material facts."""

    hints: dict[str, str] = {}
    for fact in facts:
        if fact.fact_kind in _SITE_HINT_KINDS:
            hints.setdefault(fact.fact_kind.value, fact.normalized_value or fact.value)
    return hints


def contact_hints(facts: list[ExtractedMaterialFact]) -> dict[str, str]:
    """Return contact-channel hints from material facts."""

    hints: dict[str, str] = {}
    for fact in facts:
        if fact.fact_kind in _CONTACT_HINT_KINDS:
            hints.setdefault(fact.fact_kind.value, fact.normalized_value or fact.value)
    return hints


def reasons_for_events(events: list[OpportunityTransitionEvent]) -> list[str]:
    """Return deterministic human-readable reasons from transition events."""

    return [
        event.rationale
        for event in events
        if event.event_kind != OpportunityTransitionKind.SOURCE_OBSERVED
    ]


def limitations_for_intake(intake: UniversalIntakeRecord) -> list[str]:
    """Return opportunity-analysis limitations inherited from the intake record."""

    limitations: list[str] = []
    if intake.routing not in {IntakeRouting.OPPORTUNITY_INTAKE, IntakeRouting.SOURCE_ADAPTER}:
        limitations.append(f"intake routing is {intake.routing.value}, not opportunity-ready")
    if not intake.extracted_facts:
        limitations.append("no extracted material facts were available for opportunity scoring")
    for fragment in intake.unmapped_fragments:
        limitations.append(f"unmapped evidence remains: {fragment.reason}")
    return _unique(limitations)


def _drafts_for_fact(fact: ExtractedMaterialFact) -> list[_EventDraft]:
    """Return transition-event drafts for one extracted material fact."""

    context = (fact.context or "").lower()
    value = (fact.normalized_value or fact.value).lower()

    if fact.fact_kind == MaterialFactKind.SCH_NUMBER:
        return [_draft(OpportunityTransitionKind.CEQA_SIGNAL, fact, 25)]
    if fact.fact_kind == MaterialFactKind.PERMIT_NUMBER:
        if _contains_any(context, _CONTEXT_ISSUED_TERMS):
            return [_draft(OpportunityTransitionKind.PERMIT_ISSUED, fact, 30)]
        return [_draft(OpportunityTransitionKind.PERMIT_APPLICATION, fact, 20)]
    if fact.fact_kind == MaterialFactKind.CSLB_LICENSE:
        return [_draft(OpportunityTransitionKind.CONTRACTOR_IDENTIFIED, fact, 22)]
    if fact.fact_kind == MaterialFactKind.MONEY:
        return [_draft(OpportunityTransitionKind.VALUATION_CHANGED, fact, 18)]
    if fact.fact_kind in _SITE_HINT_KINDS:
        return [_draft(OpportunityTransitionKind.SITE_ANCHOR, fact, 12)]
    if fact.fact_kind in _CONTACT_HINT_KINDS:
        return [_draft(OpportunityTransitionKind.CONTACT_CHANNEL, fact, 7)]
    if fact.fact_kind == MaterialFactKind.AGENCY:
        return [_draft(OpportunityTransitionKind.AGENCY_ANCHOR, fact, 6)]
    if fact.fact_kind == MaterialFactKind.DATE:
        if _contains_any(context, _CONTEXT_INSPECTION_TERMS):
            return [_draft(OpportunityTransitionKind.INSPECTION_MOVEMENT, fact, 18)]
        if _contains_any(context, _CONTEXT_FINAL_TERMS):
            return [_draft(OpportunityTransitionKind.EXPIRATION_OR_FINALIZATION, fact, 18)]
        if _contains_any(context, _CONTEXT_APPLICATION_TERMS):
            return [_draft(OpportunityTransitionKind.PERMIT_APPLICATION, fact, 12)]
        return []
    if fact.fact_kind == MaterialFactKind.KEYWORD:
        if value in _CEQA_KEYWORDS:
            return [_draft(OpportunityTransitionKind.CEQA_SIGNAL, fact, 18)]
        if value in _SCOPE_KEYWORDS or _contains_any(context, _CONTEXT_CONTRACTOR_TERMS):
            return [_draft(OpportunityTransitionKind.CONSTRUCTION_SCOPE, fact, 8)]
    return []


def _draft(
    kind: OpportunityTransitionKind,
    fact: ExtractedMaterialFact,
    score_delta: int,
) -> _EventDraft:
    """Create a deterministic transition-event draft."""

    return _EventDraft(
        kind=kind,
        label=_LABELS[kind],
        facts=[fact],
        score_delta=score_delta,
        rationale=_RATIONALES[kind],
    )


def _merge_event_drafts(drafts: list[_EventDraft]) -> list[_EventDraft]:
    """Merge duplicate transition kinds while retaining all supporting facts."""

    by_kind: dict[OpportunityTransitionKind, _EventDraft] = {}
    for draft in drafts:
        existing = by_kind.get(draft.kind)
        if existing is None:
            by_kind[draft.kind] = draft
            continue
        fact_ids = {fact.fact_id for fact in existing.facts}
        existing.facts.extend(fact for fact in draft.facts if fact.fact_id not in fact_ids)
        existing.score_delta = max(existing.score_delta, draft.score_delta)
    return [by_kind[kind] for kind in OpportunityTransitionKind if kind in by_kind]


def _event_confidence(facts: list[ExtractedMaterialFact]) -> FactConfidence:
    """Return the strongest confidence represented by the supporting facts."""

    if not facts:
        return FactConfidence.SOURCE_CLAIMED
    if any(fact.confidence == FactConfidence.VERIFIED for fact in facts):
        return FactConfidence.VERIFIED
    if any(fact.confidence == FactConfidence.CONFLICTING for fact in facts):
        return FactConfidence.CONFLICTING
    if any(fact.confidence == FactConfidence.AMBIGUOUS for fact in facts):
        return FactConfidence.AMBIGUOUS
    if any(fact.confidence == FactConfidence.INFERRED for fact in facts):
        return FactConfidence.INFERRED
    return FactConfidence.SOURCE_CLAIMED


def _contains_any(value: str, terms: Iterable[str]) -> bool:
    """Return whether value contains any listed term."""

    return any(term in value for term in terms)


def _unique(values: list[str]) -> list[str]:
    """Return values with duplicates removed in first-seen order."""

    seen: set[str] = set()
    unique_values: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        unique_values.append(value)
    return unique_values


class _EventDraft:
    """Mutable internal transition-event draft before Pydantic validation."""

    def __init__(
        self,
        *,
        kind: OpportunityTransitionKind,
        label: str,
        facts: list[ExtractedMaterialFact],
        score_delta: int,
        rationale: str,
    ) -> None:
        self.kind = kind
        self.label = label
        self.facts = facts
        self.score_delta = score_delta
        self.rationale = rationale


_LABELS = {
    OpportunityTransitionKind.SOURCE_OBSERVED: "Lawful source record observed",
    OpportunityTransitionKind.CEQA_SIGNAL: "CEQA or environmental-review signal",
    OpportunityTransitionKind.PERMIT_APPLICATION: "Permit application or filing signal",
    OpportunityTransitionKind.PERMIT_ISSUED: "Issued permit signal",
    OpportunityTransitionKind.CONTRACTOR_IDENTIFIED: "Contractor identified signal",
    OpportunityTransitionKind.VALUATION_CHANGED: "Valuation or budget signal",
    OpportunityTransitionKind.INSPECTION_MOVEMENT: "Inspection movement signal",
    OpportunityTransitionKind.EXPIRATION_OR_FINALIZATION: "Expiration or finalization signal",
    OpportunityTransitionKind.SITE_ANCHOR: "Site, parcel, or address anchor",
    OpportunityTransitionKind.CONTACT_CHANNEL: "Contact channel signal",
    OpportunityTransitionKind.AGENCY_ANCHOR: "Public agency anchor",
    OpportunityTransitionKind.CONSTRUCTION_SCOPE: "Construction scope signal",
}

_RATIONALES = {
    OpportunityTransitionKind.SOURCE_OBSERVED: (
        "The lawful intake layer preserved a source record for monitoring."
    ),
    OpportunityTransitionKind.CEQA_SIGNAL: (
        "Environmental-review movement can surface projects before permit issuance."
    ),
    OpportunityTransitionKind.PERMIT_APPLICATION: (
        "Permit application or filing movement can indicate a project entering the "
        "approval pipeline."
    ),
    OpportunityTransitionKind.PERMIT_ISSUED: (
        "Issued-permit movement is a high-value outreach trigger because work may mobilize soon."
    ),
    OpportunityTransitionKind.CONTRACTOR_IDENTIFIED: (
        "A contractor/license signal identifies a party that can be enriched and contacted."
    ),
    OpportunityTransitionKind.VALUATION_CHANGED: (
        "Valuation or budget data helps estimate project size and security-service potential."
    ),
    OpportunityTransitionKind.INSPECTION_MOVEMENT: (
        "Inspection movement indicates active project progress after approval or "
        "construction start."
    ),
    OpportunityTransitionKind.EXPIRATION_OR_FINALIZATION: (
        "Expiration or finalization can mark closing windows, reactivation risk, "
        "or post-project relationship timing."
    ),
    OpportunityTransitionKind.SITE_ANCHOR: (
        "A parcel, APN, or address allows cross-source matching and geographic deduplication."
    ),
    OpportunityTransitionKind.CONTACT_CHANNEL: (
        "A contact channel reduces enrichment friction for outreach preparation."
    ),
    OpportunityTransitionKind.AGENCY_ANCHOR: (
        "An agency hint helps route the candidate to the correct jurisdiction/source family."
    ),
    OpportunityTransitionKind.CONSTRUCTION_SCOPE: (
        "Construction-scope language helps distinguish relevant project records "
        "from generic public records."
    ),
}
