from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from constructionsight.ceqanet_csv_access_policy_cli import app
from constructionsight.ceqanet_csv_access_policy_models import (
    CeqanetCsvAccessPolicy,
    CeqanetCsvAccessPolicyStatus,
    CeqanetCsvAccessPolicyVerification,
)
from constructionsight.ceqanet_csv_access_policy_service import (
    assert_ceqanet_csv_access_policy_current,
    build_ceqanet_csv_access_policy,
    verify_ceqanet_csv_access_policy,
)
from constructionsight.ceqanet_csv_live_models import CeqanetCsvLiveExecution
from constructionsight.ceqanet_csv_models import CeqanetCsvExportKind
from constructionsight.ceqanet_csv_replay_models import (
    CeqanetCsvEncodingReplay,
    CeqanetCsvEncodingReplayVerification,
)
from constructionsight.ceqanet_maturity_proposal_models import (
    CeqanetSourceMaturityProposal,
    CeqanetSourceMaturityProposalVerification,
)
from constructionsight.models import PublicSource

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "data/source_registry.seed.json"
EVIDENCE_DIR = ROOT / "evidence/source_verification"
EXECUTION_PATH = EVIDENCE_DIR / "ceqanet_csv_live_execution_2026-07-12.json"
REPLAY_PATH = EVIDENCE_DIR / "ceqanet_csv_windows1252_replay_2026-07-12.json"
REPLAY_VERIFICATION_PATH = (
    EVIDENCE_DIR / "ceqanet_csv_windows1252_replay_verification_2026-07-12.json"
)
MATURITY_PATH = EVIDENCE_DIR / "ceqanet_source_maturity_proposal_2026-07-13.json"
MATURITY_VERIFICATION_PATH = (
    EVIDENCE_DIR
    / "ceqanet_source_maturity_proposal_verification_2026-07-13.json"
)
POLICY_PATH = EVIDENCE_DIR / "ceqanet_csv_access_policy_2026-07-14.json"
POLICY_VERIFICATION_PATH = (
    EVIDENCE_DIR / "ceqanet_csv_access_policy_verification_2026-07-14.json"
)
POLICY_REPORT_PATH = ROOT / "docs/audits/ceqanet_csv_access_policy_2026-07-14.md"
EFFECTIVE_DATE = date(2026, 7, 14)
EXPIRES_ON = date(2026, 8, 13)
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


def _maturity() -> CeqanetSourceMaturityProposal:
    return CeqanetSourceMaturityProposal.model_validate(_load_json(MATURITY_PATH))


def _maturity_verification() -> CeqanetSourceMaturityProposalVerification:
    return CeqanetSourceMaturityProposalVerification.model_validate(
        _load_json(MATURITY_VERIFICATION_PATH)
    )


def _policy() -> CeqanetCsvAccessPolicy:
    return build_ceqanet_csv_access_policy(
        _sources(),
        _execution(),
        _replay(),
        _replay_verification(),
        _maturity(),
        _maturity_verification(),
        effective_date=EFFECTIVE_DATE,
        expires_on=EXPIRES_ON,
    )


def test_policy_binds_evidence_and_allows_only_bounded_collection() -> None:
    policy = _policy()

    assert (
        policy.policy_status
        is CeqanetCsvAccessPolicyStatus.READY_FOR_EXPLICIT_EVIDENCE_COLLECTION
    )
    assert policy.registry_status == "partial"
    assert policy.allowed_export_kinds == [
        CeqanetCsvExportKind.PROJECT,
        CeqanetCsvExportKind.DOCUMENT,
    ]
    assert policy.max_requests_per_execution == 1
    assert policy.max_executions_per_utc_day == 1
    assert policy.retry_count == 0
    assert policy.retain_complete_body is True
    assert policy.require_independent_verification is True
    assert policy.explicit_execution_authorization_required is True
    assert policy.attachment_download_authorized is False
    assert policy.html_automation_authorized is False
    assert policy.credential_use_authorized is False
    assert policy.captcha_handling_authorized is False
    assert policy.access_control_bypass_authorized is False
    assert policy.persistence_mutation_authorized is False
    assert policy.registry_mutation_authorized is False
    assert policy.source_promotion_authorized is False
    assert policy.production_recurring_execution_authorized is False
    assert policy.halt_status_codes == [401, 403, 407, 429, 451]
    policy.assert_integrity()


def test_policy_digest_is_deterministic() -> None:
    first = _policy()
    second = _policy()

    assert first.policy_digest == second.policy_digest


def test_independent_policy_verification_passes() -> None:
    policy = _policy()

    verification = verify_ceqanet_csv_access_policy(
        _sources(),
        _execution(),
        _replay(),
        _replay_verification(),
        _maturity(),
        _maturity_verification(),
        policy,
    )

    assert verification.passed is True
    assert verification.finding_count == 0
    assert verification.findings == []
    assert verification.policy_digest == policy.policy_digest


