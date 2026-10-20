"""Reviewed append-only native handoff to the original CEQAnet CSV series.

No network or source-policy mutation. An exact retained execution is checked
through the original builder; new series and manifests are immutable and
published create-only. An active server may select the new exact manifest.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from constructionsight.authorization_decision_models import authorization_digest
from constructionsight.ceqanet_csv_evidence_series_models import (
    CeqanetCsvEvidenceExecution,
    CeqanetCsvEvidenceSeriesStatus,
)
from constructionsight.ceqanet_csv_evidence_series_service import (
    build_ceqanet_csv_evidence_series,
    verify_ceqanet_csv_evidence_series,
)
from constructionsight.command_center_ceqanet_series_audit import _json_artifact
from constructionsight.command_center_ceqanet_series_execution import _context
from constructionsight.storage.runtime_artifacts import (
    read_runtime_artifact,
    write_runtime_text,
)

_FILE_RE = re.compile(
    r"ceqanet-csv-evidence-\d{4}-\d{2}-\d{2}-\d{10}-(?:project|document-[1-9]\d*)\.json"
)
_MANIFEST_SCHEMA = "constructionsight.ceqanet_csv_series_manifest.v1"
_SCHEMA = "constructionsight.native-ceqanet-series-append-preview/v1"
_OUTPUT_CEILING = 16 * 1024 * 1024


def _proposal(
    database: Path | None,
    original_execution: Path | None,
    policy: Path | None,
    manifest: Path | None,
    request: dict[str, Any],
) -> tuple[dict[str, Any], str, str, Path, Path]:
    if set(request) != {"retained_execution_file"}:
        raise ValueError("select only one exact original retained CSV evidence file")
    name = request["retained_execution_file"]
    if not isinstance(name, str) or _FILE_RE.fullmatch(name) is None:
        raise ValueError("only a canonical retained CEQAnet execution filename is allowed")
    if manifest is None:
        raise ValueError("original CEQAnet series manifest is not configured")
    audit, context, series, observed = _context(
        database, original_execution, policy, manifest,
    )
    if series.status is not CeqanetCsvEvidenceSeriesStatus.COLLECTING:
        raise ValueError("original CEQAnet series is terminal, not appendable")
    old_manifest, raw_old = _json_artifact(manifest, limit=64 * 1024)
    if hashlib.sha256(raw_old).hexdigest() != audit["manifest_sha256"]:
        raise ValueError("original CEQAnet manifest changed during append review")
    if any(item["file"] == name for item in old_manifest["evidence_executions"]):
        raise ValueError("retained execution already belongs to the original series")

    candidate_path = manifest.parent / name
    raw_candidate = read_runtime_artifact(
        candidate_path, max_bytes=_OUTPUT_CEILING,
    )
    candidate = CeqanetCsvEvidenceExecution.model_validate(
        json.loads(raw_candidate.decode("utf-8"))
    )
    candidate.assert_integrity()
    if candidate.live_execution.executed_at.date().isoformat() != name.split("-")[3] + "-" + name.split("-")[4] + "-" + name.split("-")[5]:
        raise ValueError("retained original execution filename has a different UTC date")
    if candidate.live_execution.request.sch_number not in name:
        raise ValueError("retained original execution filename has a different SCH")
    if candidate.live_execution.request.document_id is None:
        if not name.endswith("-project.json"):
            raise ValueError("retained original project execution filename mismatches")
    elif not name.endswith(
        f"-document-{candidate.live_execution.request.document_id}.json"
    ):
        raise ValueError("retained original document execution filename mismatches")

    ref = f"evidence/operator-ceqanet/{name}"
    if any(item[0] == ref for item in observed):
        raise ValueError("original series already contains retained artifact identity")
    new_observed = [*observed, (ref, candidate)]
    new_series = build_ceqanet_csv_evidence_series(*context, new_observed)
    verification = verify_ceqanet_csv_evidence_series(
        *context, new_observed, new_series,
    )
    if (
        not verification.passed
        or new_series.observation_count != series.observation_count + 1
        or new_series.predecessor_series_digest != series.series_digest
    ):
        raise ValueError("original governed append failed independent sequence proof")
    # Keep deterministic bytes for create-only, crash-replay-safe publication.
    new_series = new_series.model_copy(
        update={"generated_at": candidate.live_execution.executed_at},
    )
    series_name = (
        f"ceqanet-series-{new_series.series_sequence:02d}-"
        f"{new_series.series_digest[:16]}.json"
    )
    manifest_name = (
        f"ceqanet-series-manifest-{new_series.series_sequence:02d}-"
        f"{new_series.series_digest[:16]}.json"
    )
    new_manifest = {
        "schema_version": _MANIFEST_SCHEMA,
        "series_file": series_name,
        "evidence_executions": [
            *old_manifest["evidence_executions"],
            {"artifact_ref": ref, "file": name},
        ],
    }
    next_series_path = manifest.parent / series_name
    next_manifest_path = manifest.parent / manifest_name
    if next_manifest_path == manifest or next_series_path == manifest:
        raise ValueError("new immutable ledger output conflicts with active input")
    series_text = json.dumps(
        new_series.model_dump(mode="json"), indent=2, sort_keys=True,
    ) + "\n"
    manifest_text = json.dumps(new_manifest, indent=2, sort_keys=True) + "\n"
    basis = {
        "manifest_sha256": audit["manifest_sha256"],
        "original_series_digest": series.series_digest,
        "original_policy_digest": audit["original_policy_digest"],
        "original_registry_digest": audit["original_registry_digest"],
        "candidate_sha256": hashlib.sha256(raw_candidate).hexdigest(),
        "candidate_artifact_ref": ref,
        "next_series_digest": new_series.series_digest,
        "next_series_file": series_name,
        "next_manifest_file": manifest_name,
    }
    result = {
        "schema_version": _SCHEMA,
        "available": True,
        "may_request_approval": True,
        "original_observation_count": series.observation_count,
        "next_observation_count": new_series.observation_count,
        "next_series_status": new_series.status.value,
        "original_series_digest": series.series_digest,
        "next_series_digest": new_series.series_digest,
        "candidate_execution_digest": candidate.evidence_execution_digest,
        "candidate_execution_sha256": basis["candidate_sha256"],
        "next_series_file": series_name,
        "next_manifest_file": manifest_name,
        "expected_preview_digest": authorization_digest(
            "native-original-ceqanet-series-reviewed-append", basis,
        ),
        "network_executed": False,
        "persistence_mutated": False,
        "source_registry_mutated": False,
        "original_source_evidence_mutated": False,
        "commercial_authority_granted": False,
    }
    return result, series_text, manifest_text, next_series_path, next_manifest_path


def preview_original_ceqanet_series_append(
    database: Path | None,
    original_execution: Path | None,
    policy: Path | None,
    manifest: Path | None,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Show exact immutable original ledger transition before any publication."""
    if not isinstance(payload, dict):
        raise ValueError("exact original CEQAnet retained observation required")
    if manifest is None or database is None or original_execution is None or policy is None:
        return {
            "schema_version": _SCHEMA,
            "available": False,
            "may_request_approval": False,
            "blockers": ["configure a verified original CEQAnet evidence series first"],
            "network_executed": False,
            "persistence_mutated": False,
        }
    result, _series, _manifest, _sp, _mp = _proposal(
        database, original_execution, policy, manifest, payload,
    )
    return result


