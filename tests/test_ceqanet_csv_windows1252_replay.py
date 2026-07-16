from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from constructionsight.ceqanet_csv_cli import app
from constructionsight.ceqanet_csv_live_models import CeqanetCsvLiveExecution
from constructionsight.ceqanet_csv_models import CeqanetCsvInspection
from constructionsight.ceqanet_csv_replay_models import (
    CeqanetCsvEncodingReplay,
    CeqanetCsvEncodingReplayVerification,
)
from constructionsight.ceqanet_csv_replay_service import (
    build_ceqanet_csv_encoding_replay,
    verify_ceqanet_csv_encoding_replay,
)
from constructionsight.ceqanet_csv_service import (
    build_ceqanet_csv_export_request,
    inspect_ceqanet_csv_bytes,
)

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_DIR = ROOT / "evidence/source_verification"
EXECUTION_PATH = EVIDENCE_DIR / "ceqanet_csv_live_execution_2026-07-12.json"
REPLAY_PATH = EVIDENCE_DIR / "ceqanet_csv_windows1252_replay_2026-07-12.json"
VERIFICATION_PATH = EVIDENCE_DIR / "ceqanet_csv_windows1252_replay_verification_2026-07-12.json"
REPORT_PATH = ROOT / "docs/audits/ceqanet_csv_windows1252_replay_2026-07-12.md"
runner = CliRunner()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _request():
    return build_ceqanet_csv_export_request(sch_number="2026030377")


def test_windows1252_is_used_only_after_strict_utf8_failure() -> None:
    content = ("SCH Number,Description\r\n2026030377,Alpha • Beta\r\n").encode("windows-1252")

    inspection = inspect_ceqanet_csv_bytes(
        _request(),
        content,
        content_type="text/csv",
    )

    assert inspection.encoding == "windows-1252"
    assert inspection.rows[0]["description"] == "Alpha • Beta"
    assert "source body decoded as Windows-1252 after strict UTF-8 failure" in (inspection.warnings)


def test_valid_utf8_remains_preferred_over_windows1252() -> None:
    content = ("SCH Number,Description\r\n2026030377,Alpha • Beta\r\n").encode()

    inspection = inspect_ceqanet_csv_bytes(
        _request(),
        content,
        content_type="text/csv",
    )

    assert inspection.encoding == "utf-8-sig"
    assert "source body decoded as Windows-1252 after strict UTF-8 failure" not in (
        inspection.warnings
    )


def test_undefined_windows1252_byte_is_rejected() -> None:
    content = b"SCH Number,Description\r\n2026030377,bad\x81value\r\n"

    with pytest.raises(
        ValueError,
        match="UTF-8, UTF-8 with BOM, or Windows-1252",
    ):
        inspect_ceqanet_csv_bytes(
            _request(),
            content,
            content_type="text/csv",
        )


def test_retained_live_body_builds_verified_offline_replay() -> None:
    execution = CeqanetCsvLiveExecution.model_validate(_load_json(EXECUTION_PATH))

    replay = build_ceqanet_csv_encoding_replay(execution)
    verification = verify_ceqanet_csv_encoding_replay(execution, replay)

    assert replay.network_executed is False
    assert replay.persistence_mutated is False
    assert replay.source_execution_digest == execution.execution_digest
    assert replay.source_body_sha256 == execution.body_sha256
    assert replay.inspection.encoding == "windows-1252"
    assert replay.inspection.row_count > 0
    assert replay.inspection.request.sch_number == "2026030377"
    replay.assert_integrity()
    assert verification.passed is True
    assert verification.findings == []


def test_replay_verifier_rejects_provenance_tampering() -> None:
    execution = CeqanetCsvLiveExecution.model_validate(_load_json(EXECUTION_PATH))
    replay = build_ceqanet_csv_encoding_replay(execution)
    tampered = replay.model_copy(update={"source_execution_digest": "0" * 64})

    verification = verify_ceqanet_csv_encoding_replay(execution, tampered)

    assert verification.passed is False
    assert "CEQAnet CSV encoding replay digest mismatch" in verification.findings
    assert (
        "replay source execution digest does not match the live execution" in verification.findings
    )


