"""Conservative ArcGIS capability parsing, probe planning, and assessment."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from constructionsight.parcel_source_acquisition_models import (
    ParcelArcGISAcquisitionAssessment,
    ParcelArcGISAcquisitionGap,
    ParcelArcGISAcquisitionGapCode,
    ParcelArcGISAcquisitionStatus,
    ParcelArcGISBulkManifest,
    ParcelArcGISCapabilitySnapshot,
    ParcelArcGISFieldDefinition,
    ParcelArcGISProbeKind,
    ParcelArcGISProbeObservation,
    ParcelArcGISProbePlan,
    ParcelArcGISProbeRequest,
    arcgis_capability_projection_digest,
    arcgis_schema_fingerprint,
    canonical_json_payload,
    digest_identity,
    digest_json_payload,
)
from constructionsight.parcel_source_verification import (
    get_verified_parcel_source_profiles,
)
from constructionsight.parcel_source_verification_models import (
    ParcelSourceVerificationProfile,
)

_CAPABILITY_OBSERVED_AT = datetime(2026, 7, 14, 15, 17, 30, tzinfo=UTC)
_SAN_BERNARDINO_KEY = "san-bernardino:county-gis-parcels"
_RIVERSIDE_KEY = "riverside:county-gis-parcels"


def get_official_arcgis_capability_snapshots() -> list[ParcelArcGISCapabilitySnapshot]:
    """Return metadata-bound advertised capabilities for both official layers."""

    profiles = {
        profile.source_key: profile for profile in get_verified_parcel_source_profiles()
    }
    snapshots = [
        parse_arcgis_capability_snapshot(
            profiles[_SAN_BERNARDINO_KEY],
            _san_bernardino_metadata_projection(),
            observed_at=_CAPABILITY_OBSERVED_AT,
            limitations=(
                "Advertised query capabilities are not proof of successful page retrieval.",
                "No complete count-reconciled acquisition rehearsal has been executed.",
                "The metadata projection excludes mutable rendering and editing properties.",
            ),
        ),
        parse_arcgis_capability_snapshot(
            profiles[_RIVERSIDE_KEY],
            _riverside_metadata_projection(),
            observed_at=_CAPABILITY_OBSERVED_AT,
            limitations=(
                "Advertised query capabilities are not proof of successful page retrieval.",
                "No complete count-reconciled acquisition rehearsal has been executed.",
                "The metadata projection excludes mutable rendering and editing properties.",
            ),
        ),
    ]
    return sorted(snapshots, key=lambda snapshot: snapshot.source_key)


def get_official_arcgis_probe_plans(
    *,
    sample_size: int = 2,
    generated_at: datetime | None = None,
) -> list[ParcelArcGISProbePlan]:
    """Return bounded non-mutating plans for both official county layers."""

    return [
        build_arcgis_probe_plan(
            snapshot,
            sample_size=sample_size,
            generated_at=generated_at or _CAPABILITY_OBSERVED_AT,
        )
        for snapshot in get_official_arcgis_capability_snapshots()
    ]


def get_official_arcgis_acquisition_assessments(
    *,
    generated_at: datetime | None = None,
) -> list[ParcelArcGISAcquisitionAssessment]:
    """Return current metadata-only assessments without fabricating probe results."""

    snapshots = get_official_arcgis_capability_snapshots()
    plans = get_official_arcgis_probe_plans(generated_at=generated_at)
    plans_by_snapshot = {plan.snapshot_id: plan for plan in plans}
    return [
        build_arcgis_acquisition_assessment(
            snapshot,
            plans_by_snapshot[snapshot.snapshot_id],
            generated_at=generated_at or _CAPABILITY_OBSERVED_AT,
        )
        for snapshot in snapshots
    ]


def parse_arcgis_capability_snapshot(
    profile: ParcelSourceVerificationProfile,
    metadata: dict[str, Any],
    *,
    observed_at: datetime,
    limitations: tuple[str, ...],
) -> ParcelArcGISCapabilitySnapshot:
    """Parse and bind a live ArcGIS layer metadata projection."""

    _require_aware(observed_at, "ArcGIS capability observed_at")
    if "error" in metadata:
        raise ValueError("ArcGIS capability metadata contains an error response")
    fields_payload = metadata.get("fields")
    if not isinstance(fields_payload, list) or not fields_payload:
        raise ValueError("ArcGIS capability metadata requires a nonempty field list")
    fields = tuple(
        sorted(
            (_parse_field_definition(item) for item in fields_payload),
            key=lambda field: (field.name.casefold(), field.field_type),
        )
    )
    field_names = {field.name for field in fields}
    expected_profile_fields = field_names | {"geometry"}
    if expected_profile_fields != set(profile.schema_fields):
        missing = sorted(expected_profile_fields - set(profile.schema_fields))
        stale = sorted(set(profile.schema_fields) - expected_profile_fields)
        raise ValueError(
            "ArcGIS metadata disagrees with verification profile schema: "
            f"missing={missing}, stale={stale}"
        )
    layer_url = profile.source_url
    if not layer_url:
        raise ValueError("ArcGIS verification profile requires a source URL")
    object_id_field = _object_id_field(metadata, fields)
    spatial_reference = _spatial_reference(metadata)
    geometry_type = _required_string(metadata, "geometryType")
    advanced = metadata.get("advancedQueryCapabilities")
    if not isinstance(advanced, dict):
        advanced = {}
    capabilities = {
        value.strip().casefold()
        for value in str(metadata.get("capabilities", "")).split(",")
        if value.strip()
    }
    supported_formats = tuple(
        sorted(
            {
                value.strip().casefold()
                for value in str(metadata.get("supportedQueryFormats", "")).split(",")
                if value.strip()
            },
            key=str.casefold,
        )
    )
    max_record_count = _required_int(metadata, "maxRecordCount", minimum=1)
    if profile.max_record_count != max_record_count:
        raise ValueError("ArcGIS maximum record count drifted from verification profile")
    schema_fingerprint = arcgis_schema_fingerprint(
        fields,
        geometry_type=geometry_type,
        spatial_reference=spatial_reference,
    )
    canonical_limitations = tuple(sorted(set(limitations), key=str.casefold))
    service_version = _service_version(metadata)
    object_id_is_unique = _object_id_is_unique(metadata, object_id_field)
    supports_query = "query" in capabilities
    supports_count = bool(
        metadata.get("supportsStatistics") or advanced.get("supportsStatistics")
    )
    supports_order_by = bool(advanced.get("supportsOrderBy"))
    supports_pagination = bool(advanced.get("supportsPagination"))
    metadata_projection_digest = arcgis_capability_projection_digest(
        service_version=service_version,
        geometry_type=geometry_type,
        spatial_reference=spatial_reference,
        fields=fields,
        object_id_field=object_id_field,
        object_id_is_unique=object_id_is_unique,
        max_record_count=max_record_count,
        supports_query=supports_query,
        supports_count=supports_count,
        supports_order_by=supports_order_by,
        supports_pagination=supports_pagination,
        supported_query_formats=supported_formats,
    )
    candidate = ParcelArcGISCapabilitySnapshot.model_construct(
        snapshot_id="parcel-arcgis-capability:" + ("0" * 64),
        profile_id=profile.profile_id,
        source_key=profile.source_key,
        county=profile.county,
        layer_url=layer_url,
        observed_at=observed_at,
        service_version=service_version,
        geometry_type=geometry_type,
        spatial_reference=spatial_reference,
        fields=fields,
        schema_fingerprint=schema_fingerprint,
        metadata_projection_digest=metadata_projection_digest,
        object_id_field=object_id_field,
        object_id_is_unique=object_id_is_unique,
        max_record_count=max_record_count,
        supports_query=supports_query,
        supports_count=supports_count,
        supports_order_by=supports_order_by,
        supports_pagination=supports_pagination,
        supported_query_formats=supported_formats,
        limitations=canonical_limitations,
    )
    payload = candidate.model_dump(mode="json", exclude={"snapshot_id"})
    return ParcelArcGISCapabilitySnapshot.model_validate(
        {
            **payload,
            "snapshot_id": digest_identity("parcel-arcgis-capability", payload),
        }
    )


def build_arcgis_probe_plan(
    snapshot: ParcelArcGISCapabilitySnapshot,
    *,
    sample_size: int = 2,
    generated_at: datetime | None = None,
) -> ParcelArcGISProbePlan:
    """Build count, adjacent-page, and replay requests without authorizing bulk."""

    if sample_size < 1 or sample_size > min(snapshot.max_record_count, 100):
        raise ValueError("ArcGIS probe sample size exceeds the bounded safe limit")
    requests = tuple(
        _probe_request(snapshot, kind=kind, sample_size=sample_size)
        for kind in ParcelArcGISProbeKind
    )
    candidate = ParcelArcGISProbePlan.model_construct(
        plan_id="parcel-arcgis-probe-plan:" + ("0" * 64),
        snapshot_id=snapshot.snapshot_id,
        profile_id=snapshot.profile_id,
        source_key=snapshot.source_key,
        county=snapshot.county,
        sample_size=sample_size,
        requests=requests,
        bulk_run_authorized=False,
        next_action=(
            "execute the four read-only requests, persist digest-bound responses, "
            "and reassess before any complete acquisition rehearsal"
        ),
        generated_at=generated_at or datetime.now(UTC),
    )
    payload = candidate.model_dump(
        mode="json",
        exclude={"plan_id", "generated_at"},
    )
    return ParcelArcGISProbePlan.model_validate(
        {**candidate.model_dump(mode="json"), "plan_id": digest_identity(
            "parcel-arcgis-probe-plan", payload
        )}
    )


def parse_arcgis_probe_observation(
    request: ParcelArcGISProbeRequest,
    response_payload: dict[str, Any],
    *,
    observed_at: datetime,
) -> ParcelArcGISProbeObservation:
    """Parse one ArcGIS count or page response and bind the exact response digest."""

    _require_aware(observed_at, "ArcGIS probe observed_at")
    if "error" in response_payload:
        raise ValueError("ArcGIS probe response contains an error")
    total_count: int | None = None
    object_ids: tuple[int, ...] = ()
    exceeded_transfer_limit: bool | None = None
    if request.kind == ParcelArcGISProbeKind.COUNT:
        total_count = _required_int(response_payload, "count", minimum=0)
    else:
        features = response_payload.get("features")
        if not isinstance(features, list):
            raise ValueError("ArcGIS page response requires a feature list")
        parsed_ids: list[int] = []
        for feature in features:
            if not isinstance(feature, dict):
                raise ValueError("ArcGIS page features must be JSON objects")
            attributes = feature.get("attributes")
            if not isinstance(attributes, dict):
                raise ValueError("ArcGIS page features require attributes")
            value = attributes.get(request.object_id_field)
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError("ArcGIS page object IDs must be integers")
            parsed_ids.append(value)
        object_ids = tuple(parsed_ids)
        transfer_value = response_payload.get("exceededTransferLimit")
        if transfer_value is not None and not isinstance(transfer_value, bool):
            raise ValueError("ArcGIS exceededTransferLimit must be boolean when present")
        exceeded_transfer_limit = transfer_value
    response_payload_json = canonical_json_payload(response_payload)
    candidate = ParcelArcGISProbeObservation.model_construct(
        observation_id="parcel-arcgis-probe-observation:" + ("0" * 64),
        request_id=request.request_id,
        snapshot_id=request.snapshot_id,
        profile_id=request.profile_id,
        source_key=request.source_key,
        county=request.county,
        kind=request.kind,
        observed_at=observed_at,
        response_digest=digest_json_payload(response_payload),
        response_payload_json=response_payload_json,
        schema_fingerprint=request.schema_fingerprint,
        total_count=total_count,
        object_ids=object_ids,
        exceeded_transfer_limit=exceeded_transfer_limit,
    )
    payload = candidate.model_dump(mode="json", exclude={"observation_id"})
    return ParcelArcGISProbeObservation.model_validate(
        {
            **payload,
            "observation_id": digest_identity(
                "parcel-arcgis-probe-observation", payload
            ),
        }
    )


def build_arcgis_bulk_manifest(
    snapshot: ParcelArcGISCapabilitySnapshot,
    *,
    started_at: datetime,
    completed_at: datetime,
    starting_count: int,
    ending_count: int,
    page_size: int,
    page_count: int,
    retrieved_count: int,
    unique_object_id_count: int,
    duplicate_object_id_count: int,
    failed_page_count: int,
    terminal_page_observed: bool,
    checkpoint_resume_verified: bool,
    retry_recovery_verified: bool,
    page_response_digests: tuple[str, ...],
    object_id_set_digest: str,
) -> ParcelArcGISBulkManifest:
    """Build a digest-bound complete-run manifest after a real rehearsal."""

    candidate = ParcelArcGISBulkManifest.model_construct(
        manifest_id="parcel-arcgis-bulk-manifest:" + ("0" * 64),
        snapshot_id=snapshot.snapshot_id,
        profile_id=snapshot.profile_id,
        source_key=snapshot.source_key,
        county=snapshot.county,
        schema_fingerprint=snapshot.schema_fingerprint,
        started_at=started_at,
        completed_at=completed_at,
        starting_count=starting_count,
        ending_count=ending_count,
        page_size=page_size,
        page_count=page_count,
        retrieved_count=retrieved_count,
        unique_object_id_count=unique_object_id_count,
        duplicate_object_id_count=duplicate_object_id_count,
        failed_page_count=failed_page_count,
        terminal_page_observed=terminal_page_observed,
        checkpoint_resume_verified=checkpoint_resume_verified,
        retry_recovery_verified=retry_recovery_verified,
        page_response_digests=page_response_digests,
        object_id_set_digest=object_id_set_digest,
    )
    payload = candidate.model_dump(mode="json", exclude={"manifest_id"})
    return ParcelArcGISBulkManifest.model_validate(
        {
            **payload,
            "manifest_id": digest_identity("parcel-arcgis-bulk-manifest", payload),
        }
    )


def build_arcgis_acquisition_assessment(
    snapshot: ParcelArcGISCapabilitySnapshot,
    plan: ParcelArcGISProbePlan,
    observations: Iterable[ParcelArcGISProbeObservation] = (),
    *,
    bulk_manifest: ParcelArcGISBulkManifest | None = None,
    generated_at: datetime | None = None,
) -> ParcelArcGISAcquisitionAssessment:
    """Assess advertised capability, bounded proof, and complete-run reconciliation."""

    _require_plan_scope(snapshot, plan)
    reviewed = list(observations)
    request_by_id = {request.request_id: request for request in plan.requests}
    if len(request_by_id) != len(plan.requests):
        raise ValueError("ArcGIS probe plan request IDs must be unique")
    observation_by_request: dict[str, ParcelArcGISProbeObservation] = {}
    for observation in reviewed:
        request = request_by_id.get(observation.request_id)
        if request is None:
            raise ValueError("ArcGIS observation is not part of the probe plan")
        if observation.request_id in observation_by_request:
            raise ValueError("ArcGIS probe requests may have only one bound observation")
        if (
            observation.snapshot_id != snapshot.snapshot_id
            or observation.profile_id != snapshot.profile_id
            or observation.source_key != snapshot.source_key
            or observation.county != snapshot.county
            or observation.kind != request.kind
        ):
            raise ValueError("ArcGIS probe observation scope does not match its request")
        observation_by_request[observation.request_id] = observation

    gaps = _capability_gaps(snapshot)
    requests_by_kind = {request.kind: request for request in plan.requests}
    count_observation = observation_by_request.get(
        requests_by_kind[ParcelArcGISProbeKind.COUNT].request_id
    )
    if count_observation is None:
        gaps.append(
            _gap(
                ParcelArcGISAcquisitionGapCode.COUNT_PROBE_MISSING,
                "No executed count response is bound to the current schema snapshot.",
                "execute and persist the planned count request",
            )
        )
    page_observations = {
        kind: observation_by_request.get(requests_by_kind[kind].request_id)
        for kind in (
            ParcelArcGISProbeKind.INITIAL_PAGE,
            ParcelArcGISProbeKind.NEXT_PAGE,
            ParcelArcGISProbeKind.REPLAY_PAGE,
        )
    }
    if (
        page_observations[ParcelArcGISProbeKind.INITIAL_PAGE] is None
        or page_observations[ParcelArcGISProbeKind.NEXT_PAGE] is None
    ):
        gaps.append(
            _gap(
                ParcelArcGISAcquisitionGapCode.PAGE_PROBE_MISSING,
                "Adjacent ordered page responses have not both been observed.",
                "execute and persist the planned initial and next-page requests",
            )
        )
    if page_observations[ParcelArcGISProbeKind.REPLAY_PAGE] is None:
        gaps.append(
            _gap(
                ParcelArcGISAcquisitionGapCode.PAGE_REPLAY_MISSING,
                "The initial ordered page has not been replayed for stability.",
                "execute and persist the planned replay-page request",
            )
        )
    if any(
        observation.schema_fingerprint != snapshot.schema_fingerprint
        for observation in reviewed
    ):
        gaps.append(
            _gap(
                ParcelArcGISAcquisitionGapCode.SCHEMA_DRIFT,
                "A probe observation is bound to a different schema fingerprint.",
                "stop acquisition and re-verify the live schema",
            )
        )
    expected_count = None if count_observation is None else count_observation.total_count
    sample_ids: set[int] = set()
    if all(observation is not None for observation in page_observations.values()):
        initial = page_observations[ParcelArcGISProbeKind.INITIAL_PAGE]
        next_page = page_observations[ParcelArcGISProbeKind.NEXT_PAGE]
        replay = page_observations[ParcelArcGISProbeKind.REPLAY_PAGE]
        assert initial is not None
        assert next_page is not None
        assert replay is not None
        sequence_valid = _page_sequence_is_valid(
            plan,
            initial,
            next_page,
            replay,
            expected_count,
        )
        sample_ids = set(initial.object_ids) | set(next_page.object_ids)
        if not sequence_valid:
            gaps.append(
                _gap(
                    ParcelArcGISAcquisitionGapCode.PAGE_SEQUENCE_INVALID,
                    "Ordered adjacent pages or the replay page failed reconciliation.",
                    "stop and inspect ordering, offset, duplication, and source drift",
                )
            )

    if bulk_manifest is None:
        gaps.append(
            _gap(
                ParcelArcGISAcquisitionGapCode.BULK_REHEARSAL_MISSING,
                "No complete count-reconciled acquisition manifest is present.",
                "run a checkpointed rehearsal only after bounded probes pass",
            )
        )
    else:
        _require_manifest_scope(snapshot, count_observation, bulk_manifest)

    canonical_gaps = tuple(sorted(gaps, key=lambda gap: gap.code.value))
    status = _status_for_gaps(canonical_gaps)
    observation_ids = tuple(sorted(item.observation_id for item in reviewed))
    candidate = ParcelArcGISAcquisitionAssessment.model_construct(
        assessment_id="parcel-arcgis-acquisition:" + ("0" * 64),
        snapshot_id=snapshot.snapshot_id,
        plan_id=plan.plan_id,
        profile_id=snapshot.profile_id,
        source_key=snapshot.source_key,
        county=snapshot.county,
        status=status,
        probe_observation_ids=observation_ids,
        bulk_manifest_id=None if bulk_manifest is None else bulk_manifest.manifest_id,
        expected_record_count=expected_count,
        observed_unique_sample_count=len(sample_ids),
        bulk_acquisition_verified=(
            status == ParcelArcGISAcquisitionStatus.BULK_REHEARSAL_VERIFIED
        ),
        gaps=canonical_gaps,
        generated_at=generated_at or datetime.now(UTC),
    )
    payload = candidate.model_dump(
        mode="json",
        exclude={"assessment_id", "generated_at"},
    )
    return ParcelArcGISAcquisitionAssessment.model_validate(
        {
            **candidate.model_dump(mode="json"),
            "assessment_id": digest_identity("parcel-arcgis-acquisition", payload),
        }
    )


def _probe_request(
    snapshot: ParcelArcGISCapabilitySnapshot,
    *,
    kind: ParcelArcGISProbeKind,
    sample_size: int,
) -> ParcelArcGISProbeRequest:
    is_count = kind == ParcelArcGISProbeKind.COUNT
    offset = None
    if kind == ParcelArcGISProbeKind.INITIAL_PAGE:
        offset = 0
    elif kind == ParcelArcGISProbeKind.NEXT_PAGE:
        offset = sample_size
    elif kind == ParcelArcGISProbeKind.REPLAY_PAGE:
        offset = 0
    candidate = ParcelArcGISProbeRequest.model_construct(
        request_id="parcel-arcgis-probe-request:" + ("0" * 64),
        snapshot_id=snapshot.snapshot_id,
        profile_id=snapshot.profile_id,
        source_key=snapshot.source_key,
        county=snapshot.county,
        kind=kind,
        where="1=1",
        object_id_field=snapshot.object_id_field,
        schema_fingerprint=snapshot.schema_fingerprint,
        out_fields=() if is_count else (snapshot.object_id_field,),
        order_by_fields=()
        if is_count
        else (f"{snapshot.object_id_field} ASC",),
        return_geometry=False,
        return_count_only=is_count,
        offset=offset,
        record_count=None if is_count else sample_size,
    )
    payload = candidate.model_dump(mode="json", exclude={"request_id"})
    return ParcelArcGISProbeRequest.model_validate(
        {
            **payload,
            "request_id": digest_identity("parcel-arcgis-probe-request", payload),
        }
    )


def _capability_gaps(
    snapshot: ParcelArcGISCapabilitySnapshot,
) -> list[ParcelArcGISAcquisitionGap]:
    checks = (
        (
            snapshot.supports_query,
            ParcelArcGISAcquisitionGapCode.QUERY_NOT_ADVERTISED,
            "The layer metadata does not advertise Query capability.",
            "replace or re-verify the source layer",
        ),
        (
            snapshot.supports_count,
            ParcelArcGISAcquisitionGapCode.COUNT_NOT_ADVERTISED,
            "The layer metadata does not advertise count/statistics support.",
            "verify a supported count strategy before acquisition",
        ),
        (
            snapshot.supports_order_by,
            ParcelArcGISAcquisitionGapCode.ORDERING_NOT_ADVERTISED,
            "The layer metadata does not advertise ordered queries.",
            "do not paginate without a stable server-side order",
        ),
        (
            snapshot.supports_pagination,
            ParcelArcGISAcquisitionGapCode.PAGINATION_NOT_ADVERTISED,
            "The layer metadata does not advertise pagination.",
            "verify an object-ID batch strategy or replace the source",
        ),
        (
            snapshot.object_id_is_unique,
            ParcelArcGISAcquisitionGapCode.UNIQUE_OBJECT_ID_UNVERIFIED,
            "The metadata does not prove a unique object ID field.",
            "verify a stable unique cursor before page retrieval",
        ),
    )
    return [
        _gap(code, explanation, next_action)
        for passed, code, explanation, next_action in checks
        if not passed
    ]


def _page_sequence_is_valid(
    plan: ParcelArcGISProbePlan,
    initial: ParcelArcGISProbeObservation,
    next_page: ParcelArcGISProbeObservation,
    replay: ParcelArcGISProbeObservation,
    expected_count: int | None,
) -> bool:
    if initial.response_digest != replay.response_digest:
        return False
    if set(initial.object_ids) & set(next_page.object_ids):
        return False
    combined = initial.object_ids + next_page.object_ids
    if combined != tuple(sorted(set(combined))):
        return False
    if expected_count is None:
        return False
    expected_initial = min(plan.sample_size, expected_count)
    expected_next = min(plan.sample_size, max(expected_count - plan.sample_size, 0))
    if (
        expected_count > plan.sample_size
        and initial.exceeded_transfer_limit is not True
    ):
        return False
    if (
        expected_count > plan.sample_size * 2
        and next_page.exceeded_transfer_limit is not True
    ):
        return False
    return (
        len(initial.object_ids) == expected_initial
        and len(next_page.object_ids) == expected_next
    )


def _require_plan_scope(
    snapshot: ParcelArcGISCapabilitySnapshot,
    plan: ParcelArcGISProbePlan,
) -> None:
    if (
        plan.snapshot_id != snapshot.snapshot_id
        or plan.profile_id != snapshot.profile_id
        or plan.source_key != snapshot.source_key
        or plan.county != snapshot.county
    ):
        raise ValueError("ArcGIS probe plan scope does not match capability snapshot")
    if any(
        request.object_id_field != snapshot.object_id_field
        or request.schema_fingerprint != snapshot.schema_fingerprint
        for request in plan.requests
    ):
        raise ValueError("ArcGIS probe requests do not match capability schema")


def _require_manifest_scope(
    snapshot: ParcelArcGISCapabilitySnapshot,
    count_observation: ParcelArcGISProbeObservation | None,
    manifest: ParcelArcGISBulkManifest,
) -> None:
    if (
        manifest.snapshot_id != snapshot.snapshot_id
        or manifest.profile_id != snapshot.profile_id
        or manifest.source_key != snapshot.source_key
        or manifest.county != snapshot.county
        or manifest.schema_fingerprint != snapshot.schema_fingerprint
    ):
        raise ValueError("ArcGIS bulk manifest scope does not match capability snapshot")
    if count_observation is None or count_observation.total_count is None:
        raise ValueError("ArcGIS bulk manifest requires a bound count observation")
    if manifest.starting_count != count_observation.total_count:
        raise ValueError("ArcGIS bulk manifest does not reconcile to the probe count")


def _status_for_gaps(
    gaps: tuple[ParcelArcGISAcquisitionGap, ...],
) -> ParcelArcGISAcquisitionStatus:
    blockers = {
        ParcelArcGISAcquisitionGapCode.QUERY_NOT_ADVERTISED,
        ParcelArcGISAcquisitionGapCode.COUNT_NOT_ADVERTISED,
        ParcelArcGISAcquisitionGapCode.ORDERING_NOT_ADVERTISED,
        ParcelArcGISAcquisitionGapCode.PAGINATION_NOT_ADVERTISED,
        ParcelArcGISAcquisitionGapCode.UNIQUE_OBJECT_ID_UNVERIFIED,
        ParcelArcGISAcquisitionGapCode.SCHEMA_DRIFT,
        ParcelArcGISAcquisitionGapCode.PAGE_SEQUENCE_INVALID,
    }
    codes = {gap.code for gap in gaps}
    if codes & blockers:
        return ParcelArcGISAcquisitionStatus.BLOCKED
    if not gaps:
        return ParcelArcGISAcquisitionStatus.BULK_REHEARSAL_VERIFIED
    if codes == {ParcelArcGISAcquisitionGapCode.BULK_REHEARSAL_MISSING}:
        return ParcelArcGISAcquisitionStatus.BOUNDED_QUERY_VERIFIED
    return ParcelArcGISAcquisitionStatus.METADATA_ONLY


def _gap(
    code: ParcelArcGISAcquisitionGapCode,
    explanation: str,
    next_action: str,
) -> ParcelArcGISAcquisitionGap:
    return ParcelArcGISAcquisitionGap(
        code=code,
        explanation=explanation,
        next_action=next_action,
    )


def _parse_field_definition(payload: object) -> ParcelArcGISFieldDefinition:
    if not isinstance(payload, dict):
        raise ValueError("ArcGIS field definitions must be JSON objects")
    name = payload.get("name")
    field_type = payload.get("type")
    if not isinstance(name, str) or not name:
        raise ValueError("ArcGIS field definitions require a name")
    if not isinstance(field_type, str) or not field_type:
        raise ValueError("ArcGIS field definitions require a type")
    nullable = payload.get("nullable")
    if nullable is not None and not isinstance(nullable, bool):
        raise ValueError("ArcGIS field nullable must be boolean when present")
    length = payload.get("length")
    if length is not None and (isinstance(length, bool) or not isinstance(length, int)):
        raise ValueError("ArcGIS field length must be an integer when present")
    return ParcelArcGISFieldDefinition(
        name=name,
        field_type=field_type,
        nullable=nullable,
        length=length,
    )


def _object_id_field(
    metadata: dict[str, Any],
    fields: tuple[ParcelArcGISFieldDefinition, ...],
) -> str:
    explicit = metadata.get("objectIdField")
    if isinstance(explicit, str) and explicit:
        return explicit
    candidates = [
        field.name for field in fields if field.field_type == "esriFieldTypeOID"
    ]
    if len(candidates) != 1:
        raise ValueError("ArcGIS metadata must identify exactly one object ID field")
    return candidates[0]


def _object_id_is_unique(metadata: dict[str, Any], object_id_field: str) -> bool:
    unique_id = metadata.get("uniqueIdField")
    if (
        isinstance(unique_id, dict)
        and str(unique_id.get("name", "")).casefold() == object_id_field.casefold()
        and unique_id.get("isSystemMaintained") is True
    ):
        return True
    indexes = metadata.get("indexes")
    if not isinstance(indexes, list):
        return False
    return any(
        isinstance(index, dict)
        and str(index.get("fields", "")).strip().casefold()
        == object_id_field.casefold()
        and index.get("isUnique") is True
        for index in indexes
    )


def _spatial_reference(metadata: dict[str, Any]) -> str:
    value = metadata.get("spatialReference")
    if not isinstance(value, dict):
        raise ValueError("ArcGIS metadata requires a spatial reference")
    wkid = value.get("wkid")
    latest = value.get("latestWkid", wkid)
    if isinstance(wkid, bool) or not isinstance(wkid, int):
        raise ValueError("ArcGIS spatial reference WKID must be an integer")
    if isinstance(latest, bool) or not isinstance(latest, int):
        raise ValueError("ArcGIS latest spatial reference WKID must be an integer")
    return f"EPSG:{latest} (ArcGIS WKID {wkid})"


def _required_string(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"ArcGIS metadata requires {key}")
    return value


def _service_version(payload: dict[str, Any]) -> str:
    value = payload.get("currentVersion")
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError("ArcGIS metadata requires currentVersion")
    text = str(value).strip()
    if not text:
        raise ValueError("ArcGIS metadata requires currentVersion")
    return text


def _required_int(payload: dict[str, Any], key: str, *, minimum: int) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"ArcGIS payload requires integer {key} >= {minimum}")
    return value


def _require_aware(value: datetime, label: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")


def _san_bernardino_metadata_projection() -> dict[str, Any]:
    return {
        "currentVersion": 12,
        "geometryType": "esriGeometryPolygon",
        "spatialReference": {"wkid": 102100, "latestWkid": 3857},
        "objectIdField": "OBJECTID",
        "uniqueIdField": {"name": "OBJECTID", "isSystemMaintained": True},
        "maxRecordCount": 1000,
        "capabilities": "Query",
        "supportsStatistics": True,
        "supportedQueryFormats": "JSON, geoJSON, PBF",
        "advancedQueryCapabilities": {
            "supportsStatistics": True,
            "supportsOrderBy": True,
            "supportsPagination": True,
        },
        "fields": [
            _field("OBJECTID", "esriFieldTypeOID", nullable=False),
            _field("ParcelNumber", "esriFieldTypeString", length=9),
            _field("OwnerName", "esriFieldTypeString", length=36),
            _field("LandValue", "esriFieldTypeString", length=14),
            _field("ImprovementValue", "esriFieldTypeString", length=14),
            _field("PersonalPropertyValue", "esriFieldTypeString", length=14),
            _field("ExemptionValue", "esriFieldTypeString", length=14),
            _field("HomeOwnerExemption", "esriFieldTypeString", length=1),
            _field("Acreage", "esriFieldTypeDouble"),
            _field("TaxStatus", "esriFieldTypeString", length=50),
            _field("TaxRateArea", "esriFieldTypeString", length=7),
            _field("Zoning", "esriFieldTypeString", length=54),
            _field("ZoningDescription", "esriFieldTypeString", length=128),
            _field("Jurisdiction", "esriFieldTypeString", length=54),
            _field("JurisdictionURL", "esriFieldTypeString", length=80),
            _field("BaseYear", "esriFieldTypeString", length=4),
            _field("PageMap", "esriFieldTypeString", length=6),
            _field("AssessDescription", "esriFieldTypeString", length=72),
            _field("AssessClass", "esriFieldTypeString", length=72),
            _field("Shape__Area", "esriFieldTypeDouble"),
            _field("Shape__Length", "esriFieldTypeDouble"),
        ],
    }


def _riverside_metadata_projection() -> dict[str, Any]:
    return {
        "currentVersion": 11.5,
        "geometryType": "esriGeometryPolygon",
        "spatialReference": {"wkid": 102646, "latestWkid": 2230},
        "maxRecordCount": 2000,
        "capabilities": "Map,Query,Data",
        "supportsStatistics": True,
        "supportedQueryFormats": "JSON, geoJSON, PBF",
        "advancedQueryCapabilities": {
            "supportsStatistics": True,
            "supportsOrderBy": True,
            "supportsPagination": True,
        },
        "indexes": [
            {"fields": "OBJECTID", "isUnique": True},
            {"fields": "APN", "isUnique": False},
        ],
        "fields": [
            _field("OBJECTID", "esriFieldTypeOID", nullable=None),
            _field("APN", "esriFieldTypeString", nullable=None, length=32),
            _field("FLAG", "esriFieldTypeString", nullable=None, length=2),
            _field("MAIL_STREET", "esriFieldTypeString", nullable=None, length=64),
            _field("MAIL_CITY", "esriFieldTypeString", nullable=None, length=48),
            _field("SITUS_STREET", "esriFieldTypeString", nullable=None, length=64),
            _field("SITUS_CITY", "esriFieldTypeString", nullable=None, length=48),
            _field("STREET_NUMBER", "esriFieldTypeInteger", nullable=None),
            _field(
                "STREET_PREDIRECTION",
                "esriFieldTypeString",
                nullable=None,
                length=2,
            ),
            _field("STREET_NAME", "esriFieldTypeString", nullable=None, length=64),
            _field("STREET_TYPE", "esriFieldTypeString", nullable=None, length=8),
            _field("STREET_SUFFIX", "esriFieldTypeString", nullable=None, length=16),
            _field("UNIT_NUMBER", "esriFieldTypeString", nullable=None, length=8),
            _field("CITY", "esriFieldTypeString", nullable=None, length=32),
            _field("ZIP_CODE", "esriFieldTypeString", nullable=None, length=16),
            _field("CLASS_CODE", "esriFieldTypeString", nullable=None, length=64),
            _field("MULTIPLE", "esriFieldTypeString", nullable=None, length=64),
            _field(
                "SUBDIVISION_NAME",
                "esriFieldTypeString",
                nullable=None,
                length=64,
            ),
            _field("ACREAGE", "esriFieldTypeDouble", nullable=None),
            _field(
                "RECORDER_MAP_TYPE",
                "esriFieldTypeString",
                nullable=None,
                length=16,
            ),
            _field("BOOK", "esriFieldTypeString", nullable=None, length=4),
            _field("PAGE", "esriFieldTypeString", nullable=None, length=4),
            _field("MAP_BOOK_PAGE", "esriFieldTypeString", nullable=None, length=16),
            _field("COUNTY_CODE", "esriFieldTypeString", nullable=None, length=2),
            _field("LOT_TYPE", "esriFieldTypeString", nullable=None, length=16),
            _field("LOT", "esriFieldTypeString", nullable=None, length=64),
            _field("BLOCK", "esriFieldTypeString", nullable=None, length=64),
            _field("CAME_FROM", "esriFieldTypeString", nullable=None, length=2000),
            _field("TAX_RATE_AREA", "esriFieldTypeString", nullable=None, length=6),
            _field("LAND", "esriFieldTypeDouble", nullable=None),
            _field("STRUCTURES", "esriFieldTypeDouble", nullable=None),
            _field("SHAPE", "esriFieldTypeGeometry", nullable=None),
            _field("SHAPE.STArea()", "esriFieldTypeDouble", nullable=None),
            _field("SHAPE.STLength()", "esriFieldTypeDouble", nullable=None),
        ],
    }


def _field(
    name: str,
    field_type: str,
    *,
    nullable: bool | None = True,
    length: int | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": name,
        "type": field_type,
        "nullable": nullable,
    }
    if length is not None:
        payload["length"] = length
    return payload
