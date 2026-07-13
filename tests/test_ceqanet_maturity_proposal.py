from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from constructionsight.ceqanet_csv_live_models import CeqanetCsvLiveExecution
from constructionsight.ceqanet_csv_replay_models import (
    CeqanetCsvEncodingReplay,
    CeqanetCsvEncodingReplayVerification,
)
from constructionsight.ceqanet_maturity_proposal_cli import app
from constructionsight.ceqanet_maturity_proposal_models import (
    CeqanetMaturityDecision,
    CeqanetSourceMaturityProposal,
    CeqanetSourceMaturityProposalVerification,
)
from constructionsight.ceqanet_maturity_proposal_service import (
    build_ceqanet_source_maturity_proposal,
    verify_ceqanet_source_maturity_proposal,
)
from constructionsight.models import PublicSource, VerificationStatus

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "data/source_registry.seed.json"
EVIDENCE_DIR = ROOT / "evidence/source_verification"
EXECUTION_PATH = EVIDENCE_DIR / "ceqanet_csv_live_execution_2026-07-12.json"
REPLAY_PATH = EVIDENCE_DIR / "ceqanet_csv_windows1252_replay_2026-07-12.json"
REPLAY_VERIFICATION_PATH = (
    EVIDENCE_DIR / "ceqanet_csv_windows1252_replay_verification_2026-07-12.json"
)
PROPOSAL_PATH = (
    EVIDENCE_DIR / "ceqanet_source_maturity_proposal_2026-07-13.json"
)
PROPOSAL_VERIFICATION_PATH = (
    EVIDENCE_DIR
    / "ceqanet_source_maturity_proposal_verification_2026-07-13.json"
)
PROPOSAL_REPORT_PATH = (
    ROOT / "docs/audits/ceqanet_source_maturity_proposal_2026-07-13.md"
)
runner = CliRunner()


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sources() -> list[PublicSource]:
    payload = _load_json(REGISTRY_PATH)
    assert isinstance(payload, list)
    return [PublicSource.model_validate(item) for item in payload]


def _execution() -> CeqanetCsvLiveExecution:
    return CeqanetCsvLiveExecution.model_validate(_load_json(EXECUTION_PATH))


def _replay() -> CeqanetCsvEncodingReplay:
    return CeqanetCsvEncodingReplay.model_validate(_load_json(REPLAY_PATH))


def _replay_verification() -> CeqanetCsvEncodingReplayVerification:
    return CeqanetCsvEncodingReplayVerification.model_validate(
        _load_json(REPLAY_VERIFICATION_PATH)
    )


def _proposal() -> CeqanetSourceMaturityProposal:
    return build_ceqanet_source_maturity_proposal(
        _sources(),
        _execution(),
        _replay(),
        _replay_verification(),
    )


def test_proposal_binds_exact_evidence_and_keeps_source_partial() -> None:
    proposal = _proposal()
    execution = _execution()
    replay = _replay()

    assert proposal.decision is CeqanetMaturityDecision.KEEP_PARTIAL
    assert proposal.registry_status == "partial"
    assert proposal.live_execution_digest == execution.execution_digest
    assert proposal.source_body_sha256 == execution.body_sha256
    assert proposal.replay_digest == replay.replay_digest
    assert proposal.inspection_digest == replay.inspection.inspection_digest
    assert proposal.observed_status_code == 200
    assert proposal.observed_row_count == 2
    assert proposal.observed_encoding == "windows-1252"
    assert proposal.network_executed is False
    assert proposal.persistence_mutated is False
    assert proposal.registry_mutation_authorized is False
    assert proposal.recurring_execution_authorized is False
    assert proposal.blockers
    proposal.assert_integrity()


def test_proposal_digest_excludes_generation_timestamp() -> None:
    first = _proposal()
    second = _proposal()

    assert first.generated_at != second.generated_at
    assert first.proposal_digest == second.proposal_digest


def test_independent_proposal_verification_passes() -> None:
    proposal = _proposal()

    verification = verify_ceqanet_source_maturity_proposal(
        _sources(),
        _execution(),
        _replay(),
        _replay_verification(),
        proposal,
    )

    assert verification.passed is True
    assert verification.finding_count == 0
    assert verification.findings == []
    assert verification.proposal_digest == proposal.proposal_digest


