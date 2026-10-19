"""Native guarded CEQAnet listing and CSV entry points, using original services."""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from constructionsight.adapters.ceqanet_listing import (
    CeqanetListingQuery,
    CeqanetReadOnlyListingPlanner,
)
from constructionsight.adapters.ceqanet_listing_dry_run import CeqanetListingDryRunExecutor
from constructionsight.authorization_decision import AuthorizationDeniedError
from constructionsight.authorization_decision_models import authorization_digest
from constructionsight.ceqanet_csv_service import build_ceqanet_csv_export_request
from constructionsight.ceqanet_listing_plan_cli import _dry_run_to_dict, _plan_to_dict
from constructionsight.ceqanet_listing_service import (
    CeqanetListingServiceError,
    _plan_identity,
    execute_authorized_ceqanet_listing,
)
from constructionsight.legal import AccessDecision, SourceAccessProfile, evaluate_access
from constructionsight.operator_services.ceqanet_csv_service import (
    execute_authorized_ceqanet_csv,
)

_FLAGS = ("requires_login", "has_captcha", "robots_disallows_collection",
          "terms_disallow_collection", "paywalled")
_QUERY_KEYS = {"counties", "document_types", "lead_agencies", "received_from",
               "received_to", "posted_from", "posted_to", "high_signal_only",
               "page_size", "max_pages"}


def _profile(url: str, review: Any) -> SourceAccessProfile:
    if not isinstance(review, dict) or set(review) != set(_FLAGS) | {"access_fact_basis"}:
        raise ValueError("exact complete source access review required")
    if any(review[key] is not None and type(review[key]) is not bool for key in _FLAGS):
        raise ValueError("source restriction facts must be true, false, or unknown")
    basis = review["access_fact_basis"]
    if basis is not None and (
        not isinstance(basis, str) or len(basis) > 80
        or any(ord(c) < 32 or ord(c) == 127 for c in basis)
    ):
        raise ValueError("invalid immutable access evidence identity")
    return SourceAccessProfile(
        public_url=url, access_fact_basis=basis,
        requires_login=review["requires_login"],
        has_captcha=review["has_captcha"],
        robots_disallows_collection=review["robots_disallows_collection"],
        terms_disallow_collection=review["terms_disallow_collection"],
        paywalled=review["paywalled"],
    )


def _listing(payload: dict[str, Any]) -> tuple[CeqanetListingQuery, SourceAccessProfile]:
    if set(payload) != {"query", "access_review"}:
        raise ValueError("exact CEQAnet listing review required")
    query = payload["query"]
    if not isinstance(query, dict) or set(query) != _QUERY_KEYS:
        raise ValueError("complete bounded listing filters required")
    if (type(query["page_size"]) is not int
            or type(query["max_pages"]) is not int
            or type(query["high_signal_only"]) is not bool):
        raise ValueError("page size/count and signal flag must have exact types")

    def names(key: str) -> tuple[str, ...]:
        raw = query[key]
        if not isinstance(raw, list) or len(raw) > 15:
            raise ValueError(f"invalid bounded {key} filters")
        if any(not isinstance(value, str) or value != value.strip()
               or not 1 <= len(value) <= 100
               or any(ord(ch) < 32 for ch in value) for value in raw):
            raise ValueError(f"invalid {key} filter")
        return tuple(raw)

    def day(key: str) -> date | None:
        raw = query[key]
        if raw is None:
            return None
        if not isinstance(raw, str) or re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw) is None:
            raise ValueError(f"{key} must be ISO date or null")
        return date.fromisoformat(raw)

    return CeqanetListingQuery(
        counties=names("counties"), document_types=names("document_types"),
        lead_agencies=names("lead_agencies"),
        received_from=day("received_from"), received_to=day("received_to"),
        posted_from=day("posted_from"), posted_to=day("posted_to"),
        high_signal_only=query["high_signal_only"],
        page_size=query["page_size"], max_pages=query["max_pages"],
    ), _profile("https://ceqanet.lci.ca.gov/", payload["access_review"])


def preview_original_ceqanet_listing(payload: dict[str, Any]) -> dict[str, Any]:
    """Re-use original listing plan and zero-network dry-run."""
    query, profile = _listing(payload)
    plan = CeqanetReadOnlyListingPlanner().build_plan(query, evaluate_access(profile))
    dry = CeqanetListingDryRunExecutor().run(plan)
    plan_id = _plan_identity(plan)
    identity = authorization_digest("native-ceqanet-listing-approval", {
        "query": payload["query"], "access_review": payload["access_review"],
        "plan_id": plan_id, "timeout_seconds": 20.0, "max_response_bytes": 50_000,
    })
    return {
        "schema_version": "constructionsight.native-ceqanet-listing-preview/v1",
        "policy_id": "CS-NET-002",
        "plan_id": plan_id, "original_plan": _plan_to_dict(plan),
        "original_dry_run": _dry_run_to_dict(dry, plan),
        "request_count": dry.planned_request_count,
        "expected_preview_digest": identity, "may_request_approval": plan.allowed,
        "network_executed": False, "source_registry_mutated": False,
        "commercial_authority_granted": False,
    }


