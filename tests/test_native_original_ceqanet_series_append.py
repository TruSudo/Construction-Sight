"""Native original CEQAnet ledger append is separately reviewed and append-only."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from constructionsight.ceqanet_csv_evidence_series_models import CeqanetCsvEvidenceSeries
from constructionsight.ceqanet_csv_evidence_series_service import (
    build_ceqanet_csv_evidence_series,
)
from constructionsight.command_center_ceqanet_series_append import (
    apply_reviewed_original_ceqanet_series_append,
    preview_original_ceqanet_series_append,
)
from constructionsight.command_center_ceqanet_series_execution import _context
from constructionsight.command_center_ceqanet_series_audit import (
    original_retained_ceqanet_series_audit,
)
from tests.test_native_original_ceqanet_series_audit import _series

_NAME = "ceqanet-csv-evidence-2026-07-14-2026030377-project.json"


def _ready(tmp_path: Path) -> tuple[Path, Path, Path, Path, Path]:
    db, source, policy, manifest, folder = _series(tmp_path, with_one=True)
    _audit, original, _series_observed, _observed = _context(
        db, source, policy, manifest,
    )
    empty = build_ceqanet_csv_evidence_series(*original, [])
    (folder / "series.json").write_text(
        json.dumps(empty.model_dump(mode="json")),
    )
    (folder / "manifest.json").write_text(json.dumps({
        "schema_version": "constructionsight.ceqanet_csv_series_manifest.v1",
        "series_file": "series.json", "evidence_executions": [],
    }))
    (folder / _NAME).write_bytes((folder / "observation.json").read_bytes())
    return db, source, policy, manifest, folder


def test_append_original_historical_retained_observation_without_source_or_registry_mutation(
    tmp_path: Path,
) -> None:
    db, source, policy, manifest, folder = _ready(tmp_path)
    baseline = {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in folder.iterdir() if p.is_file()
    }
    db_before = hashlib.sha256(db.read_bytes()).hexdigest()
    selection = {"retained_execution_file": _NAME}
    reviewed = preview_original_ceqanet_series_append(
        db, source, policy, manifest, selection,
    )
    assert reviewed["may_request_approval"] is True
    assert reviewed["next_observation_count"] == 1
    assert reviewed["network_executed"] is False
    with pytest.raises(ValueError, match="stale"):
        apply_reviewed_original_ceqanet_series_append(
            db, source, policy, manifest, {
                **selection, "expected_preview_digest": "0" * 64,
                "caller_confirmation": True,
                "review_reason": "Operator reviewed this exact original observation",
            },
        )
    result = apply_reviewed_original_ceqanet_series_append(
        db, source, policy, manifest, {
            **selection,
            "expected_preview_digest": reviewed["expected_preview_digest"],
            "caller_confirmation": True,
            "review_reason": "Operator reviewed this exact original observation",
        },
    )
    assert result["new_immutable_series_published"] is True
    assert result["network_executed"] is False
    assert result["source_registry_mutated"] is False
    assert result["next_series_digest"] == reviewed["next_series_digest"]
    successor = Path(result["series_manifest_path"])
    assert successor.is_file()
    checked = original_retained_ceqanet_series_audit(
        db, source, policy, successor,
    )
    assert checked["original_series_verification"]["passed"] is True
    assert checked["series"]["observation_count"] == 1
    assert checked["series"]["predecessor_series_digest"] == reviewed[
        "original_series_digest"
    ]
    assert hashlib.sha256(db.read_bytes()).hexdigest() == db_before
    assert {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest()
        for p in folder.iterdir() if p.name in baseline
    } == baseline
    replay = apply_reviewed_original_ceqanet_series_append(
        db, source, policy, manifest, {
            **selection,
            "expected_preview_digest": reviewed["expected_preview_digest"],
            "caller_confirmation": True,
            "review_reason": "Operator reviewed this exact original observation",
        },
    )
    assert replay["next_series_digest"] == result["next_series_digest"]


def test_append_original_refuses_unsafe_and_already_retained_candidates(
    tmp_path: Path,
) -> None:
    db, source, policy, manifest, folder = _ready(tmp_path)
    assert preview_original_ceqanet_series_append(
        db, source, policy, None, {"retained_execution_file": _NAME},
    )["may_request_approval"] is False
    for unsafe in ("../private.json", "observation.json", "/etc/passwd"):
        with pytest.raises(ValueError):
            preview_original_ceqanet_series_append(
                db, source, policy, manifest, {"retained_execution_file": unsafe},
            )
    (folder / _NAME).write_text("{}")
    with pytest.raises(ValueError):
        preview_original_ceqanet_series_append(
            db, source, policy, manifest, {"retained_execution_file": _NAME},
        )


def test_append_original_requires_explicit_review_and_rejects_duplicate(
    tmp_path: Path,
) -> None:
    db, source, policy, manifest, folder = _ready(tmp_path)
    candidate = {"retained_execution_file": _NAME}
    preview = preview_original_ceqanet_series_append(
        db, source, policy, manifest, candidate,
    )
    with pytest.raises(ValueError, match="consent"):
        apply_reviewed_original_ceqanet_series_append(
            db, source, policy, manifest, {
                **candidate,
                "expected_preview_digest": preview["expected_preview_digest"],
                "caller_confirmation": False,
                "review_reason": "Reviewed immutable original evidence append",
            },
        )
    prior = json.loads(manifest.read_text())
    prior["evidence_executions"] = [{
        "artifact_ref": f"evidence/operator-ceqanet/{_NAME}",
        "file": _NAME,
    }]
    series, _ = (folder / "series.json"), None
    # Even before the original builder runs, the selected exact physical
    # candidate cannot be attached twice under a renamed logical reference.
    manifest.write_text(json.dumps(prior))
    with pytest.raises(ValueError):
        preview_original_ceqanet_series_append(
            db, source, policy, manifest, candidate,
        )
