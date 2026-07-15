from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from pydantic import ValidationError

from constructionsight.authorization_decision import (
    AuthorizationDeniedError,
    AuthorizationUseLedger,
    authorize_and_claim,
    build_authorization_decision,
)
from constructionsight.authorization_decision_models import (
    AuthorizationDecision,
    AuthorizationReusePolicy,
    authorization_digest,
)


def _decision(
    *,
    reuse_policy: AuthorizationReusePolicy = AuthorizationReusePolicy.SINGLE_USE,
) -> AuthorizationDecision:
    issued_at = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)
    grants = ("apply exact status transition",)
    if reuse_policy is AuthorizationReusePolicy.EXACT_REPLAY:
        grants = (
            "apply exact status transition",
            "exact replay of apply-status",
        )
    return build_authorization_decision(
        actor_id="operator:tyler",
        action="apply-status",
        resource_type="source-record",
        resource_id="source:county-parcel",
        exact_scope=("field:status", "transition:verified-candidate"),
        current_state_identity="state:abc123",
        expected_identity="state:abc123",
        granted_authority=grants,
        denied_authority=(
            "change source identity",
            "expand field scope",
            "send outreach",
        ),
        reason="Apply the independently reviewed exact status transition.",
        issued_at=issued_at,
        not_before=issued_at,
        expires_at=issued_at + timedelta(minutes=15),
        reuse_policy=reuse_policy,
        revocation_identity="revocation:none:v1",
        audit_identity="audit:status-transition:v1",
        caller_confirmation=True,
        limitations=(
            "local CLI operator identity is not authentication",
            "no hosted or cross-process claim is established",
        ),
    )


def _claim(
    decision: AuthorizationDecision,
    ledger: AuthorizationUseLedger,
    *,
    replay_identity: str = "result:1",
):
    return authorize_and_claim(
        decision,
        actor_id="operator:tyler",
        action="apply-status",
        resource_type="source-record",
        resource_id="source:county-parcel",
        exact_scope=("field:status", "transition:verified-candidate"),
        current_state_identity="state:abc123",
        current_revocation_identity="revocation:none:v1",
        replay_identity=replay_identity,
        checked_at=datetime(2026, 7, 15, 12, 5, tzinfo=UTC),
        ledger=ledger,
    )


def test_builder_constructs_digest_bound_decision_without_placeholder_validation() -> None:
    decision = _decision()

    assert decision.decision_id == authorization_digest(
        "authorization-decision",
        decision.identity_payload(),
    )
    assert decision.decision_id != "authorization-decision:" + "0" * 64


def test_preflight_constructs_digest_bound_identity_without_placeholder_validation() -> None:
    preflight = _claim(_decision(), AuthorizationUseLedger())

    assert preflight.preflight_id == authorization_digest(
        "authorization-preflight",
        preflight.identity_payload(),
    )
    assert preflight.preflight_id != "authorization-preflight:" + "0" * 64


def test_decision_identity_binds_caller_confirmation_but_boolean_is_not_authority() -> None:
    confirmed = _decision()
    unconfirmed = build_authorization_decision(
        **{
            **confirmed.model_dump(
                exclude={"decision_id", "schema_version", "max_uses", "failure_posture"}
            ),
            "caller_confirmation": False,
        }
    )

    assert confirmed.decision_id != unconfirmed.decision_id
    assert confirmed.exact_scope == unconfirmed.exact_scope
    assert confirmed.granted_authority == unconfirmed.granted_authority
    assert confirmed.denied_authority == unconfirmed.denied_authority


def test_decision_rejects_naive_time_and_stale_issue_state() -> None:
    issued_at = datetime(2026, 7, 15, 12, 0)
    with pytest.raises(ValidationError, match="timezone-aware"):
        build_authorization_decision(
            actor_id="operator:tyler",
            action="apply-status",
            resource_type="source-record",
            resource_id="source:county-parcel",
            exact_scope=("field:status",),
            current_state_identity="state:new",
            expected_identity="state:old",
            granted_authority=("apply exact status transition",),
            denied_authority=("expand field scope",),
            reason="Test stale issue state.",
            issued_at=issued_at,
            not_before=issued_at,
            expires_at=issued_at + timedelta(minutes=1),
            reuse_policy=AuthorizationReusePolicy.SINGLE_USE,
            revocation_identity="revocation:none:v1",
            audit_identity="audit:test",
            caller_confirmation=True,
            limitations=("test only",),
        )


def test_preflight_rejects_expiry_revocation_scope_and_stale_state() -> None:
    decision = _decision()
    base = dict(
        decision=decision,
        actor_id="operator:tyler",
        action="apply-status",
        resource_type="source-record",
        resource_id="source:county-parcel",
        exact_scope=("field:status", "transition:verified-candidate"),
        current_state_identity="state:abc123",
        current_revocation_identity="revocation:none:v1",
        replay_identity="result:1",
        checked_at=datetime(2026, 7, 15, 12, 5, tzinfo=UTC),
        ledger=AuthorizationUseLedger(),
    )
    cases = (
        ({"checked_at": decision.expires_at}, "expired"),
        ({"current_revocation_identity": "revocation:changed"}, "revocation_identity"),
        ({"exact_scope": ("field:status",)}, "exact_scope"),
        ({"current_state_identity": "state:stale"}, "current_state_identity"),
    )
    for update, message in cases:
        with pytest.raises(AuthorizationDeniedError, match=message):
            authorize_and_claim(**{**base, **update})


def test_single_use_claim_allows_only_one_concurrent_caller() -> None:
    decision = _decision()
    ledger = AuthorizationUseLedger()

    def attempt() -> str:
        try:
            return _claim(decision, ledger).preflight_id
        except AuthorizationDeniedError as exc:
            return str(exc)

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _: attempt(), range(24)))

    successful = [value for value in results if value.startswith("authorization-preflight:")]
    denied = [value for value in results if "already consumed" in value]
    assert len(successful) == 1
    assert len(denied) == 23
    assert ledger.is_claimed(decision.decision_id) is True


def test_exact_replay_requires_same_replay_identity_and_repeats_no_effect() -> None:
    decision = _decision(reuse_policy=AuthorizationReusePolicy.EXACT_REPLAY)
    ledger = AuthorizationUseLedger()

    first = _claim(decision, ledger, replay_identity="result:immutable")
    replay = _claim(decision, ledger, replay_identity="result:immutable")

    assert "execute only the exact granted operation" in first.next_action
    assert "without repeating effects" in replay.next_action
    with pytest.raises(AuthorizationDeniedError, match="conflicting replay"):
        _claim(decision, ledger, replay_identity="result:conflict")


def test_tampering_after_validation_is_detected_before_claim() -> None:
    decision = _decision()
    tampered = decision.model_copy(update={"resource_id": "source:other"})

    with pytest.raises(AuthorizationDeniedError, match="integrity"):
        _claim(tampered, AuthorizationUseLedger())