@pytest.mark.parametrize(
    ("as_of_date", "message"),
    [
        (date(2026, 7, 13), "not yet effective"),
        (date(2026, 8, 14), "expired"),
    ],
)
def test_policy_current_check_rejects_outside_window(
    as_of_date: date,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        assert_ceqanet_csv_access_policy_current(
            _policy(),
            as_of_date=as_of_date,
        )


def test_policy_current_check_accepts_window_boundaries() -> None:
    policy = _policy()

    assert_ceqanet_csv_access_policy_current(policy, as_of_date=EFFECTIVE_DATE)
    assert_ceqanet_csv_access_policy_current(policy, as_of_date=EXPIRES_ON)


def test_builder_rejects_authority_longer_than_31_inclusive_days() -> None:
    with pytest.raises(ValueError, match="cannot exceed 31 inclusive days"):
        build_ceqanet_csv_access_policy(
            _sources(),
            _execution(),
            _replay(),
            _replay_verification(),
            _maturity(),
            _maturity_verification(),
            effective_date=EFFECTIVE_DATE,
            expires_on=date(2026, 8, 14),
        )


def test_committed_policy_is_replayable_current_and_nonproduction() -> None:
    assert POLICY_PATH.is_file()
    assert POLICY_VERIFICATION_PATH.is_file()
    assert POLICY_REPORT_PATH.is_file()

    policy = CeqanetCsvAccessPolicy.model_validate(_load_json(POLICY_PATH))
    stored_verification = CeqanetCsvAccessPolicyVerification.model_validate(
        _load_json(POLICY_VERIFICATION_PATH)
    )
    recomputed = verify_ceqanet_csv_access_policy(
        _sources(),
        _execution(),
        _replay(),
        _replay_verification(),
        _maturity(),
        _maturity_verification(),
        policy,
    )

    assert recomputed == stored_verification
    assert policy.policy_digest == (
        "d84e6b80234a96799593db0601cc92e6480bad15bfd016001b35568c481c1674"
    )
    assert policy.policy_status is (
        CeqanetCsvAccessPolicyStatus.READY_FOR_EXPLICIT_EVIDENCE_COLLECTION
    )
    assert policy.source_promotion_authorized is False
    assert policy.production_recurring_execution_authorized is False
    assert_ceqanet_csv_access_policy_current(
        policy,
        as_of_date=EFFECTIVE_DATE,
    )
    policy.assert_integrity()


def test_verification_detects_tampered_policy() -> None:
    policy = _policy()
    tampered = policy.model_copy(update={"timeout_seconds": 25.0})

    verification = verify_ceqanet_csv_access_policy(
        _sources(),
        _execution(),
        _replay(),
        _replay_verification(),
        _maturity(),
        _maturity_verification(),
        tampered,
    )

    assert verification.passed is False
    assert "CEQAnet CSV access policy digest mismatch" in verification.findings
    assert (
        "CSV access policy does not match current evidence and governance"
        in verification.findings
    )


def test_builder_rejects_mismatched_maturity_verification() -> None:
    changed = _maturity_verification().model_copy(
        update={"proposal_digest": "0" * 64}
    )

    with pytest.raises(ValueError, match="stored maturity verification does not match"):
        build_ceqanet_csv_access_policy(
            _sources(),
            _execution(),
            _replay(),
            _replay_verification(),
            _maturity(),
            changed,
            effective_date=EFFECTIVE_DATE,
            expires_on=EXPIRES_ON,
        )


def test_cli_builds_verifies_and_checks_current_policy(tmp_path: Path) -> None:
    policy_path = tmp_path / "policy.json"
    verification_path = tmp_path / "verification.json"
    common = [
        str(REGISTRY_PATH),
        str(EXECUTION_PATH),
        str(REPLAY_PATH),
        str(REPLAY_VERIFICATION_PATH),
        str(MATURITY_PATH),
        str(MATURITY_VERIFICATION_PATH),
    ]

    build_result = runner.invoke(
        app,
        [
            "build",
            *common,
            "--effective-date",
            EFFECTIVE_DATE.isoformat(),
            "--expires-on",
            EXPIRES_ON.isoformat(),
            "--output",
            str(policy_path),
        ],
    )

    assert build_result.exit_code == 0, build_result.output
    payload = _load_json(policy_path)
    assert payload["policy_status"] == "ready_for_explicit_evidence_collection"
    assert payload["production_recurring_execution_authorized"] is False

    verify_result = runner.invoke(
        app,
        [
            "verify",
            *common,
            str(policy_path),
            "--output",
            str(verification_path),
        ],
    )

    assert verify_result.exit_code == 0, verify_result.output
    verification = _load_json(verification_path)
    assert verification["passed"] is True
    assert verification["finding_count"] == 0

    current_result = runner.invoke(
        app,
        [
            "check-current",
            str(policy_path),
            "--as-of-date",
            EFFECTIVE_DATE.isoformat(),
        ],
    )
    assert current_result.exit_code == 0, current_result.output
    assert "is current" in current_result.output


def test_policy_model_rejects_unknown_fields() -> None:
    payload = _policy().model_dump(mode="json")
    payload["unexpected"] = "blocked"

    with pytest.raises(ValidationError):
        CeqanetCsvAccessPolicy.model_validate(payload)