def apply_reviewed_original_ceqanet_series_append(
    database: Path | None,
    original_execution: Path | None,
    policy: Path | None,
    manifest: Path | None,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Atomically publish next immutable snapshot, then next exact manifest."""
    if not isinstance(payload, dict) or set(payload) != {
        "retained_execution_file", "expected_preview_digest",
        "review_reason", "caller_confirmation",
    }:
        raise ValueError("exact reviewed original CEQAnet series append approval required")
    reason = payload["review_reason"]
    if (
        payload["caller_confirmation"] is not True
        or not isinstance(reason, str)
        or not 10 <= len(reason.strip()) <= 2_000
        or not isinstance(payload["expected_preview_digest"], str)
    ):
        raise ValueError("explicit original CEQAnet ledger append consent required")
    selection = {"retained_execution_file": payload["retained_execution_file"]}
    preview, series_text, manifest_text, series_path, manifest_path = _proposal(
        database, original_execution, policy, manifest, selection,
    )
    if preview["expected_preview_digest"] != payload["expected_preview_digest"]:
        raise ValueError("original CEQAnet series append approval is stale")
    # Create-only, versioned outputs; exact replays can finish a previously
    # interrupted two-file publication. The active original manifest is intact.
    for path, expected in (
        (series_path, series_text), (manifest_path, manifest_text),
    ):
        try:
            write_runtime_text(
                path, expected, overwrite=False, max_bytes=_OUTPUT_CEILING,
            )
        except FileExistsError:
            raw = read_runtime_artifact(path, max_bytes=_OUTPUT_CEILING)
            if raw != expected.encode("utf-8"):
                raise ValueError(
                    "immutable original CEQAnet series output already differs"
                ) from None
    return {
        "schema_version": "constructionsight.native-ceqanet-series-append-result/v1",
        "original_series_digest": preview["original_series_digest"],
        "next_series_digest": preview["next_series_digest"],
        "next_observation_count": preview["next_observation_count"],
        "next_series_status": preview["next_series_status"],
        "reviewed_preview_digest": preview["expected_preview_digest"],
        "next_series_file": preview["next_series_file"],
        "next_manifest_file": preview["next_manifest_file"],
        "network_executed": False,
        "source_registry_mutated": False,
        "original_source_evidence_mutated": False,
        "new_immutable_series_published": True,
        "commercial_authority_granted": False,
        "series_manifest_path": str(manifest_path),
        "relaunch_option": "--operator-ceqanet-csv-series-manifest",
    }
