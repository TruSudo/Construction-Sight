"""Native review of the original bounded CEQAnet discovery boundary.

Preview is fully offline. Execution delegates to the preserved governed one-shot
discovery service only after exact same-source, same-day manual confirmation.
It does not create sources, persist observations, or enable source collection.
"""

from __future__ import annotations

from typing import Any

from constructionsight.authorization_decision_models import authorization_digest
from constructionsight.ceqanet_discovery_http import CEQANET_DISCOVERY_POLICY
from constructionsight.effect_consumption import trusted_utc_now
from constructionsight.operator_services import ceqanet_discovery_service

_DISCOVERY_URL = str(CEQANET_DISCOVERY_POLICY.allowed_request_urls[0])


def preview_original_ceqanet_discovery() -> dict[str, Any]:
    """Describe exact original request and today's authorization boundary without HTTP."""
    utc_date = trusted_utc_now().date().isoformat()
    expected = authorization_digest(
        "ceqanet-discovery-state",
        {
            "policy_id": CEQANET_DISCOVERY_POLICY.policy_id,
            "request_url": _DISCOVERY_URL,
            "utc_date": utc_date,
        },
    )
    return {
        "schema_version": "constructionsight.native-ceqanet-discovery-preview/v1",
        "policy_id": CEQANET_DISCOVERY_POLICY.policy_id,
        "request_url": _DISCOVERY_URL,
        "expected_state_digest": expected,
        "utc_date": utc_date,
        "allowed_methods": ["GET"],
        "max_response_bytes": CEQANET_DISCOVERY_POLICY.max_response_bytes,
        "redirects_followed": False,
        "retries": 0,
        "operator_confirmation_required": True,
        "one_attempt_per_utc_date": True,
        "network_executed": False,
        "source_registry_mutated": False,
        "source_collection_enabled": False,
        "commercial_authority_granted": False,
        "meaning": (
            "Read-only review of the original CS-NET-001 public CEQAnet search "
            "discovery. Only a separately confirmed bounded one-shot discovery "
            "can perform network access. This is not source verification, "
            "recurring ingestion, or authorization to contact a project."
        ),
    }


def execute_reviewed_original_ceqanet_discovery(payload: dict[str, Any]) -> dict[str, Any]:
    """Fail closed on substitutions before consuming original source authorization."""
    if set(payload) != {
        "policy_id", "request_url", "expected_state_digest", "utc_date",
        "review_reason", "caller_confirmation",
    }:
        raise ValueError("exact CEQAnet discovery confirmation fields required")
    preview = preview_original_ceqanet_discovery()
    if any(payload[field] != preview[field] for field in (
        "policy_id", "request_url", "expected_state_digest", "utc_date",
    )):
        raise ValueError("CEQAnet discovery policy or UTC date changed; review again")
    reason = payload["review_reason"]
    if (
        not isinstance(reason, str) or not 10 <= len(reason.strip()) <= 2000
        or payload["caller_confirmation"] is not True
    ):
        raise ValueError("explicit reason and one-shot CEQAnet discovery consent required")
    executed = ceqanet_discovery_service.execute_authorized_ceqanet_discovery(
        execute_live=True,
        authorization_reason=reason.strip(),
    )
    return {
        "schema_version": "constructionsight.native-ceqanet-discovery-result/v1",
        "policy_id": preview["policy_id"],
        "request_url": preview["request_url"],
        "reviewed_state_digest": preview["expected_state_digest"],
        "utc_date": preview["utc_date"],
        "original_discovery_result": ceqanet_discovery_service._encode_discovery(
            executed.result
        ),
        "original_authorization": executed.authorization.to_dict(),
        "source_registry_mutated": False,
        "source_collection_enabled": False,
        "recurring_collection_enabled": False,
        "source_promoted": False,
        "commercial_authority_granted": False,
        "meaning": (
            "Original one-shot bounded CEQAnet public-search discovery evidence. "
            "No source status or independent verification was established; "
            "no records were ingested, no recurrence or contact was authorized."
        ),
    }
