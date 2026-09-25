"""Retain parcel observations and select current source records conservatively."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from constructionsight.parcel_assurance import (
    DEFAULT_PARCEL_ASSURANCE_FIELDS,
    build_parcel_assurance_report,
)
from constructionsight.parcel_assurance_models import ParcelAssuranceSourceContext
from constructionsight.parcel_core_models import ParcelCoreRecord
from constructionsight.parcel_observation_models import (
    ParcelCurrentSelectionReport,
    ParcelCurrentSelectionStatus,
    ParcelLongitudinalAssuranceResult,
    ParcelLongitudinalAssuranceStatus,
    ParcelObservationDisposition,
    ParcelObservationDispositionStatus,
    ParcelObservationTimeBasis,
    ParcelRecordObservation,
    ParcelSourceCurrentSelection,
    ParcelSourceSelectionStatus,
    parcel_current_selection_id,
    parcel_record_content_digest,
    parcel_record_digest,
)
from constructionsight.parcel_source_models import ParcelFieldRole


def build_parcel_record_observation(
    record: ParcelCoreRecord,
) -> ParcelRecordObservation:
    """Bind a complete canonical parcel record into an immutable observation."""

    retained = ParcelCoreRecord.model_validate(record.to_dict())
    record_digest = parcel_record_digest(retained)
    return ParcelRecordObservation(
        observation_id=f"parcel-observation:{record_digest}",
        record_digest=record_digest,
        content_digest=parcel_record_content_digest(retained),
        record=retained,
    )


def select_current_parcel_observations(
    observations: Sequence[ParcelRecordObservation],
    *,
    generated_at: datetime | None = None,
) -> ParcelCurrentSelectionReport:
    """Select at most one current observation per source without guessing through ties."""

    retained = list(observations)
    if not retained:
        raise ValueError("parcel current selection requires at least one observation")
    observation_ids = [item.observation_id for item in retained]
    if len(observation_ids) != len(set(observation_ids)):
        raise ValueError("parcel current selection requires unique observations")
    first = retained[0].record
    subject = (first.normalized_apn, first.county.strip().casefold())
    for observation in retained:
        record = observation.record
        if (record.normalized_apn, record.county.strip().casefold()) != subject:
            raise ValueError("parcel observations must identify the same parcel")

    grouped: dict[str, list[ParcelRecordObservation]] = {}
    for observation in retained:
        grouped.setdefault(observation.record.source_key, []).append(observation)
    source_selections = [
        _select_source(source_key, grouped[source_key])
        for source_key in sorted(grouped)
    ]
    requires_review = any(item.requires_human_review for item in source_selections)
    current_ids = sorted(
        item.current_observation_id
        for item in source_selections
        if item.current_observation_id is not None
    )
    status = (
        ParcelCurrentSelectionStatus.REVIEW_REQUIRED
        if requires_review
        else ParcelCurrentSelectionStatus.COMPLETE
    )
    limitations = sorted(
        {
            "Current selection is derived; retained source observations remain immutable.",
            (
                "Source-effective time is used only when every observation for that "
                "source supplies it."
            ),
            (
                "Observation time is used only when no observation for that source "
                "supplies source-effective time."
            ),
            *(
                limitation
                for selection in source_selections
                for limitation in selection.limitations
            ),
        }
    )
    selection_id = parcel_current_selection_id(
        normalized_apn=first.normalized_apn,
        county=first.county,
        status=status,
        source_count=len(source_selections),
        current_observation_ids=current_ids,
        source_selections=source_selections,
        requires_human_review=requires_review,
        limitations=limitations,
    )
    return ParcelCurrentSelectionReport(
        selection_report_id=selection_id,
        normalized_apn=first.normalized_apn,
        county=first.county,
        status=status,
        source_count=len(source_selections),
        current_observation_ids=current_ids,
        source_selections=source_selections,
        requires_human_review=requires_review,
        limitations=limitations,
        generated_at=_aware_utc(generated_at or datetime.now(UTC), "generated_at"),
    )


def build_longitudinal_parcel_assurance(
    *,
    observations: Sequence[ParcelRecordObservation],
    source_contexts: Sequence[ParcelAssuranceSourceContext],
    field_roles: Sequence[ParcelFieldRole] = DEFAULT_PARCEL_ASSURANCE_FIELDS,
    generated_at: datetime | None = None,
) -> ParcelLongitudinalAssuranceResult:
    """Feed only governed current observations into existing parcel assurance."""

    generated = _aware_utc(generated_at or datetime.now(UTC), "generated_at")
    selection = select_current_parcel_observations(
        observations,
        generated_at=generated,
    )
    contexts = _contexts_by_source(source_contexts)
    observed_source_keys = {
        observation.record.source_key for observation in observations
    }
    if set(contexts) != observed_source_keys:
        missing = sorted(observed_source_keys - set(contexts))
        extra = sorted(set(contexts) - observed_source_keys)
        raise ValueError(
            "parcel longitudinal source contexts must exactly match observations; "
            f"missing={missing}, extra={extra}"
        )
    limitations = tuple(
        sorted(
            {
                (
                    "Assurance is withheld whenever any source timeline lacks a unique "
                    "current observation."
                ),
                (
                    "Superseded observations remain evidence but do not enter current "
                    "field assurance."
                ),
            }
        )
    )
    if selection.requires_human_review:
        return ParcelLongitudinalAssuranceResult(
            status=ParcelLongitudinalAssuranceStatus.BLOCKED_REVIEW,
            selection=selection,
            limitations=limitations,
        )

    by_id = {item.observation_id: item for item in observations}
    current_records = [
        by_id[observation_id].record
        for observation_id in selection.current_observation_ids
    ]
    assurance = build_parcel_assurance_report(
        records=current_records,
        source_contexts=list(contexts.values()),
        field_roles=field_roles,
        generated_at=generated,
    )
    return ParcelLongitudinalAssuranceResult(
        status=ParcelLongitudinalAssuranceStatus.BUILT,
        selection=selection,
        assurance_report=assurance,
        limitations=limitations,
    )


def _select_source(
    source_key: str,
    observations: list[ParcelRecordObservation],
) -> ParcelSourceCurrentSelection:
    effective_presence = [
        item.record.source_updated_at is not None for item in observations
    ]
    if any(effective_presence) and not all(effective_presence):
        candidate_ids = sorted(item.observation_id for item in observations)
        dispositions = [
            ParcelObservationDisposition(
                observation_id=observation_id,
                status=ParcelObservationDispositionStatus.CURRENT_CANDIDATE,
                reasons=[
                    "The observation cannot be ordered against a different time basis."
                ],
            )
            for observation_id in candidate_ids
        ]
        return ParcelSourceCurrentSelection(
            source_key=source_key,
            status=ParcelSourceSelectionStatus.AMBIGUOUS,
            time_basis=ParcelObservationTimeBasis.MIXED_UNCOMPARABLE,
            candidate_observation_ids=candidate_ids,
            dispositions=dispositions,
            requires_human_review=True,
            reasons=[
                "Some source observations supply source-effective time and others do not."
            ],
            limitations=[
                (
                    "Source-effective time and observation time are not treated as "
                    "interchangeable clocks."
                )
            ],
        )

    if all(effective_presence):
        time_basis = ParcelObservationTimeBasis.SOURCE_EFFECTIVE_AT
        timestamp_by_id = {
            item.observation_id: _aware_utc(
                _required_effective_time(item),
                "source_updated_at",
            )
            for item in observations
        }
        basis_reason = "The latest source-effective timestamp governs this source."
    else:
        time_basis = ParcelObservationTimeBasis.OBSERVED_AT
        timestamp_by_id = {
            item.observation_id: _aware_utc(item.record.created_at, "created_at")
            for item in observations
        }
        basis_reason = (
            "No source-effective timestamps were supplied; latest observation time governs."
        )

    governing_timestamp = max(timestamp_by_id.values())
    top = [
        item
        for item in observations
        if timestamp_by_id[item.observation_id] == governing_timestamp
    ]
    top_ids = sorted(item.observation_id for item in top)
    if len({item.content_digest for item in top}) > 1:
        dispositions = _ambiguous_dispositions(observations, top_ids)
        return ParcelSourceCurrentSelection(
            source_key=source_key,
            status=ParcelSourceSelectionStatus.AMBIGUOUS,
            time_basis=time_basis,
            governing_timestamp=governing_timestamp,
            candidate_observation_ids=top_ids,
            dispositions=dispositions,
            requires_human_review=True,
            reasons=sorted(
                {
                    basis_reason,
                    (
                        "Competing observations at the governing timestamp contain "
                        "different parcel content."
                    ),
                }
            ),
            limitations=[
                "No current record is selected through a same-time content conflict."
            ],
        )

    current = max(
        top,
        key=lambda item: (
            _aware_utc(item.record.created_at, "created_at"),
            item.observation_id,
        ),
    )
    current_id = current.observation_id
    dispositions = [
        ParcelObservationDisposition(
            observation_id=item.observation_id,
            status=(
                ParcelObservationDispositionStatus.CURRENT
                if item.observation_id == current_id
                else ParcelObservationDispositionStatus.SUPERSEDED
            ),
            superseded_by_observation_ids=(
                [] if item.observation_id == current_id else [current_id]
            ),
            reasons=(
                ["This is the unique governed current observation."]
                if item.observation_id == current_id
                else [_supersession_reason(item, current, time_basis)]
            ),
        )
        for item in sorted(observations, key=lambda value: value.observation_id)
    ]
    return ParcelSourceCurrentSelection(
        source_key=source_key,
        status=ParcelSourceSelectionStatus.SELECTED,
        time_basis=time_basis,
        governing_timestamp=governing_timestamp,
        current_observation_id=current_id,
        candidate_observation_ids=[current_id],
        dispositions=dispositions,
        requires_human_review=False,
        reasons=[basis_reason],
    )


def _ambiguous_dispositions(
    observations: list[ParcelRecordObservation],
    candidate_ids: list[str],
) -> list[ParcelObservationDisposition]:
    candidate_set = set(candidate_ids)
    return [
        ParcelObservationDisposition(
            observation_id=item.observation_id,
            status=(
                ParcelObservationDispositionStatus.CURRENT_CANDIDATE
                if item.observation_id in candidate_set
                else ParcelObservationDispositionStatus.SUPERSEDED
            ),
            superseded_by_observation_ids=(
                [] if item.observation_id in candidate_set else candidate_ids
            ),
            reasons=(
                ["This observation is a competing current candidate."]
                if item.observation_id in candidate_set
                else ["A newer governing timestamp supersedes this observation."]
            ),
        )
        for item in sorted(observations, key=lambda value: value.observation_id)
    ]


def _supersession_reason(
    prior: ParcelRecordObservation,
    current: ParcelRecordObservation,
    time_basis: ParcelObservationTimeBasis,
) -> str:
    if prior.content_digest == current.content_digest:
        return "A later equivalent observation explicitly supersedes this observation."
    if time_basis is ParcelObservationTimeBasis.SOURCE_EFFECTIVE_AT:
        return "A newer source-effective observation explicitly supersedes this observation."
    return "A later observed parcel record explicitly supersedes this observation."


def _required_effective_time(observation: ParcelRecordObservation) -> datetime:
    value = observation.record.source_updated_at
    if value is None:
        raise ValueError("source-effective selection requires complete timestamps")
    return value


def _contexts_by_source(
    source_contexts: Sequence[ParcelAssuranceSourceContext],
) -> dict[str, ParcelAssuranceSourceContext]:
    contexts = list(source_contexts)
    keys = [item.source_key for item in contexts]
    if len(keys) != len(set(keys)):
        raise ValueError("parcel longitudinal source contexts must be unique")
    return {item.source_key: item for item in contexts}


def _aware_utc(value: datetime, label: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")
    return value.astimezone(UTC)