def _approval(payload: dict[str, Any], exact: set[str]) -> str:
    if set(payload) != exact | {
        "expected_preview_digest", "review_reason", "caller_confirmation",
    }:
        raise ValueError("exact approved source acquisition fields required")
    reason = payload["review_reason"]
    if (not isinstance(reason, str) or not 10 <= len(reason.strip()) <= 2000
            or payload["caller_confirmation"] is not True
            or not isinstance(payload["expected_preview_digest"], str)):
        raise ValueError("explicit exact reviewed source authorization required")
    return reason.strip()


def execute_reviewed_original_ceqanet_listing(payload: dict[str, Any]) -> dict[str, Any]:
    reason = _approval(payload, {"query", "access_review"})
    review = {"query": payload["query"], "access_review": payload["access_review"]}
    preview = preview_original_ceqanet_listing(review)
    if (not preview["may_request_approval"]
            or preview["expected_preview_digest"] != payload["expected_preview_digest"]):
        raise ValueError("CEQAnet listing plan is unapproved or stale")
    query, profile = _listing(review)
    plan = CeqanetReadOnlyListingPlanner().build_plan(query, evaluate_access(profile))
    try:
        result = execute_authorized_ceqanet_listing(
            plan=plan, access_profile=profile,
            authorization_reason=reason, caller_confirmation=True,
            timeout_seconds=20.0, max_response_bytes=50_000,
        )
    except (AuthorizationDeniedError, CeqanetListingServiceError) as exc:
        raise ValueError(f"original CEQAnet listing access denied: {exc}") from exc
    return {
        "schema_version": "constructionsight.native-ceqanet-listing-result/v1",
        "reviewed_preview_digest": preview["expected_preview_digest"],
        "original_execution": result, "fresh_request_not_established": True,
        "source_registry_mutated": False, "commercial_authority_granted": False,
    }


def _csv(payload: dict[str, Any]) -> tuple[Any, SourceAccessProfile]:
    if set(payload) != {"export", "access_review"}:
        raise ValueError("exact CEQAnet CSV review required")
    export = payload["export"]
    if not isinstance(export, dict) or set(export) != {"sch_number", "document_id"}:
        raise ValueError("exact official CSV export identity required")
    sch, doc = export["sch_number"], export["document_id"]
    if not isinstance(sch, str) or re.fullmatch(r"\d{10}", sch) is None:
        raise ValueError("ten-digit SCH required")
    if doc is not None and (type(doc) is not int or not 1 <= doc <= 2_147_483_647):
        raise ValueError("bounded positive document ID required")
    request = build_ceqanet_csv_export_request(sch_number=sch, document_id=doc)
    return request, _profile(request.source_url, payload["access_review"])


def preview_original_ceqanet_csv(payload: dict[str, Any]) -> dict[str, Any]:
    request, profile = _csv(payload)
    access = evaluate_access(profile)
    identity = authorization_digest("native-ceqanet-csv-approval", {
        "request": request.model_dump(mode="json"),
        "access_review": payload["access_review"],
        "timeout_seconds": 20.0, "max_body_bytes": 10_000_000,
        "max_retained_rows": 1_000,
    })
    return {
        "schema_version": "constructionsight.native-ceqanet-csv-preview/v1",
        "policy_id": "CS-NET-003",
        "original_request": request.model_dump(mode="json"),
        "access_decision": access.decision.value,
        "access_reason": access.reason,
        "expected_preview_digest": identity,
        "may_request_approval": access.decision is AccessDecision.ALLOWED,
        "network_executed": False, "persistence_mutated": False,
        "commercial_authority_granted": False,
    }


def execute_reviewed_original_ceqanet_csv(payload: dict[str, Any]) -> dict[str, Any]:
    reason = _approval(payload, {"export", "access_review"})
    review = {"export": payload["export"], "access_review": payload["access_review"]}
    preview = preview_original_ceqanet_csv(review)
    if (not preview["may_request_approval"]
            or preview["expected_preview_digest"] != payload["expected_preview_digest"]):
        raise ValueError("CEQAnet CSV review unapproved or stale")
    request, profile = _csv(review)
    try:
        original = execute_authorized_ceqanet_csv(
            request=request, access_profile=profile,
            authorization_reason=reason, caller_confirmation=True,
            timeout_seconds=20.0, max_body_bytes=10_000_000, max_retained_rows=1_000,
        )
    except AuthorizationDeniedError as exc:
        raise ValueError(f"original CEQAnet CSV access denied: {exc}") from exc
    return {
        "schema_version": "constructionsight.native-ceqanet-csv-result/v1",
        "reviewed_preview_digest": preview["expected_preview_digest"],
        "original_execution": original.execution.model_dump(mode="json"),
        "original_verification": original.verification.model_dump(mode="json"),
        "original_authorization": original.authorization.to_dict(),
        "fresh_request_not_established": True, "persistence_mutated": False,
        "commercial_authority_granted": False,
    }