def test_committed_replay_artifacts_are_replayable_and_consistent() -> None:
    for path in (REPLAY_PATH, VERIFICATION_PATH, REPORT_PATH):
        assert path.is_file(), f"missing replay evidence artifact: {path}"

    execution = CeqanetCsvLiveExecution.model_validate(_load_json(EXECUTION_PATH))
    replay = CeqanetCsvEncodingReplay.model_validate(_load_json(REPLAY_PATH))
    stored = CeqanetCsvEncodingReplayVerification.model_validate(_load_json(VERIFICATION_PATH))
    recomputed = verify_ceqanet_csv_encoding_replay(execution, replay)

    assert replay.inspection.encoding == "windows-1252"
    assert replay.inspection.byte_length == 7_832
    assert replay.inspection.body_sha256 == (
        "5b1bc503c81d12ed0f00e52539edb437b42ae4c3a539a25e1c82a02b84273163"
    )
    assert stored == recomputed
    assert stored.passed is True
    assert stored.findings == []
    assert replay.network_executed is False
    assert replay.persistence_mutated is False

    temporary_paths = (
        ROOT / ".github/workflows/ceqanet-csv-windows1252-replay.yml",
        ROOT / ".github/workflows/ceqanet-csv-windows1252-replay-v2.yml",
        ROOT / "scripts/apply_ceqanet_windows1252_replay.py",
        ROOT / "scripts/patch_ceqanet_windows1252_runtime.py",
    )
    assert all(not path.exists() for path in temporary_paths)


def test_replay_cli_builds_and_verifies_retained_body(tmp_path: Path) -> None:
    replay_path = tmp_path / "replay.json"
    verification_path = tmp_path / "verification.json"

    replay_result = runner.invoke(
        app,
        [
            "replay-execution",
            str(EXECUTION_PATH),
            "--output",
            str(replay_path),
            "--max-retained-rows",
            "1000",
        ],
    )

    assert replay_result.exit_code == 0, replay_result.output
    replay_payload = _load_json(replay_path)
    assert replay_payload["network_executed"] is False
    assert replay_payload["persistence_mutated"] is False
    assert replay_payload["inspection"]["encoding"] == "windows-1252"

    verify_result = runner.invoke(
        app,
        [
            "verify-replay",
            str(EXECUTION_PATH),
            str(replay_path),
            "--output",
            str(verification_path),
        ],
    )

    assert verify_result.exit_code == 0, verify_result.output
    verification_payload = _load_json(verification_path)
    assert verification_payload["passed"] is True
    assert verification_payload["finding_count"] == 0
    assert verification_payload["findings"] == []


def test_replay_models_reject_unknown_fields() -> None:
    execution = CeqanetCsvLiveExecution.model_validate(_load_json(EXECUTION_PATH))
    replay = build_ceqanet_csv_encoding_replay(execution)
    replay_payload: dict[str, Any] = replay.model_dump(mode="json")
    replay_payload["unexpected"] = True

    with pytest.raises(ValueError, match="Extra inputs are not permitted"):
        CeqanetCsvEncodingReplay.model_validate(replay_payload)

    verification = verify_ceqanet_csv_encoding_replay(execution, replay)
    verification_payload: dict[str, Any] = verification.model_dump(mode="json")
    verification_payload["unexpected"] = True

    with pytest.raises(ValueError, match="Extra inputs are not permitted"):
        CeqanetCsvEncodingReplayVerification.model_validate(verification_payload)


def test_inspection_schema_accepts_only_declared_encodings() -> None:
    execution = CeqanetCsvLiveExecution.model_validate(_load_json(EXECUTION_PATH))
    replay = build_ceqanet_csv_encoding_replay(execution)
    payload: dict[str, Any] = replay.inspection.model_dump(mode="json")
    payload["encoding"] = "latin-1"

    with pytest.raises(ValueError, match="Input should be"):
        CeqanetCsvInspection.model_validate(payload)