def test_committed_proposal_is_replayable_and_non_authorizing() -> None:
    assert PROPOSAL_PATH.is_file()
    assert PROPOSAL_VERIFICATION_PATH.is_file()
    assert PROPOSAL_REPORT_PATH.is_file()

    proposal = CeqanetSourceMaturityProposal.model_validate(_load_json(PROPOSAL_PATH))
    stored_verification = CeqanetSourceMaturityProposalVerification.model_validate(
        _load_json(PROPOSAL_VERIFICATION_PATH)
    )
    recomputed = verify_ceqanet_source_maturity_proposal(
        _sources(),
        _execution(),
        _replay(),
        _replay_verification(),
        proposal,
    )

    assert recomputed == stored_verification
    assert proposal.proposal_digest == (
        "3a8069a5dd72a921f1e4324347d00d3c5a8ee8f7100676bdff3a702d6a424088"
    )
    assert proposal.decision is CeqanetMaturityDecision.KEEP_PARTIAL
    assert proposal.registry_mutation_authorized is False
    assert proposal.recurring_execution_authorized is False
    proposal.assert_integrity()


def test_verification_detects_tampered_proposal() -> None:
    proposal = _proposal()
    tampered = proposal.model_copy(
        update={"observed_row_count": proposal.observed_row_count + 1}
    )

    verification = verify_ceqanet_source_maturity_proposal(
        _sources(),
        _execution(),
        _replay(),
        _replay_verification(),
        tampered,
    )

    assert verification.passed is False
    assert "CEQAnet source-maturity proposal digest mismatch" in verification.findings
    assert (
        "maturity proposal does not match current evidence and registry"
        in verification.findings
    )


def test_builder_rejects_nonpartial_registry_status() -> None:
    sources = _sources()
    sources[0] = sources[0].model_copy(
        update={"verification_status": VerificationStatus.VERIFIED}
    )

    with pytest.raises(ValueError, match="requires registry status partial"):
        build_ceqanet_source_maturity_proposal(
            sources,
            _execution(),
            _replay(),
            _replay_verification(),
        )


def test_builder_rejects_mismatched_stored_replay_verification() -> None:
    changed = _replay_verification().model_copy(update={"replay_digest": "0" * 64})

    with pytest.raises(ValueError, match="stored replay verification does not match"):
        build_ceqanet_source_maturity_proposal(
            _sources(),
            _execution(),
            _replay(),
            changed,
        )


def test_cli_builds_and_verifies_report_only_proposal(tmp_path: Path) -> None:
    proposal_path = tmp_path / "proposal.json"
    verification_path = tmp_path / "verification.json"

    build_result = runner.invoke(
        app,
        [
            "build",
            str(REGISTRY_PATH),
            str(EXECUTION_PATH),
            str(REPLAY_PATH),
            str(REPLAY_VERIFICATION_PATH),
            "--output",
            str(proposal_path),
        ],
    )

    assert build_result.exit_code == 0, build_result.output
    payload = _load_json(proposal_path)
    assert payload["decision"] == "keep_partial"
    assert payload["network_executed"] is False
    assert payload["registry_mutation_authorized"] is False
    assert payload["recurring_execution_authorized"] is False

    verify_result = runner.invoke(
        app,
        [
            "verify",
            str(REGISTRY_PATH),
            str(EXECUTION_PATH),
            str(REPLAY_PATH),
            str(REPLAY_VERIFICATION_PATH),
            str(proposal_path),
            "--output",
            str(verification_path),
        ],
    )

    assert verify_result.exit_code == 0, verify_result.output
    verification = _load_json(verification_path)
    assert verification["passed"] is True
    assert verification["finding_count"] == 0


def test_proposal_model_rejects_unknown_fields() -> None:
    payload = _proposal().model_dump(mode="json")
    payload["unexpected"] = "blocked"

    with pytest.raises(ValidationError):
        CeqanetSourceMaturityProposal.model_validate(payload)
