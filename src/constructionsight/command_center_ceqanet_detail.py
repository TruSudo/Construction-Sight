"""Native reviewed CEQAnet detail read using original access and execution services.

Every preview is offline. Live requests require operator-supplied, evidence-bound
lawful-access findings and separate exact-preview authorization. Unknown facts fail
closed; source verification and persistent ingestion are never implied.
"""

from __future__ import annotations

from typing import Any

from constructionsight.authorization_decision import AuthorizationDeniedError
from constructionsight.authorization_decision_models import authorization_digest
from constructionsight.ceqanet_detail_http import CEQANET_DETAIL_POLICY
from constructionsight.ceqanet_detail_service import (
    _validated_detail_url,
    execute_authorized_ceqanet_detail,
)
from constructionsight.legal import AccessDecision, SourceAccessProfile, evaluate_access
from constructionsight.local_operator_authorization import resolve_local_operator_id

_FACTS = (
    "requires_login",
    "has_captcha",
    "robots_disallows_collection",
    "terms_disallow_collection",
    "paywalled",
)
_REVIEW_FIELDS = set(_FACTS) | {"access_fact_basis"}
_TIMEOUT = CEQANET_DETAIL_POLICY.read_timeout_seconds
_MAX_BYTES = CEQANET_DETAIL_POLICY.max_response_bytes


def _reviewed_profile(payload: dict[str, Any]) -> tuple[str, SourceAccessProfile]:
    if set(payload) != {"detail_url", "access_review"}:
        raise ValueError("exact CEQAnet detail review fields required")
    url = payload["detail_url"]
    if not isinstance(url, str) or not 1 <= len(url) <= 2048:
        raise ValueError("bounded original CEQAnet detail URL required")
    url = _validated_detail_url(url)
    access = payload["access_review"]
    if not isinstance(access, dict) or set(access) != _REVIEW_FIELDS:
        raise ValueError("complete explicit CEQAnet lawful-access review required")
    for key in _FACTS:
        if access[key] is not None and type(access[key]) is not bool:
            raise ValueError("CEQAnet access restrictions must be true, false or unknown")
    basis = access["access_fact_basis"]
    if basis is not None and (
        not isinstance(basis, str) or len(basis) > 80
        or any(ord(character) < 32 or ord(character) == 127 for character in basis)
    ):
        raise ValueError("CEQAnet access evidence identity is invalid")
    profile = SourceAccessProfile(
        public_url=url,
        requires_login=access["requires_login"],
        has_captcha=access["has_captcha"],
        robots_disallows_collection=access["robots_disallows_collection"],
        terms_disallow_collection=access["terms_disallow_collection"],
        paywalled=access["paywalled"],
        access_fact_basis=basis,
        access_facts_reviewed=basis is not None,
        review_basis="Operator supplied exact source access review identity",
    )
    return url, profile


def preview_original_ceqanet_detail(payload: dict[str, Any]) -> dict[str, Any]:
    """Build a digest-bound, no-network review without inventing lawful-access facts."""
    url, profile = _reviewed_profile(payload)
    access = evaluate_access(profile)
    expected = authorization_digest(
        "native-original-ceqanet-detail-review",
        {
            "policy_id": CEQANET_DETAIL_POLICY.policy_id,
            "detail_url": url,
            "access_review": payload["access_review"],
            "timeout_seconds": _TIMEOUT,
            "max_body_bytes": _MAX_BYTES,
        },
    )
    return {
        "schema_version": "constructionsight.native-ceqanet-detail-preview/v1",
        "policy_id": CEQANET_DETAIL_POLICY.policy_id,
        "detail_url": url,
        "access_decision": access.decision.value,
        "access_reason": access.reason,
        "request_method": "GET",
        "max_response_bytes": _MAX_BYTES,
        "timeout_seconds": _TIMEOUT,
        "expected_preview_digest": expected,
        "may_request_approval": access.decision is AccessDecision.ALLOWED,
        "one_shot_approval_required": True,
        "network_executed": False,
        "source_registry_mutated": False,
        "commercial_authority_granted": False,
        "operator_supplied_access_facts_not_independently_verified": True,
    }


def execute_reviewed_original_ceqanet_detail(payload: dict[str, Any]) -> dict[str, Any]:
    """Delegate to original governed one-shot detail read after exact prior review."""
    if set(payload) != {
        "detail_url", "access_review", "expected_preview_digest",
        "review_reason", "caller_confirmation",
    }:
        raise ValueError("exact reviewed CEQAnet detail authorization fields required")
    preview = preview_original_ceqanet_detail({
        "detail_url": payload["detail_url"],
        "access_review": payload["access_review"],
    })
    if (
        not isinstance(payload["expected_preview_digest"], str)
        or payload["expected_preview_digest"] != preview["expected_preview_digest"]
    ):
        raise ValueError("CEQAnet detail access review changed; preview again")
    reason = payload["review_reason"]
    if (
        not isinstance(reason, str) or not 10 <= len(reason.strip()) <= 2000
        or payload["caller_confirmation"] is not True
        or not preview["may_request_approval"]
    ):
        raise ValueError("evidence-backed access review and explicit approval required")
    _, profile = _reviewed_profile({
        "detail_url": payload["detail_url"],
        "access_review": payload["access_review"],
    })
    try:
        result = execute_authorized_ceqanet_detail(
            detail_url=preview["detail_url"],
            access_profile=profile,
            operator_id=resolve_local_operator_id(),
            authorization_reason=reason.strip(),
            caller_confirmation=True,
            timeout_seconds=_TIMEOUT,
            max_body_bytes=_MAX_BYTES,
        )
    except AuthorizationDeniedError as exc:
        raise ValueError(f"original CEQAnet detail access was denied: {exc}") from exc
    return {
        "schema_version": "constructionsight.native-ceqanet-detail-result/v1",
        "original_execution": result,
        "reviewed_preview_digest": preview["expected_preview_digest"],
        "new_network_attempt_in_this_call": None,
        "authorized_result_or_exact_durable_replay": True,
        "source_registry_mutated": False,
        "source_promoted": False,
        "recurring_collection_enabled": False,
        "commercial_authority_granted": False,
        "operator_supplied_access_facts_not_independently_verified": True,
        "meaning": (
            "Retained original bounded CEQAnet detail read or exact replay; no source verification, "
            "registry update, persistence, recurring collection or outreach."
        ),
    }
