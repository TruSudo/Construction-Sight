"""Governed native one-request SMARTS public catalog metadata inspection.

Reuse the original strict CKAN package/resource verifier. A reviewed exact
public endpoint and access decision authorizes only one metadata GET, never
dataset export, scheduling, source status promotion, ingestion or outreach.
"""

from __future__ import annotations

import re
from typing import Any

import httpx

from constructionsight.authorization_decision_models import authorization_digest
from constructionsight.legal import AccessDecision, SourceAccessProfile, evaluate_access
from constructionsight.smarts_api import USER_AGENT
from constructionsight.smarts_catalog_probe import (
    CATALOG_ENDPOINT,
    MAX_METADATA_BYTES,
    PACKAGE_ID,
    REQUIRED_RESOURCES,
    build_catalog_summary,
    fetch_catalog,
)

_FACTS = (
    "requires_login",
    "has_captcha",
    "robots_disallows_collection",
    "terms_disallow_collection",
    "paywalled",
)
_KEYS = frozenset((*_FACTS, "access_fact_basis"))


def _access(payload: dict[str, Any]) -> SourceAccessProfile:
    if set(payload) != {"access_review"} or not isinstance(
        payload["access_review"], dict
    ):
        raise ValueError("exact SMARTS catalog access review required")
    review = payload["access_review"]
    if set(review) != _KEYS:
        raise ValueError("complete SMARTS source access facts required")
    if any(
        review[key] is not None and type(review[key]) is not bool
        for key in _FACTS
    ):
        raise ValueError("SMARTS catalog access restrictions must be tri-state")
    basis = review["access_fact_basis"]
    if basis is not None and (
        not isinstance(basis, str)
        or re.fullmatch(r"(?:review|evidence):[0-9a-f]{64}", basis) is None
    ):
        raise ValueError("catalog access evidence must be an immutable SHA-256 identity")
    return SourceAccessProfile(
        public_url=CATALOG_ENDPOINT,
        access_fact_basis=basis,
        requires_login=review["requires_login"],
        has_captcha=review["has_captcha"],
        robots_disallows_collection=review["robots_disallows_collection"],
        terms_disallow_collection=review["terms_disallow_collection"],
        paywalled=review["paywalled"],
    )


def preview_original_smarts_catalog(payload: dict[str, Any]) -> dict[str, Any]:
    """Exact source policy and one bounded original catalog request, no network."""
    profile = _access(payload)
    policy = evaluate_access(profile)
    review_digest = authorization_digest(
        "native-original-smarts-catalog-review/v1",
        {
            "endpoint": CATALOG_ENDPOINT,
            "package_id": PACKAGE_ID,
            "resources": REQUIRED_RESOURCES,
            "max_bytes": MAX_METADATA_BYTES,
            "timeout_seconds": 15,
            "access_review": payload["access_review"],
        },
    )
    return {
        "schema_version": "constructionsight.native-smarts-catalog-preview/v1",
        "policy_id": "CS-NET-SMARTS-CATALOG",
        "official_catalog_url": CATALOG_ENDPOINT,
        "exact_package_id": PACKAGE_ID,
        "expected_resource_ids": REQUIRED_RESOURCES,
        "maximum_response_bytes": MAX_METADATA_BYTES,
        "request_method": "GET",
        "request_count": 1,
        "redirects_followed": False,
        "access_decision": policy.decision.value,
        "access_reason": policy.reason,
        "may_request_approval": policy.decision is AccessDecision.ALLOWED,
        "expected_review_digest": review_digest,
        "network_executed": False,
        "persistence_mutated": False,
        "collection_authorized": False,
        "commercial_authority_granted": False,
    }


def execute_reviewed_original_smarts_catalog(payload: dict[str, Any]) -> dict[str, Any]:
    """Fetch original bounded metadata only after unchanged explicit exact approval."""
    if set(payload) != {
        "access_review",
        "expected_review_digest",
        "review_reason",
        "caller_confirmation",
    }:
        raise ValueError("exact SMARTS catalog execution approval required")
    reason = payload["review_reason"]
    if (
        not isinstance(reason, str)
        or reason != reason.strip()
        or not 10 <= len(reason) <= 1000
        or payload["caller_confirmation"] is not True
        or not isinstance(payload["expected_review_digest"], str)
    ):
        raise ValueError("exact SMARTS catalog approval and reason required")
    review = {"access_review": payload["access_review"]}
    preview = preview_original_smarts_catalog(review)
    if (
        not preview["may_request_approval"]
        or payload["expected_review_digest"] != preview["expected_review_digest"]
    ):
        raise ValueError("SMARTS catalog source review blocked or changed")
    with httpx.Client(
        follow_redirects=False,
        trust_env=False,
        timeout=httpx.Timeout(15.0, connect=5.0),
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    ) as client:
        observed = fetch_catalog(client)
    original = build_catalog_summary(observed)
    return {
        "schema_version": "constructionsight.native-smarts-catalog-result/v1",
        "reviewed_digest": preview["expected_review_digest"],
        "original_catalog_observation": original,
        "source_access_fact_basis": payload["access_review"]["access_fact_basis"],
        "network_executed": True,
        "request_count": 1,
        "dataset_downloaded": False,
        "persistence_mutated": False,
        "collection_authorized": False,
        "commercial_authority_granted": False,
        "meaning": (
            "One operator-reviewed original public CKAN metadata observation. "
            "No CSV download, source promotion, schedule, lead qualification or outreach."
        ),
    }
