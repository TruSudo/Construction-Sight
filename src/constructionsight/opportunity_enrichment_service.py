"""Opportunity enrichment service."""

from __future__ import annotations

import hashlib

from constructionsight.contractor_identity_models import ContractorIdentity
from constructionsight.decision_record_models import DecisionRecord
from constructionsight.domain_types import confidence_band
from constructionsight.opportunity_enrichment_models import (
    EnrichmentSignalKind,
    OpportunityEnrichmentReport,
    OpportunityEnrichmentSignal,
)
from constructionsight.permit_transition_models import (
    PermitTransition,
    PermitTransitionKind,
)
from constructionsight.site_resolution_models import SiteResolutionResult, SiteResolutionStatus


def enrich_opportunity(
    *,
    base_candidate_id: str,
    site_resolution: SiteResolutionResult | None = None,
    permit_transitions: list[PermitTransition] | None = None,
    contractor_identity: ContractorIdentity | None = None,
    decision_records: list[DecisionRecord] | None = None,
) -> OpportunityEnrichmentReport:
    """Build a cross-layer opportunity enrichment report."""

    signals: list[OpportunityEnrichmentSignal] = []
    if site_resolution is not None:
        signal = _site_signal(site_resolution)
        if signal is not None:
            signals.append(signal)
    for transition in permit_transitions or []:
        signals.append(_permit_signal(transition))
    if contractor_identity is not None:
        signals.append(_contractor_signal(contractor_identity))
    for decision in decision_records or []:
        signals.append(_decision_signal(decision))

    lead_score = min(sum(signal.score_delta for signal in signals), 100)
    confidence_score = _average_confidence(signals)
    limitations = _limitations(signals)
    reasons = [signal.reason for signal in signals]
    return OpportunityEnrichmentReport(
        report_id=_report_id(base_candidate_id, signals),
        base_candidate_id=base_candidate_id,
        lead_score=lead_score,
        confidence_score=confidence_score,
        confidence_band=confidence_band(confidence_score),
        signals=signals,
        reasons=_unique(reasons),
        limitations=limitations,
        next_action=_next_action(lead_score, limitations),
    )


def _site_signal(site_resolution: SiteResolutionResult) -> OpportunityEnrichmentSignal | None:
    """Return site-resolution enrichment signal when meaningful."""

    if site_resolution.status == SiteResolutionStatus.UNRESOLVED:
        return None
    score = 20 if site_resolution.status == SiteResolutionStatus.RESOLVED else 10
    confidence_score = site_resolution.candidates[0].confidence_score if site_resolution.candidates else 0
    return OpportunityEnrichmentSignal(
        signal_key=f"signal:site:{_short_hash(site_resolution.resolution_id)}",
        signal_kind=EnrichmentSignalKind.PARCEL_SITE,
        label="site anchor",
        score_delta=score,
        confidence_score=confidence_score,
        reason="site or parcel anchor is available",
        limitations=list(site_resolution.limitations),
    )


def _permit_signal(transition: PermitTransition) -> OpportunityEnrichmentSignal:
    """Return permit transition enrichment signal."""

    score_by_kind = {
        PermitTransitionKind.NEW_RECORD: 10,
        PermitTransitionKind.STATUS_CHANGED: 20,
        PermitTransitionKind.VALUE_CHANGED: 15,
        PermitTransitionKind.CONTRACTOR_CHANGED: 15,
        PermitTransitionKind.DATE_CHANGED: 10,
        PermitTransitionKind.SITE_CHANGED: 20,
        PermitTransitionKind.DESCRIPTION_CHANGED: 5,
    }
    score = score_by_kind[transition.transition_kind]
    return OpportunityEnrichmentSignal(
        signal_key=f"signal:permit:{_short_hash(transition.transition_id)}",
        signal_kind=EnrichmentSignalKind.PERMIT_TRANSITION,
        label=transition.transition_kind.value,
        score_delta=score,
        confidence_score=80,
        reason=transition.reason,
        limitations=list(transition.limitations),
    )


def _contractor_signal(identity: ContractorIdentity) -> OpportunityEnrichmentSignal:
    """Return contractor identity enrichment signal."""

    score = 15 if identity.license is not None else 8
    return OpportunityEnrichmentSignal(
        signal_key=f"signal:contractor:{_short_hash(identity.contractor_key)}",
        signal_kind=EnrichmentSignalKind.CONTRACTOR_IDENTITY,
        label="contractor identity",
        score_delta=score,
        confidence_score=identity.confidence_score,
        reason="contractor identity signal is available",
        limitations=list(identity.limitations),
    )


def _decision_signal(decision: DecisionRecord) -> OpportunityEnrichmentSignal:
    """Return public decision enrichment signal."""

    score = 15 if decision.site_key or decision.apn else 10
    return OpportunityEnrichmentSignal(
        signal_key=f"signal:decision:{_short_hash(decision.decision_key)}",
        signal_kind=EnrichmentSignalKind.DECISION_SIGNAL,
        label=decision.decision_kind.value,
        score_delta=score,
        confidence_score=decision.confidence_score,
        reason="pre-permit public decision signal is available",
        limitations=list(decision.limitations),
    )


def _average_confidence(signals: list[OpportunityEnrichmentSignal]) -> int:
    """Return average confidence score across signals."""

    if not signals:
        return 0
    return round(sum(signal.confidence_score for signal in signals) / len(signals))


def _limitations(signals: list[OpportunityEnrichmentSignal]) -> list[str]:
    """Return unique limitations from all signals."""

    values: list[str] = []
    for signal in signals:
        values.extend(signal.limitations)
    if not signals:
        values.append("no enrichment signals were available")
    return _unique(values)


def _next_action(lead_score: int, limitations: list[str]) -> str:
    """Return deterministic next action from score and limitations."""

    if lead_score >= 70 and not limitations:
        return "prepare outreach preview"
    if lead_score >= 50:
        return "review limitations before outreach"
    if lead_score > 0:
        return "monitor and enrich with more source evidence"
    return "hold until parcel, permit, contractor, or decision signal appears"


def _report_id(
    base_candidate_id: str,
    signals: list[OpportunityEnrichmentSignal],
) -> str:
    """Build deterministic enrichment report id."""

    basis = "|".join([base_candidate_id, ",".join(signal.signal_key for signal in signals)])
    return f"opportunity-enrichment:{_short_hash(basis)}"


def _short_hash(value: str) -> str:
    """Return a short deterministic hash."""

    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


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
