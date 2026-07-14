"""Build field-level parcel assurance from current canonical records."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from constructionsight.parcel_assurance_models import (
    ParcelAssuranceReport,
    ParcelAssuranceReviewStatus,
    ParcelAssuranceSourceContext,
    ParcelAssuranceStatus,
    ParcelAssuranceValueGroup,
    ParcelClaimMethod,
    ParcelEvidenceAuthority,
    ParcelEvidenceClaim,
    ParcelFieldAssurance,
)
from constructionsight.parcel_source_models import ParcelFieldRole

if TYPE_CHECKING:
    from constructionsight.parcel_core_models import ParcelCoreRecord


DEFAULT_PARCEL_ASSURANCE_FIELDS: tuple[ParcelFieldRole, ...] = (
    ParcelFieldRole.APN,
    ParcelFieldRole.ADDRESS,
    ParcelFieldRole.OWNER,
    ParcelFieldRole.COUNTY,
    ParcelFieldRole.STATE,
    ParcelFieldRole.JURISDICTION,
    ParcelFieldRole.ZONING,
    ParcelFieldRole.LAND_USE,
    ParcelFieldRole.ACREAGE,
    ParcelFieldRole.GEOMETRY,
    ParcelFieldRole.CENTROID_LATITUDE,
    ParcelFieldRole.CENTROID_LONGITUDE,
)


def build_parcel_assurance_report(
    *,
    records: Sequence[ParcelCoreRecord],
    source_contexts: Sequence[ParcelAssuranceSourceContext],
    field_roles: Sequence[ParcelFieldRole] = DEFAULT_PARCEL_ASSURANCE_FIELDS,
    generated_at: datetime | None = None,
) -> ParcelAssuranceReport:
    """Compare current parcel records without mutating their canonical payloads."""

    current_records = list(records)
    if not current_records:
        raise ValueError("parcel assurance requires at least one current record")
    requested_fields = _validated_fields(field_roles)
    contexts = _context_by_source(source_contexts)
    _validate_current_records(current_records, contexts)

    claims = sorted(
        (
            claim
            for record in current_records
            for claim in _claims_from_record(record, contexts[record.source_key])
            if claim.field_role in requested_fields
        ),
        key=lambda claim: claim.claim_id,
    )
    assurances = [
        _evaluate_field(field_role, claims)
        for field_role in sorted(requested_fields, key=lambda role: role.value)
    ]
    review_status = ParcelAssuranceReviewStatus.EVALUATED
    if any(assurance.requires_human_review for assurance in assurances):
        review_status = ParcelAssuranceReviewStatus.REVIEW_REQUIRED
    elif any(
        assurance.status == ParcelAssuranceStatus.MISSING for assurance in assurances
    ):
        review_status = ParcelAssuranceReviewStatus.INCOMPLETE

    first_record = current_records[0]
    report_limitations = _unique_sorted(
        [
            "Assurance applies only to the supplied current parcel records.",
            "Agreement does not establish countywide source coverage or legal title.",
            "Source currency is preserved but not evaluated by this report.",
            *(
                limitation
                for context in contexts.values()
                for limitation in context.limitations
            ),
        ]
    )
    return ParcelAssuranceReport(
        report_id=_report_id(
            normalized_apn=first_record.normalized_apn,
            county=first_record.county,
            claims=claims,
            field_roles=requested_fields,
            contexts=[contexts[record.source_key] for record in current_records],
        ),
        normalized_apn=first_record.normalized_apn,
        county=first_record.county,
        review_status=review_status,
        source_count=len(current_records),
        independent_lineage_count=len(
            {contexts[record.source_key].lineage_key for record in current_records}
        ),
        source_keys=sorted(record.source_key for record in current_records),
        lineage_keys=sorted(
            {contexts[record.source_key].lineage_key for record in current_records}
        ),
        claims=claims,
        field_assurances=assurances,
        limitations=report_limitations,
        generated_at=generated_at or datetime.now(UTC),
    )


def _validated_fields(field_roles: Sequence[ParcelFieldRole]) -> set[ParcelFieldRole]:
    fields = list(field_roles)
    if not fields:
        raise ValueError("parcel assurance requires at least one field role")
    if len(fields) != len(set(fields)):
        raise ValueError("parcel assurance field roles must be unique")
    unsupported = {
        ParcelFieldRole.SOURCE_RECORD_ID,
        ParcelFieldRole.UPDATED_AT,
        ParcelFieldRole.UNKNOWN,
    }
    if any(field in unsupported for field in fields):
        raise ValueError("parcel assurance field roles must identify parcel facts")
    return set(fields)


def _context_by_source(
    source_contexts: Sequence[ParcelAssuranceSourceContext],
) -> dict[str, ParcelAssuranceSourceContext]:
    contexts = list(source_contexts)
    keys = [context.source_key for context in contexts]
    if len(keys) != len(set(keys)):
        raise ValueError("parcel assurance source contexts must have unique source keys")
    return {context.source_key: context for context in contexts}


def _validate_current_records(
    records: list[ParcelCoreRecord],
    contexts: dict[str, ParcelAssuranceSourceContext],
) -> None:
    first_record = records[0]
    subject = (first_record.normalized_apn, first_record.county.strip().casefold())
    record_ids = [record.parcel_record_id for record in records]
    source_keys = [record.source_key for record in records]
    if len(record_ids) != len(set(record_ids)):
        raise ValueError("parcel assurance records must have unique record IDs")
    if len(source_keys) != len(set(source_keys)):
        raise ValueError("parcel assurance accepts one current record per source key")
    for record in records:
        record_subject = (record.normalized_apn, record.county.strip().casefold())
        if record_subject != subject:
            raise ValueError("parcel assurance records must identify the same parcel")
        if record.source_key not in contexts:
            raise ValueError(
                f"missing parcel assurance source context: {record.source_key}"
            )


def _claims_from_record(
    record: ParcelCoreRecord,
    context: ParcelAssuranceSourceContext,
) -> list[ParcelEvidenceClaim]:
    claims: list[ParcelEvidenceClaim] = []
    for (
        field_role,
        original_value,
        normalized_value,
        claim_method,
        limitations,
    ) in _record_values(record):
        authority = context.authority_for(field_role)
        if (
            claim_method != ParcelClaimMethod.DIRECT_OBSERVATION
            and authority == ParcelEvidenceAuthority.AUTHORITATIVE
        ):
            authority = context.default_authority
        claim_limitations = _unique_sorted(
            [*record.limitations, *context.limitations, *limitations]
        )
        claims.append(
            ParcelEvidenceClaim(
                claim_id=_claim_id(
                    record=record,
                    context=context,
                    field_role=field_role,
                    original_value=original_value,
                    normalized_value=normalized_value,
                    authority=authority,
                    claim_method=claim_method,
                    limitations=claim_limitations,
                ),
                parcel_record_id=record.parcel_record_id,
                source_key=record.source_key,
                source_record_id=record.source_record_id,
                lineage_key=context.lineage_key,
                field_role=field_role,
                original_value=original_value,
                normalized_value=normalized_value,
                authority=authority,
                claim_method=claim_method,
                evidence_reference=f"parcel-record:{record.parcel_record_id}",
                source_effective_at=record.source_updated_at,
                observed_at=record.created_at,
                limitations=claim_limitations,
            )
        )
    return claims


def _record_values(
    record: ParcelCoreRecord,
) -> list[
    tuple[ParcelFieldRole, str, str, ParcelClaimMethod, list[str]]
]:
    direct = ParcelClaimMethod.DIRECT_OBSERVATION
    derived = ParcelClaimMethod.DETERMINISTIC_DERIVATION
    values: list[
        tuple[ParcelFieldRole, str, str, ParcelClaimMethod, list[str]]
    ] = [
        (ParcelFieldRole.APN, record.apn, record.normalized_apn, direct, []),
        (
            ParcelFieldRole.COUNTY,
            record.county,
            _normalize_text(record.county),
            direct,
            [],
        ),
        (
            ParcelFieldRole.STATE,
            record.state,
            record.state.strip().upper(),
            direct,
            [],
        ),
    ]
    optional_text = (
        (ParcelFieldRole.ADDRESS, record.address, record.normalized_address),
        (ParcelFieldRole.JURISDICTION, record.jurisdiction, None),
        (ParcelFieldRole.ZONING, record.zoning, None),
        (ParcelFieldRole.LAND_USE, record.land_use, None),
    )
    for field_role, original_value, normalized_value in optional_text:
        if original_value is not None:
            values.append(
                (
                    field_role,
                    original_value,
                    normalized_value or _normalize_text(original_value),
                    direct,
                    [],
                )
            )
    if record.acreage is not None:
        acreage = _normalized_number(record.acreage)
        values.append((ParcelFieldRole.ACREAGE, acreage, acreage, direct, []))
    if record.geometry is not None:
        geometry = record.geometry
        geometry_limitations = list(geometry.limitations)
        geometry_value = geometry.geometry_hash
        if geometry_value is None and geometry.raw_geometry is not None:
            geometry_value = hashlib.sha256(
                geometry.raw_geometry.encode("utf-8")
            ).hexdigest()
        if geometry_value is not None:
            values.append(
                (
                    ParcelFieldRole.GEOMETRY,
                    geometry_value,
                    geometry_value,
                    direct,
                    geometry_limitations,
                )
            )
        if geometry.centroid_latitude is not None:
            latitude = _normalized_number(geometry.centroid_latitude)
            values.append(
                (
                    ParcelFieldRole.CENTROID_LATITUDE,
                    latitude,
                    latitude,
                    derived,
                    geometry_limitations,
                )
            )
        if geometry.centroid_longitude is not None:
            longitude = _normalized_number(geometry.centroid_longitude)
            values.append(
                (
                    ParcelFieldRole.CENTROID_LONGITUDE,
                    longitude,
                    longitude,
                    derived,
                    geometry_limitations,
                )
            )
    return values


def _evaluate_field(
    field_role: ParcelFieldRole,
    claims: list[ParcelEvidenceClaim],
) -> ParcelFieldAssurance:
    field_claims = [claim for claim in claims if claim.field_role == field_role]
    if not field_claims:
        return ParcelFieldAssurance(
            field_role=field_role,
            status=ParcelAssuranceStatus.MISSING,
            independent_lineage_count=0,
            authoritative_claim_count=0,
            reasons=["No supplied current parcel record contains this field."],
            limitations=["Missing evidence is not evidence that the fact is absent."],
        )

    value_groups = _value_groups(field_claims)
    claim_ids = sorted(claim.claim_id for claim in field_claims)
    lineage_count = len({claim.lineage_key for claim in field_claims})
    authoritative_count = sum(
        claim.authority == ParcelEvidenceAuthority.AUTHORITATIVE
        for claim in field_claims
    )
    limitations = _unique_sorted(
        limitation for claim in field_claims for limitation in claim.limitations
    )
    if len(value_groups) > 1:
        return ParcelFieldAssurance(
            field_role=field_role,
            status=ParcelAssuranceStatus.CONFLICT,
            claim_ids=claim_ids,
            value_groups=value_groups,
            independent_lineage_count=lineage_count,
            authoritative_claim_count=authoritative_count,
            requires_human_review=True,
            reasons=[
                "Supplied current records disagree on the normalized field value."
            ],
            limitations=limitations,
        )

    if authoritative_count and lineage_count >= 2:
        status = ParcelAssuranceStatus.AUTHORITATIVE_CORROBORATED
        reason = "An authoritative claim agrees with an independent source lineage."
    elif authoritative_count:
        status = ParcelAssuranceStatus.AUTHORITATIVE_SOURCE
        reason = "At least one direct claim is authoritative for this field."
    elif lineage_count >= 2:
        status = ParcelAssuranceStatus.INDEPENDENTLY_CORROBORATED
        reason = "Independent source lineages agree on the normalized field value."
    elif len(field_claims) > 1:
        status = ParcelAssuranceStatus.DEPENDENT_SOURCES_AGREE
        reason = "Multiple claims agree but share one upstream source lineage."
    else:
        status = ParcelAssuranceStatus.SINGLE_SOURCE
        reason = "Only one current source lineage supplies this field."
    return ParcelFieldAssurance(
        field_role=field_role,
        status=status,
        selected_normalized_value=value_groups[0].normalized_value,
        claim_ids=claim_ids,
        value_groups=value_groups,
        independent_lineage_count=lineage_count,
        authoritative_claim_count=authoritative_count,
        reasons=[reason],
        limitations=limitations,
    )


def _value_groups(
    claims: list[ParcelEvidenceClaim],
) -> list[ParcelAssuranceValueGroup]:
    values: dict[str, list[ParcelEvidenceClaim]] = {}
    for claim in claims:
        values.setdefault(claim.normalized_value, []).append(claim)
    return [
        ParcelAssuranceValueGroup(
            normalized_value=normalized_value,
            claim_ids=sorted(claim.claim_id for claim in grouped_claims),
            lineage_keys=sorted({claim.lineage_key for claim in grouped_claims}),
            authorities=sorted(
                {claim.authority for claim in grouped_claims},
                key=lambda authority: authority.value,
            ),
        )
        for normalized_value, grouped_claims in sorted(values.items())
    ]


def _claim_id(
    *,
    record: ParcelCoreRecord,
    context: ParcelAssuranceSourceContext,
    field_role: ParcelFieldRole,
    original_value: str,
    normalized_value: str,
    authority: ParcelEvidenceAuthority,
    claim_method: ParcelClaimMethod,
    limitations: list[str],
) -> str:
    payload = {
        "authority": authority.value,
        "field_role": field_role.value,
        "claim_method": claim_method.value,
        "lineage_key": context.lineage_key,
        "limitations": limitations,
        "normalized_value": normalized_value,
        "observed_at": record.created_at.isoformat(),
        "original_value": original_value,
        "parcel_record_id": record.parcel_record_id,
        "source_key": record.source_key,
        "source_record_id": record.source_record_id,
        "source_effective_at": (
            record.source_updated_at.isoformat()
            if record.source_updated_at is not None
            else None
        ),
    }
    return f"parcel-claim:{_digest(payload)}"


def _report_id(
    *,
    normalized_apn: str,
    county: str,
    claims: list[ParcelEvidenceClaim],
    field_roles: set[ParcelFieldRole],
    contexts: list[ParcelAssuranceSourceContext],
) -> str:
    payload = {
        "claim_ids": sorted(claim.claim_id for claim in claims),
        "county": county.strip().casefold(),
        "field_roles": sorted(field.value for field in field_roles),
        "normalized_apn": normalized_apn,
        "source_contexts": sorted(
            (_canonical_context(context) for context in contexts),
            key=lambda context: str(context["source_key"]),
        ),
    }
    return f"parcel-assurance:{_digest(payload)}"


def _digest(payload: dict[str, object]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _canonical_context(
    context: ParcelAssuranceSourceContext,
) -> dict[str, object]:
    return {
        "authoritative_fields": sorted(
            field_role.value for field_role in context.authoritative_fields
        ),
        "default_authority": context.default_authority.value,
        "limitations": sorted(context.limitations),
        "lineage_key": context.lineage_key,
        "source_key": context.source_key,
    }


def _normalize_text(value: str) -> str:
    return " ".join(value.split()).casefold()


def _normalized_number(value: float) -> str:
    return format(value, ".15g")


def _unique_sorted(values: Iterable[str]) -> list[str]:
    return sorted(set(values))
