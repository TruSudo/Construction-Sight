from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from constructionsight.parcel_source_acquisition import (
    get_official_arcgis_capability_snapshots,
)
from constructionsight.parcel_source_bulk_rehearsal_authorization import (
    build_arcgis_bulk_rehearsal_authorization,
    preflight_arcgis_bulk_rehearsal_authorization,
)
from constructionsight.parcel_source_bulk_rehearsal_authorization_models import (
    ParcelArcGISBulkRehearsalAuthorization,
)
from constructionsight.parcel_source_bulk_rehearsal_http import (
    build_arcgis_bulk_rehearsal_plan,
)

_ISSUED_AT = datetime(2026, 7, 15, 8, 0, tzinfo=UTC)
_NOT_BEFORE = _ISSUED_AT + timedelta(minutes=5)
_EXPIRES_AT = _NOT_BEFORE + timedelta(hours=6)
_NONCE = "a" * 64


def _snapshot(index: int = 0):
    return get_official_arcgis_capability_snapshots()[index]


def _plan(index: int = 0):
    snapshot = _snapshot(index)
    return build_arcgis_bulk_rehearsal_plan(
        snapshot,
        generated_at=_ISSUED_AT - timedelta(minutes=1),
        page_size=min(1000, snapshot.max_record_count),
        checkpoint_after_pages=1,
        injected_retry_page_index=1,
        max_attempts=3,
        retry_delays_seconds=(0.25, 1.0),
    )


def _authorization(**overrides):
    values = {
        "execution_nonce": _NONCE,
        "issued_by": "Tyler Alston",
        "authorization_reason": (
            "Collect one retained complete-rehearsal proof for independent review."
        ),
        "issued_at": _ISSUED_AT,
        "not_before": _NOT_BEFORE,
        "expires_at": _EXPIRES_AT,
        "authorize_live_rehearsal": True,
    }
    values.update(overrides)
    return build_arcgis_bulk_rehearsal_authorization(
        _snapshot(),
        _plan(),
        **values,
    )


def test_authorization_is_deterministic_exact_plan_and_nonproduction() -> None:
    first = _authorization()
    second = _authorization()

    assert first == second
    assert first.authorization_id.startswith("parcel-arcgis-bulk-rehearsal-authorization:")
    assert first.snapshot_id == _snapshot().snapshot_id
    assert first.plan_id == _plan().plan_id
    assert first.execution_limit == 1
    assert first.count_request_limit == 2
    assert first.live_rehearsal_execution_authorized is True
    assert first.exact_response_retention_required is True
    assert first.durable_checkpoint_required is True
    assert first.portable_proof_bundle_required is True
    assert first.independent_verification_required is True
    assert first.parcel_import_authorized is False
    assert first.source_profile_promotion_authorized is False
    assert first.recurring_execution_authorized is False
    assert first.production_bulk_run_authorized is False


def test_authorization_builder_requires_explicit_operator_decision() -> None:
    with pytest.raises(ValueError, match="explicit live rehearsal authorization"):
        _authorization(authorize_live_rehearsal=False)


def test_preflight_proves_current_unused_exact_authorization() -> None:
    authorization = _authorization()
    checked_at = _NOT_BEFORE + timedelta(minutes=1)

    preflight = preflight_arcgis_bulk_rehearsal_authorization(
        _snapshot(),
        _plan(),
        authorization,
        expected_authorization_id=authorization.authorization_id,
        checked_at=checked_at,
    )

    assert preflight.preflight_id.startswith("parcel-arcgis-bulk-rehearsal-preflight:")
    assert preflight.authorization_id == authorization.authorization_id
    assert preflight.checked_at == checked_at
    assert preflight.valid_until == authorization.expires_at
    assert preflight.exact_snapshot_verified is True
    assert preflight.exact_plan_verified is True
    assert preflight.authorization_integrity_verified is True
    assert preflight.authorization_window_verified is True
    assert preflight.single_use_available is True
    assert preflight.retention_requirements_verified is True
    assert preflight.ready_for_single_live_rehearsal is True
    assert preflight.production_bulk_run_authorized is False


def test_preflight_rejects_wrong_identity_future_expired_and_consumed() -> None:
    authorization = _authorization()

    with pytest.raises(ValueError, match="expected.*identity"):
        preflight_arcgis_bulk_rehearsal_authorization(
            _snapshot(),
            _plan(),
            authorization,
            expected_authorization_id=(
                "parcel-arcgis-bulk-rehearsal-authorization:" + ("0" * 64)
            ),
            checked_at=_NOT_BEFORE,
        )
    with pytest.raises(ValueError, match="not effective yet"):
        preflight_arcgis_bulk_rehearsal_authorization(
            _snapshot(),
            _plan(),
            authorization,
            expected_authorization_id=authorization.authorization_id,
            checked_at=_NOT_BEFORE - timedelta(microseconds=1),
        )
    with pytest.raises(ValueError, match="expired"):
        preflight_arcgis_bulk_rehearsal_authorization(
            _snapshot(),
            _plan(),
            authorization,
            expected_authorization_id=authorization.authorization_id,
            checked_at=_EXPIRES_AT,
        )
    with pytest.raises(ValueError, match="already been consumed"):
        preflight_arcgis_bulk_rehearsal_authorization(
            _snapshot(),
            _plan(),
            authorization,
            expected_authorization_id=authorization.authorization_id,
            checked_at=_NOT_BEFORE,
            used_authorization_ids={authorization.authorization_id},
        )


def test_authorization_rejects_long_window_and_plan_mismatch() -> None:
    with pytest.raises(ValueError, match="cannot exceed 24 hours"):
        _authorization(expires_at=_NOT_BEFORE + timedelta(hours=24, seconds=1))

    authorization = _authorization()
    with pytest.raises(ValueError, match="does not match the exact plan"):
        preflight_arcgis_bulk_rehearsal_authorization(
            _snapshot(1),
            _plan(1),
            authorization,
            expected_authorization_id=authorization.authorization_id,
            checked_at=_NOT_BEFORE,
        )


def test_authorization_rejects_tampering_and_unsafe_authority_expansion() -> None:
    authorization = _authorization()
    tampered = authorization.to_dict()
    tampered["page_size"] = authorization.page_size + 1
    with pytest.raises(ValueError, match="ID does not match"):
        ParcelArcGISBulkRehearsalAuthorization.model_validate(tampered)

    expanded = authorization.to_dict()
    expanded["parcel_import_authorized"] = True
    with pytest.raises(ValueError, match="literal_error|False"):
        ParcelArcGISBulkRehearsalAuthorization.model_validate(expanded)


def test_authorization_rejects_bad_chronology_and_naive_preflight_time() -> None:
    with pytest.raises(ValueError, match="issued_at cannot follow"):
        _authorization(issued_at=_NOT_BEFORE + timedelta(seconds=1))
    with pytest.raises(ValueError, match="not_before must precede"):
        _authorization(expires_at=_NOT_BEFORE)

    authorization = _authorization()
    with pytest.raises(ValueError, match="timezone-aware"):
        preflight_arcgis_bulk_rehearsal_authorization(
            _snapshot(),
            _plan(),
            authorization,
            expected_authorization_id=authorization.authorization_id,
            checked_at=datetime(2026, 7, 15, 8, 6),
        )
