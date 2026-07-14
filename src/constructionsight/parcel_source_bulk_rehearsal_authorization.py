"""Build and verify single-use live ArcGIS rehearsal authorization."""

from __future__ import annotations

from collections.abc import Collection
from datetime import datetime

from constructionsight.parcel_source_acquisition_models import (
    ParcelArcGISCapabilitySnapshot,
    digest_identity,
)
from constructionsight.parcel_source_bulk_rehearsal_authorization_models import (
    ParcelArcGISBulkRehearsalAuthorization,
    ParcelArcGISBulkRehearsalPreflight,
)
from constructionsight.parcel_source_bulk_rehearsal_http import (
    ParcelArcGISBulkRehearsalPlan,
)

_DEFAULT_LIMITATIONS = (
    "Authorization permits one complete read-only rehearsal only.",
    (
        "Authorization does not permit parcel import, profile promotion, "
        "or recurring execution."
    ),
    "Authorization expires automatically and cannot be reused after one execution.",
    (
        "Every exact response, checkpoint, portable bundle, and independent "
        "verification must be retained."
    ),
)


def build_arcgis_bulk_rehearsal_authorization(
    snapshot: ParcelArcGISCapabilitySnapshot,
    plan: ParcelArcGISBulkRehearsalPlan,
    *,
    execution_nonce: str,
    issued_by: str,
    authorization_reason: str,
    issued_at: datetime,
    not_before: datetime,
    expires_at: datetime,
    authorize_live_rehearsal: bool,
    limitations: tuple[str, ...] = _DEFAULT_LIMITATIONS,
) -> ParcelArcGISBulkRehearsalAuthorization:
    """Issue one exact-plan authorization only after an explicit caller decision."""

    if not authorize_live_rehearsal:
        raise ValueError("explicit live rehearsal authorization is required")
    _require_plan_scope(snapshot, plan)
    canonical_limitations = tuple(sorted(set(limitations), key=str.casefold))
    candidate = ParcelArcGISBulkRehearsalAuthorization.model_construct(
        authorization_id="parcel-arcgis-bulk-rehearsal-authorization:" + ("0" * 64),
        snapshot_id=snapshot.snapshot_id,
        profile_id=snapshot.profile_id,
        plan_id=plan.plan_id,
        source_key=snapshot.source_key,
        county=snapshot.county,
        query_url=plan.query_url,
        object_id_field=snapshot.object_id_field,
        page_size=plan.page_size,
        checkpoint_after_pages=plan.checkpoint_after_pages,
        injected_retry_page_index=plan.injected_retry_page_index,
        max_attempts=plan.max_attempts,
        execution_nonce=execution_nonce,
        issued_by=issued_by,
        authorization_reason=authorization_reason,
        issued_at=issued_at,
        not_before=not_before,
        expires_at=expires_at,
        limitations=canonical_limitations,
    )
    return ParcelArcGISBulkRehearsalAuthorization.model_validate(
        {
            **candidate.to_dict(),
            "authorization_id": digest_identity(
                "parcel-arcgis-bulk-rehearsal-authorization",
                candidate.identity_payload(),
            ),
        }
    )


def preflight_arcgis_bulk_rehearsal_authorization(
    snapshot: ParcelArcGISCapabilitySnapshot,
    plan: ParcelArcGISBulkRehearsalPlan,
    authorization: ParcelArcGISBulkRehearsalAuthorization,
    *,
    expected_authorization_id: str,
    checked_at: datetime,
    used_authorization_ids: Collection[str] = (),
) -> ParcelArcGISBulkRehearsalPreflight:
    """Prove one exact authorization is current, unused, and scope-matched."""

    if expected_authorization_id != authorization.authorization_id:
        raise ValueError("expected ArcGIS rehearsal authorization identity does not match")
    if authorization.authorization_id in used_authorization_ids:
        raise ValueError("ArcGIS rehearsal authorization has already been consumed")
    _require_plan_scope(snapshot, plan)
    _require_authorization_scope(snapshot, plan, authorization)
    if checked_at.tzinfo is None or checked_at.utcoffset() is None:
        raise ValueError("ArcGIS rehearsal preflight checked_at must be timezone-aware")
    if checked_at < authorization.not_before:
        raise ValueError("ArcGIS rehearsal authorization is not effective yet")
    if checked_at >= authorization.expires_at:
        raise ValueError("ArcGIS rehearsal authorization has expired")
    candidate = ParcelArcGISBulkRehearsalPreflight.model_construct(
        preflight_id="parcel-arcgis-bulk-rehearsal-preflight:" + ("0" * 64),
        authorization_id=authorization.authorization_id,
        snapshot_id=snapshot.snapshot_id,
        profile_id=snapshot.profile_id,
        plan_id=plan.plan_id,
        source_key=snapshot.source_key,
        county=snapshot.county,
        checked_at=checked_at,
        valid_until=authorization.expires_at,
        next_action=(
            "execute exactly one rehearsal through the governed HTTP adapter; retain the "
            "checkpoint, every exact response, the portable proof bundle, and independent "
            "verification before recording authorization consumption"
        ),
    )
    return ParcelArcGISBulkRehearsalPreflight.model_validate(
        {
            **candidate.to_dict(),
            "preflight_id": digest_identity(
                "parcel-arcgis-bulk-rehearsal-preflight",
                candidate.identity_payload(),
            ),
        }
    )


def _require_plan_scope(
    snapshot: ParcelArcGISCapabilitySnapshot,
    plan: ParcelArcGISBulkRehearsalPlan,
) -> None:
    expected_query_url = snapshot.layer_url.rstrip("/") + "/query"
    if (
        plan.snapshot_id != snapshot.snapshot_id
        or plan.profile_id != snapshot.profile_id
        or plan.source_key != snapshot.source_key
        or plan.county != snapshot.county
        or plan.query_url != expected_query_url
        or plan.object_id_field != snapshot.object_id_field
        or plan.page_size > snapshot.max_record_count
    ):
        raise ValueError("ArcGIS rehearsal plan does not match the capability snapshot")
    if plan.bulk_run_authorized:
        raise ValueError("ArcGIS rehearsal authorization refuses bulk-authorized plans")


def _require_authorization_scope(
    snapshot: ParcelArcGISCapabilitySnapshot,
    plan: ParcelArcGISBulkRehearsalPlan,
    authorization: ParcelArcGISBulkRehearsalAuthorization,
) -> None:
    expected = (
        snapshot.snapshot_id,
        snapshot.profile_id,
        plan.plan_id,
        snapshot.source_key,
        snapshot.county,
        plan.query_url,
        snapshot.object_id_field,
        plan.page_size,
        plan.checkpoint_after_pages,
        plan.injected_retry_page_index,
        plan.max_attempts,
    )
    actual = (
        authorization.snapshot_id,
        authorization.profile_id,
        authorization.plan_id,
        authorization.source_key,
        authorization.county,
        authorization.query_url,
        authorization.object_id_field,
        authorization.page_size,
        authorization.checkpoint_after_pages,
        authorization.injected_retry_page_index,
        authorization.max_attempts,
    )
    if actual != expected:
        raise ValueError("ArcGIS rehearsal authorization does not match the exact plan")
