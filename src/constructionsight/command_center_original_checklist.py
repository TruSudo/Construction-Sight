"""Exact retained-source manual observation review using the original offline service.

This is an in-memory checklist report, not source verification, registry
promotion, remote access, persistence or commercial authorization.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from constructionsight.adapters import default_adapter_family_specs
from constructionsight.command_center_source_reachability import (
    _selected_original_source,
    _source_digest,
)
from constructionsight.source_verification_checklist_models import (
    SourceVerificationObservation,
)
from constructionsight.source_verification_checklist_service import (
    build_source_observation_templates,
    build_source_verification_checklist_report,
)

_OBSERVATION_FLAGS = frozenset({
    "public_entry_observed",
    "query_behavior_observed",
    "result_list_observed",
    "detail_page_observed",
    "access_barrier_observed",
    "terms_review_observed",
})
_OBSERVATION_FIELDS = _OBSERVATION_FLAGS | frozenset({
    "source_key", "source_name", "notes", "evidence_refs",
})


def preview_original_manual_checklist(
    database: Path | None, *, source_name: str, public_url: str,
) -> dict[str, Any]:
    """Read one retained source and its original blank operator template."""
    source = _selected_original_source(database, source_name, public_url)
    template = build_source_observation_templates([source])[0]
    return {
        "schema_version": "constructionsight.original-manual-checklist-preview/v1",
        "source_name": source.source_name,
        "public_url": str(source.public_url),
        "source_key": template.source_key,
        "expected_source_sha256": _source_digest(source),
        "original_observation_template": template.model_dump(mode="json"),
        "network_executed": False,
        "original_registry_mutated": False,
        "source_promoted": False,
        "commercial_authority_granted": False,
        "meaning": (
            "Unfilled manual observation template for an exact original source. "
            "No public HTTP access, source promotion or verification is inferred."
        ),
    }


def review_original_manual_checklist(
    database: Path | None, payload: dict[str, Any],
) -> dict[str, Any]:
    """Project explicitly entered manual evidence through the original builder."""
    if set(payload) != {
        "source_name", "public_url", "expected_source_sha256",
        "review_reason", "caller_confirmation", "observation",
    }:
        raise ValueError("exact original manual review request fields required")
    reason = payload["review_reason"]
    expected = payload["expected_source_sha256"]
    if (
        not isinstance(reason, str) or not 10 <= len(reason.strip()) <= 2000
        or payload["caller_confirmation"] is not True
        or not isinstance(expected, str) or len(expected) != 64
        or any(c not in "0123456789abcdef" for c in expected)
    ):
        raise ValueError("explicit review reason and current source receipt required")
    source = _selected_original_source(
        database, payload["source_name"], payload["public_url"],
    )
    if _source_digest(source) != expected:
        raise ValueError("original source changed; repeat manual observation review")
    template = build_source_observation_templates([source])[0]
    data = payload["observation"]
    if not isinstance(data, dict) or set(data) != _OBSERVATION_FIELDS:
        raise ValueError("complete exact original manual observation fields required")
    if data["source_key"] != template.source_key or data["source_name"] != source.source_name:
        raise ValueError("manual observation does not belong to this original source")
    if any(
        data[field] is not None and type(data[field]) is not bool
        for field in _OBSERVATION_FLAGS
    ):
        raise ValueError("manual observation flags must be true, false or unknown")
    notes = data["notes"]
    if notes is not None and (
        not isinstance(notes, str) or len(notes) > 2000
        or any(ord(c) < 32 and c not in "\n\t" for c in notes)
    ):
        raise ValueError("manual observation notes are invalid")
    refs = data["evidence_refs"]
    if (
        not isinstance(refs, list) or len(refs) > 20
        or any(
            not isinstance(ref, str) or not 1 <= len(ref) <= 300
            or any(ord(c) < 32 or ord(c) == 127 for c in ref)
            for ref in refs
        )
        or len(refs) != len(set(refs))
    ):
        raise ValueError("unique bounded manual evidence references required")
    if any(data[field] is True for field in _OBSERVATION_FLAGS) and not refs:
        raise ValueError("positive manual observations require evidence references")
    observation = SourceVerificationObservation.model_validate(data)
    checklist = build_source_verification_checklist_report(
        [source], default_adapter_family_specs(),
        check_http=False, observations=[observation],
    )
    return {
        "schema_version": "constructionsight.original-manual-checklist-review/v1",
        "source_name": source.source_name,
        "public_url": str(source.public_url),
        "reviewed_source_sha256": expected,
        "review_reason": reason.strip(),
        "original_manual_checklist": checklist.to_dict(),
        "original_operator_observation": observation.model_dump(mode="json"),
        "network_executed": False,
        "original_registry_mutated": False,
        "source_promoted": False,
        "commercial_authority_granted": False,
        "operator_observations_not_independent_verification": True,
        "meaning": (
            "Original manual checklist report for operator-supplied observations. "
            "No independent corroboration, registry update or authority is implied."
        ),
    }
