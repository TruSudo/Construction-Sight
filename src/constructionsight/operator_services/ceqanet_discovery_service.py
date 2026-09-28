"""Authorized operator boundary for CEQAnet discovery."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from constructionsight.authorization_decision_models import authorization_digest
from constructionsight.ceqanet_discovery_http import (
    CEQANET_DISCOVERY_POLICY,
    CeqanetDiscoveryResult,
)
from constructionsight.ceqanet_discovery_service import discover_ceqanet_public_search
from constructionsight.effect_consumption import _execute_owned_effect, trusted_utc_now
from constructionsight.effect_consumption_models import EffectReplayPolicy
from constructionsight.http_transport_models import HttpFailureKind
from constructionsight.local_operator_authorization import (
    LocalAuthorizationResult,
    authorize_local_operator_operation,
)


class _DiscoveryPayload(BaseModel):
    url: str
    reachable: bool
    status_code: int | None
    advanced_search_available: bool
    sch_number_field_detected: bool
    document_type_field_detected: bool
    date_field_detected: bool
    lead_agency_field_detected: bool
    failure_kind: HttpFailureKind
    notes: str | None


@dataclass(frozen=True)
class AuthorizedCeqanetDiscoveryResult:
    """One retained discovery result plus the authority consumed to obtain it."""

    result: CeqanetDiscoveryResult
    authorization: LocalAuthorizationResult


def _encode_discovery(result: CeqanetDiscoveryResult) -> dict[str, Any]:
    payload = _DiscoveryPayload(
        url=result.url,
        reachable=result.reachable,
        status_code=result.status_code,
        advanced_search_available=result.advanced_search_available,
        sch_number_field_detected=result.sch_number_field_detected,
        document_type_field_detected=result.document_type_field_detected,
        date_field_detected=result.date_field_detected,
        lead_agency_field_detected=result.lead_agency_field_detected,
        failure_kind=result.failure_kind,
        notes=result.notes,
    )
    return payload.model_dump(mode="json")


def _decode_discovery(payload: dict[str, Any]) -> CeqanetDiscoveryResult:
    validated = _DiscoveryPayload.model_validate(payload)
    return CeqanetDiscoveryResult(
        url=validated.url,
        reachable=validated.reachable,
        status_code=validated.status_code,
        advanced_search_available=validated.advanced_search_available,
        sch_number_field_detected=validated.sch_number_field_detected,
        document_type_field_detected=validated.document_type_field_detected,
        date_field_detected=validated.date_field_detected,
        lead_agency_field_detected=validated.lead_agency_field_detected,
        failure_kind=validated.failure_kind,
        notes=validated.notes,
    )


def execute_authorized_ceqanet_discovery(
    *,
    execute_live: bool,
    authorization_reason: str,
    operator_id: str | None = None,
) -> AuthorizedCeqanetDiscoveryResult:
    """Authorize and consume one bounded CEQAnet discovery request for the UTC date."""

    authorized_at = trusted_utc_now()
    authorized_date = authorized_at.date()
    state_identity = authorization_digest(
        "ceqanet-discovery-state",
        {
            "policy_id": CEQANET_DISCOVERY_POLICY.policy_id,
            "request_url": str(CEQANET_DISCOVERY_POLICY.allowed_request_urls[0]),
            "utc_date": authorized_date.isoformat(),
        },
    )
    resource_id = authorization_digest(
        "ceqanet-discovery-resource",
        {
            "policy_id": CEQANET_DISCOVERY_POLICY.policy_id,
            "utc_date": authorized_date.isoformat(),
        },
    )
    exact_scope = tuple(
        sorted(
            {
                "method:GET",
                f"policy:{CEQANET_DISCOVERY_POLICY.policy_id}",
                "redirects:denied",
                "retries:0",
                f"utc-date:{authorized_date.isoformat()}",
                f"url:{CEQANET_DISCOVERY_POLICY.allowed_request_urls[0]}",
            },
            key=str.casefold,
        )
    )
    authorization = authorize_local_operator_operation(
        action="discover-ceqanet-public-search",
        resource_type="ceqanet-public-search-surface",
        resource_id=resource_id,
        exact_scope=exact_scope,
        current_state_identity=state_identity,
        expected_identity=state_identity,
        granted_authority=("execute one bounded CEQANet discovery GET",),
        denied_authority=tuple(
            sorted(
                {
                    "access-control bypass",
                    "credential use",
                    "persistence mutation",
                    "redirect following",
                    "repeat same-date discovery",
                    "retry",
                    "source promotion",
                },
                key=str.casefold,
            )
        ),
        reason=authorization_reason,
        caller_confirmation=execute_live,
        limitations=tuple(
            sorted(
                {
                    "discovery does not authorize registry mutation",
                    "local operator identity is not authentication",
                    "one durable discovery allowance per UTC date",
                },
                key=str.casefold,
            )
        ),
        operator_id=operator_id,
        current_revocation_identity=state_identity,
    )

    def execute(_trusted_at: datetime) -> CeqanetDiscoveryResult:
        return discover_ceqanet_public_search()

    result = _execute_owned_effect(
        authorization,
        allowance_identity=authorization_digest(
            "ceqanet-discovery-daily-allowance",
            {
                "policy_id": CEQANET_DISCOVERY_POLICY.policy_id,
                "utc_date": authorized_date.isoformat(),
            },
        ),
        content_identity=state_identity,
        implementation_id=(
            "constructionsight.ceqanet_discovery_service.discover_ceqanet_public_search"
        ),
        replay_policy=EffectReplayPolicy.EXACT,
        effect=execute,
        encode_result=_encode_discovery,
        decode_result=lambda payload: _decode_discovery(dict(payload)),
        required_utc_date=authorized_date,
    )
    return AuthorizedCeqanetDiscoveryResult(result=result, authorization=authorization)
