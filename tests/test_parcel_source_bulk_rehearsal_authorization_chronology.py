from __future__ import annotations

from datetime import timedelta

import pytest

from constructionsight.parcel_source_acquisition import (
    get_official_arcgis_capability_snapshots,
)
from constructionsight.parcel_source_bulk_rehearsal_authorization import (
    build_arcgis_bulk_rehearsal_authorization,
)
from constructionsight.parcel_source_bulk_rehearsal_http import (
    build_arcgis_bulk_rehearsal_plan,
)


def _authorization_inputs():
    snapshot = get_official_arcgis_capability_snapshots()[0]
    generated_at = snapshot.observed_at + timedelta(minutes=1)
    plan = build_arcgis_bulk_rehearsal_plan(
        snapshot,
        generated_at=generated_at,
        page_size=min(1000, snapshot.max_record_count),
        checkpoint_after_pages=1,
        injected_retry_page_index=1,
        max_attempts=3,
        retry_delays_seconds=(0.25, 1.0),
    )
    issued_at = generated_at + timedelta(minutes=1)
    return snapshot, plan, issued_at


def test_authorization_binds_snapshot_and_plan_timestamps() -> None:
    snapshot, plan, issued_at = _authorization_inputs()

    authorization = build_arcgis_bulk_rehearsal_authorization(
        snapshot,
        plan,
        execution_nonce="b" * 64,
        issued_by="Tyler Alston",
        authorization_reason="Authorize one retained rehearsal proof.",
        issued_at=issued_at,
        not_before=issued_at,
        expires_at=issued_at + timedelta(hours=1),
        authorize_live_rehearsal=True,
    )

    assert authorization.snapshot_observed_at == snapshot.observed_at
    assert authorization.plan_generated_at == plan.generated_at


def test_authorization_rejects_plan_predating_capability_snapshot() -> None:
    snapshot = get_official_arcgis_capability_snapshots()[0]
    plan = build_arcgis_bulk_rehearsal_plan(
        snapshot,
        generated_at=snapshot.observed_at - timedelta(seconds=1),
        page_size=min(1000, snapshot.max_record_count),
        checkpoint_after_pages=1,
        injected_retry_page_index=1,
        max_attempts=3,
        retry_delays_seconds=(0.25, 1.0),
    )
    issued_at = snapshot.observed_at + timedelta(minutes=1)

    with pytest.raises(ValueError, match="plan cannot predate"):
        build_arcgis_bulk_rehearsal_authorization(
            snapshot,
            plan,
            execution_nonce="c" * 64,
            issued_by="Tyler Alston",
            authorization_reason="Reject stale plan chronology.",
            issued_at=issued_at,
            not_before=issued_at,
            expires_at=issued_at + timedelta(hours=1),
            authorize_live_rehearsal=True,
        )


def test_authorization_rejects_issuance_before_plan_generation() -> None:
    snapshot, plan, _issued_at = _authorization_inputs()
    issued_at = plan.generated_at - timedelta(seconds=1)

    with pytest.raises(ValueError, match="issuance cannot predate"):
        build_arcgis_bulk_rehearsal_authorization(
            snapshot,
            plan,
            execution_nonce="d" * 64,
            issued_by="Tyler Alston",
            authorization_reason="Reject premature authorization issuance.",
            issued_at=issued_at,
            not_before=plan.generated_at,
            expires_at=plan.generated_at + timedelta(hours=1),
            authorize_live_rehearsal=True,
        )
