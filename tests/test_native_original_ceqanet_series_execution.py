"""Native original policy-bound one-shot source execution is reviewed, never implicit."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from constructionsight.ceqanet_csv_evidence_series_models import (
    CeqanetCsvEvidenceExecution,
)
from constructionsight.command_center_ceqanet_series_execution import (
    execute_reviewed_original_ceqanet_series_request,
    preview_original_ceqanet_series_request,
)
from tests.test_native_original_ceqanet_series_audit import (
    _ORIGINAL_OBSERVATION,
    _series,
)

_ALLOW = {
    "requires_login": False,
    "has_captcha": False,
    "robots_disallows_collection": False,
    "terms_disallow_collection": False,
    "paywalled": False,
    "access_fact_basis": "review:" + "a" * 64,
}
_UNKNOWN = {**_ALLOW, "requires_login": None}


def _request(access: dict[str, object] = _ALLOW) -> dict[str, object]:
    return {
        "export": {"sch_number": "2026030377", "document_id": None},
        "access_review": access,
    }


def test_original_policy_bound_preview_fails_closed_without_current_access(
    tmp_path: Path,
) -> None:
    db, source, policy, manifest, _ = _series(tmp_path)
    review = preview_original_ceqanet_series_request(
        db, source, policy, manifest, _request(_UNKNOWN),
    )
    assert review["may_request_approval"] is False
    assert review["blockers"]
    assert review["network_executed"] is False
    assert review["retained_output_file"].endswith("-project.json")
    with pytest.raises(ValueError):
        execute_reviewed_original_ceqanet_series_request(
            db, source, policy, manifest, {
                **_request(_UNKNOWN),
                "expected_preview_digest": review["expected_preview_digest"],
                "caller_confirmation": True,
                "review_reason": "One exact reviewed source evidence request",
            },
        )
    with pytest.raises(ValueError):
        preview_original_ceqanet_series_request(
            db, source, policy, manifest, _request({
                **_ALLOW, "access_fact_basis": "unverified prose",
            }),
        )


def test_original_policy_bound_one_shot_uses_original_executor_and_create_only(
    tmp_path: Path,
) -> None:
    db, source, policy, manifest, folder = _series(tmp_path)
    before = hashlib.sha256(db.read_bytes()).hexdigest()
    preview = preview_original_ceqanet_series_request(
        db, source, policy, manifest, _request(),
    )
    assert preview["may_request_approval"] is True
    assert preview["access_decision"] == "allowed"
    assertion = {
        **_request(),
        "expected_preview_digest": preview["expected_preview_digest"],
        "caller_confirmation": True,
        "review_reason": "Independently reviewed exact source access evidence",
    }
    with pytest.raises(ValueError):
        execute_reviewed_original_ceqanet_series_request(
            db, source, policy, manifest,
            {**assertion, "expected_preview_digest": "0" * 64},
        )
    original = CeqanetCsvEvidenceExecution.model_validate(
        json.loads(_ORIGINAL_OBSERVATION.read_text(encoding="utf-8"))
    )
    policy_digest = json.loads(policy.read_text())["policy_digest"]
    draft = original.model_copy(update={
        "policy_digest": policy_digest,
        "evidence_execution_digest": "0" * 64,
    })
    fake = draft.model_copy(update={
        "evidence_execution_digest": draft.computed_digest(),
    })
    with patch(
        "constructionsight.command_center_ceqanet_series_execution."
        "execute_ceqanet_csv_evidence_request",
        return_value=fake,
    ) as original_effect:
        receipt = execute_reviewed_original_ceqanet_series_request(
            db, source, policy, manifest, assertion,
        )
    assert original_effect.call_count == 1
    args, kwargs = original_effect.call_args
    assert kwargs["execute_live"] is True
    assert kwargs["authorization_reason"] == assertion["review_reason"]
    assert args[-1].source_url.endswith("OutputFormat=CSV&Sch=2026030377")
    assert receipt["retained_evidence_written"] is True
    assert receipt["series_advanced"] is False
    retained = folder / receipt["retained_artifact_file"]
    assert retained.is_file()
    assert hashlib.sha256(retained.read_bytes()).hexdigest() == receipt[
        "retained_artifact_sha256"
    ]
    assert "retained_body_base64" not in json.dumps(receipt)
    assert hashlib.sha256(db.read_bytes()).hexdigest() == before
    assert json.loads(manifest.read_text())["evidence_executions"] == []
    assert preview_original_ceqanet_series_request(
        db, source, policy, manifest, _request(),
    )["may_request_approval"] is False
    with pytest.raises(ValueError):
        execute_reviewed_original_ceqanet_series_request(
            db, source, policy, manifest, assertion,
        )


def test_original_evidence_preview_rejects_expired_policy_and_incomplete_config(
    tmp_path: Path,
) -> None:
    db, source, policy, manifest, _ = _series(tmp_path, with_one=True)
    reviewed = preview_original_ceqanet_series_request(
        db, source, policy, manifest, _request(),
    )
    assert reviewed["original_policy_date_window_state"] == "expired"
    assert reviewed["may_request_approval"] is False
    assert preview_original_ceqanet_series_request(
        db, source, policy, manifest, _request(_UNKNOWN),
    )["may_request_approval"] is False
    unconfigured = preview_original_ceqanet_series_request(
        db, source, policy, None, _request(),
    )
    assert unconfigured["available"] is False
    assert unconfigured["may_request_approval"] is False
    assert unconfigured["network_executed"] is False


def test_original_evidence_request_requires_exact_confirmation(
    tmp_path: Path,
) -> None:
    db, source, policy, manifest, _ = _series(tmp_path)
    review = preview_original_ceqanet_series_request(
        db, source, policy, manifest, _request(),
    )
    for confirmation, reason in (
        (False, "Reviewed explicit authorization"),
        (True, "short"),
    ):
        with pytest.raises(ValueError, match="explicit original"):
            execute_reviewed_original_ceqanet_series_request(
                db, source, policy, manifest, {
                    **_request(),
                    "expected_preview_digest": review["expected_preview_digest"],
                    "review_reason": reason,
                    "caller_confirmation": confirmation,
                },
            )
