from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
import socksio
from pydantic import ValidationError
from typer.testing import CliRunner

from constructionsight import ceqanet_csv_evidence_series_cli as series_cli
from constructionsight.ceqanet_csv_access_policy_models import (
    CeqanetCsvAccessPolicy,
    CeqanetCsvAccessPolicyVerification,
)
from constructionsight.ceqanet_csv_evidence_series_cli import app
from constructionsight.ceqanet_csv_evidence_series_models import (
    CeqanetCsvEvidenceExecution,
    CeqanetCsvEvidenceSeries,
    CeqanetCsvEvidenceSeriesStatus,
    CeqanetCsvEvidenceSeriesVerification,
)
from constructionsight.ceqanet_csv_evidence_series_service import (
    EvidenceExecutionInput,
    build_ceqanet_csv_evidence_series,
    execute_ceqanet_csv_evidence_request,
    verify_ceqanet_csv_evidence_series,
)
from constructionsight.ceqanet_csv_live_models import CeqanetCsvLiveExecution
from constructionsight.ceqanet_csv_replay_models import (
    CeqanetCsvEncodingReplay,
    CeqanetCsvEncodingReplayVerification,
)
from constructionsight.ceqanet_csv_service import (
    build_ceqanet_csv_export_request,
)
from constructionsight.ceqanet_maturity_proposal_models import (
    CeqanetSourceMaturityProposal,
    CeqanetSourceMaturityProposalVerification,
)
from constructionsight.models import PublicSource

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_DIR = ROOT / "evidence/source_verification"
PROJECT_FIXTURE = ROOT / "tests/fixtures/ceqanet/project_export.csv"
DOCUMENT_FIXTURE = ROOT / "tests/fixtures/ceqanet/document_export.csv"
SERIES_PATH = EVIDENCE_DIR / "ceqanet_csv_evidence_series_2026-07-14.json"
SERIES_VERIFICATION_PATH = EVIDENCE_DIR / "ceqanet_csv_evidence_series_verification_2026-07-14.json"
SERIES_AUDIT_PATH = ROOT / "docs/audits/ceqanet_csv_evidence_series_2026-07-14.md"
OBSERVATION_EXECUTION_PATH = EVIDENCE_DIR / "ceqanet_csv_evidence_execution_2026-07-14_project.json"
SEQUENCE_ONE_SERIES_PATH = EVIDENCE_DIR / "ceqanet_csv_evidence_series_2026-07-14_sequence_1.json"
SEQUENCE_ONE_VERIFICATION_PATH = (
    EVIDENCE_DIR / "ceqanet_csv_evidence_series_verification_2026-07-14_sequence_1.json"
)
OBSERVATION_AUDIT_PATH = ROOT / "docs/audits/ceqanet_csv_evidence_observation_2026-07-14.md"
OBSERVATION_ARTIFACT_REF = (
    "evidence/source_verification/ceqanet_csv_evidence_execution_2026-07-14_project.json"
)
runner = CliRunner()
_ANSI_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sources() -> list[PublicSource]:
    payload = _load_json(ROOT / "data/source_registry.seed.json")
    assert isinstance(payload, list)
    return [PublicSource.model_validate(item) for item in payload]


def _original_execution() -> CeqanetCsvLiveExecution:
    return CeqanetCsvLiveExecution.model_validate(
        _load_json(EVIDENCE_DIR / "ceqanet_csv_live_execution_2026-07-12.json")
    )


def _replay() -> CeqanetCsvEncodingReplay:
    return CeqanetCsvEncodingReplay.model_validate(
        _load_json(EVIDENCE_DIR / "ceqanet_csv_windows1252_replay_2026-07-12.json")
    )


def _replay_verification() -> CeqanetCsvEncodingReplayVerification:
    return CeqanetCsvEncodingReplayVerification.model_validate(
        _load_json(EVIDENCE_DIR / "ceqanet_csv_windows1252_replay_verification_2026-07-12.json")
    )


def _maturity() -> CeqanetSourceMaturityProposal:
    return CeqanetSourceMaturityProposal.model_validate(
        _load_json(EVIDENCE_DIR / "ceqanet_source_maturity_proposal_2026-07-13.json")
    )


def _maturity_verification() -> CeqanetSourceMaturityProposalVerification:
    return CeqanetSourceMaturityProposalVerification.model_validate(
        _load_json(EVIDENCE_DIR / "ceqanet_source_maturity_proposal_verification_2026-07-13.json")
    )


def _policy() -> CeqanetCsvAccessPolicy:
    return CeqanetCsvAccessPolicy.model_validate(
        _load_json(EVIDENCE_DIR / "ceqanet_csv_access_policy_2026-07-14.json")
    )


def _policy_verification() -> CeqanetCsvAccessPolicyVerification:
    return CeqanetCsvAccessPolicyVerification.model_validate(
        _load_json(EVIDENCE_DIR / "ceqanet_csv_access_policy_verification_2026-07-14.json")
    )


def _build_series(
    executions: list[EvidenceExecutionInput],
) -> CeqanetCsvEvidenceSeries:
    return build_ceqanet_csv_evidence_series(
        _sources(),
        _original_execution(),
        _replay(),
        _replay_verification(),
        _maturity(),
        _maturity_verification(),
        _policy(),
        _policy_verification(),
        executions,
    )


@dataclass
class _Response:
    status_code: int
    content: bytes
    url: str
    headers: dict[str, str]


class _Client:
    def __init__(self, response: _Response) -> None:
        self.response = response
        self.calls: list[tuple[str, bool, float]] = []

    def get(
        self,
        url: str,
        *,
        follow_redirects: bool,
        timeout: float,
    ) -> _Response:
        self.calls.append((url, follow_redirects, timeout))
        return self.response


def _execute(
    series: CeqanetCsvEvidenceSeries,
    existing: list[EvidenceExecutionInput],
    *,
    day: int,
    document: bool = False,
    status_code: int = 200,
) -> tuple[str, CeqanetCsvEvidenceExecution, _Client]:
    if document:
        request = build_ceqanet_csv_export_request(
            sch_number="2026070311",
            document_id=1,
        )
        body = DOCUMENT_FIXTURE.read_bytes()
    else:
        request = build_ceqanet_csv_export_request(sch_number="2026030377")
        body = PROJECT_FIXTURE.read_bytes()
    if status_code != 200:
        body = b"Forbidden"
    client = _Client(
        _Response(
            status_code=status_code,
            content=body,
            url=request.source_url,
            headers={"content-type": "text/csv"},
        )
    )
    artifact_ref = (
        f"evidence/source_verification/ceqanet_csv_evidence_execution_2026-07-{day:02d}.json"
    )
    execution = execute_ceqanet_csv_evidence_request(
        _sources(),
        _original_execution(),
        _replay(),
        _replay_verification(),
        _maturity(),
        _maturity_verification(),
        _policy(),
        _policy_verification(),
        series,
        existing,
        request,
        execute_live=True,
        client=client,
        authorization_granted_at=datetime(2026, 7, day, 12, tzinfo=UTC),
        max_retained_rows=1_000,
    )
    return artifact_ref, execution, client


def test_empty_series_is_verified_collecting_and_nonproduction() -> None:
    series = _build_series([])
    verification = verify_ceqanet_csv_evidence_series(
        _sources(),
        _original_execution(),
        _replay(),
        _replay_verification(),
        _maturity(),
        _maturity_verification(),
        _policy(),
        _policy_verification(),
        [],
        series,
    )

    assert series.status is CeqanetCsvEvidenceSeriesStatus.COLLECTING
    assert series.observation_count == 0
    assert series.series_sequence == 0
    assert series.predecessor_series_digest is None
    assert series.successful_observation_count == 0
    assert series.source_promotion_authorized is False
    assert series.production_recurring_execution_authorized is False
    series.assert_integrity()
    assert verification.passed is True
    assert verification.ready_for_maturity_review is False


def test_governed_execution_performs_one_policy_bound_get() -> None:
    series = _build_series([])
    artifact_ref, execution, client = _execute(series, [], day=14)

    assert artifact_ref.endswith("2026-07-14.json")
    assert client.calls == [
        (
            "https://ceqanet.lci.ca.gov/Search?OutputFormat=CSV&Sch=2026030377",
            True,
            20.0,
        )
    ]
    assert execution.policy_digest == _policy().policy_digest
    assert execution.request_count == 1
    assert execution.live_execution.retry_count == 0
    assert execution.live_execution.retained_body_complete is True
    assert execution.live_verification.passed is True
    execution.assert_integrity()


def test_series_becomes_ready_only_after_all_policy_criteria() -> None:
    executions: list[EvidenceExecutionInput] = []
    series = _build_series(executions)
    for day, document in [(14, False), (15, True), (16, False), (17, True)]:
        predecessor_digest = series.series_digest
        artifact_ref, execution, _ = _execute(
            series,
            executions,
            day=day,
            document=document,
        )
        executions.append((artifact_ref, execution))
        series = _build_series(executions)
        assert series.series_sequence == len(executions)
        assert series.predecessor_series_digest == predecessor_digest

    assert series.observation_count == 4
    assert series.successful_observation_count == 4
    assert len(series.distinct_successful_utc_dates) == 4
    assert {kind.value for kind in series.observed_successful_export_kinds} == {
        "project",
        "document",
    }
    assert series.status is CeqanetCsvEvidenceSeriesStatus.READY_FOR_MATURITY_REVIEW
    assert series.source_promotion_authorized is False
    assert series.production_recurring_execution_authorized is False


def test_preflight_rejects_second_execution_on_same_utc_day() -> None:
    empty = _build_series([])
    artifact_ref, first, _ = _execute(empty, [], day=14)
    existing = [(artifact_ref, first)]
    series = _build_series(existing)

    with pytest.raises(ValueError, match="at most one execution per UTC day"):
        _execute(series, existing, day=14, document=True)


def test_access_control_response_halts_series_and_blocks_later_execution() -> None:
    empty = _build_series([])
    artifact_ref, forbidden, _ = _execute(
        empty,
        [],
        day=14,
        status_code=403,
    )
    existing = [(artifact_ref, forbidden)]
    series = _build_series(existing)

    assert series.status is CeqanetCsvEvidenceSeriesStatus.HALTED
    assert series.halted_on.isoformat() == "2026-07-14"
    assert series.halt_status_code == 403
    assert series.observations[0].verification_passed is False
    assert series.observations[0].access_control_halt is True

    with pytest.raises(ValueError, match="requires a collecting series"):
        _execute(series, existing, day=15)


def test_series_rejects_duplicate_execution_artifact_refs() -> None:
    empty = _build_series([])
    artifact_ref, execution, _ = _execute(empty, [], day=14)

    with pytest.raises(ValueError, match="artifact refs must be unique"):
        _build_series(
            [
                (artifact_ref, execution),
                (artifact_ref, execution.model_copy()),
            ]
        )


def test_verification_detects_tampered_series() -> None:
    series = _build_series([])
    tampered = series.model_copy(update={"next_gate": "silently promote the source"})

    verification = verify_ceqanet_csv_evidence_series(
        _sources(),
        _original_execution(),
        _replay(),
        _replay_verification(),
        _maturity(),
        _maturity_verification(),
        _policy(),
        _policy_verification(),
        [],
        tampered,
    )

    assert verification.passed is False
    assert verification.ready_for_maturity_review is False
    assert "CEQAnet CSV evidence series digest mismatch" in verification.findings
    assert any("does not match" in item for item in verification.findings)


def test_evidence_models_reject_unknown_fields() -> None:
    payload = _build_series([]).model_dump(mode="json")
    payload["unexpected"] = True

    with pytest.raises(ValidationError):
        CeqanetCsvEvidenceSeries.model_validate(payload)


def _canonical_cli_inputs() -> list[str]:
    return [
        str(ROOT / "data/source_registry.seed.json"),
        str(EVIDENCE_DIR / "ceqanet_csv_live_execution_2026-07-12.json"),
        str(EVIDENCE_DIR / "ceqanet_csv_windows1252_replay_2026-07-12.json"),
        str(EVIDENCE_DIR / "ceqanet_csv_windows1252_replay_verification_2026-07-12.json"),
        str(EVIDENCE_DIR / "ceqanet_source_maturity_proposal_2026-07-13.json"),
        str(EVIDENCE_DIR / "ceqanet_source_maturity_proposal_verification_2026-07-13.json"),
        str(EVIDENCE_DIR / "ceqanet_csv_access_policy_2026-07-14.json"),
        str(EVIDENCE_DIR / "ceqanet_csv_access_policy_verification_2026-07-14.json"),
    ]


def test_cli_builds_and_verifies_empty_series_offline(tmp_path: Path) -> None:
    series_path = tmp_path / "series.json"
    verification_path = tmp_path / "verification.json"
    inputs = _canonical_cli_inputs()

    build_result = runner.invoke(
        app,
        ["build", *inputs, "--output", str(series_path)],
    )
    assert build_result.exit_code == 0, build_result.output
    assert _load_json(series_path)["status"] == "collecting"

    verify_result = runner.invoke(
        app,
        [
            "verify",
            *inputs,
            str(series_path),
            "--output",
            str(verification_path),
        ],
    )
    assert verify_result.exit_code == 0, verify_result.output
    assert _load_json(verification_path)["passed"] is True


def test_cli_execute_refuses_missing_explicit_authorization(
    tmp_path: Path,
) -> None:
    series_path = tmp_path / "series.json"
    build_result = runner.invoke(
        app,
        [
            "build",
            *_canonical_cli_inputs(),
            "--output",
            str(series_path),
        ],
    )
    assert build_result.exit_code == 0, build_result.output

    result = runner.invoke(
        app,
        [
            "execute",
            *_canonical_cli_inputs(),
            str(series_path),
            "--sch-number",
            "2026030377",
            "--output",
            str(tmp_path / "execution.json"),
        ],
    )

    assert result.exit_code != 0
    assert "explicit --execute-live authorization is required" in _ANSI_ESCAPE.sub(
        "", result.output
    )


def test_cli_preflights_output_conflict_before_executor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    series_path = tmp_path / "series.json"
    build_result = runner.invoke(
        app,
        [
            "build",
            *_canonical_cli_inputs(),
            "--output",
            str(series_path),
        ],
    )
    assert build_result.exit_code == 0, build_result.output

    output_path = tmp_path / "execution.json"
    output_path.write_text("preserve existing evidence\n", encoding="utf-8")
    called = False

    def _unexpected_executor(*args: object, **kwargs: object) -> None:
        nonlocal called
        called = True
        raise AssertionError("executor must not run after output conflict")

    monkeypatch.setattr(
        series_cli,
        "execute_ceqanet_csv_evidence_request",
        _unexpected_executor,
    )
    result = runner.invoke(
        app,
        [
            "execute",
            *_canonical_cli_inputs(),
            str(series_path),
            "--sch-number",
            "2026030377",
            "--output",
            str(output_path),
            "--execute-live",
        ],
    )

    assert result.exit_code != 0
    assert "output already exists" in _ANSI_ESCAPE.sub("", result.output)
    assert called is False
    assert output_path.read_text(encoding="utf-8") == ("preserve existing evidence\n")


def test_evidence_execution_rejects_authorization_after_request() -> None:
    empty = _build_series([])
    _, execution, _ = _execute(empty, [], day=14)
    payload = execution.model_dump(mode="json")
    payload["authorization_granted_at"] = "2026-07-14T13:00:00Z"

    with pytest.raises(
        ValidationError,
        match="authorization cannot postdate",
    ):
        CeqanetCsvEvidenceExecution.model_validate(payload)


def test_series_rejects_noncanonical_artifact_ref() -> None:
    empty = _build_series([])
    _, execution, _ = _execute(empty, [], day=14)

    with pytest.raises(ValueError, match="canonical POSIX form"):
        _build_series([("evidence//execution.json", execution)])


def test_expired_policy_preflight_does_not_call_http_client() -> None:
    series = _build_series([])
    request = build_ceqanet_csv_export_request(sch_number="2026030377")
    client = _Client(
        _Response(
            status_code=200,
            content=PROJECT_FIXTURE.read_bytes(),
            url=request.source_url,
            headers={"content-type": "text/csv"},
        )
    )

    with pytest.raises(ValueError, match="policy has expired"):
        execute_ceqanet_csv_evidence_request(
            _sources(),
            _original_execution(),
            _replay(),
            _replay_verification(),
            _maturity(),
            _maturity_verification(),
            _policy(),
            _policy_verification(),
            series,
            [],
            request,
            execute_live=True,
            client=client,
            authorization_granted_at=datetime(
                2026,
                8,
                14,
                12,
                tzinfo=UTC,
            ),
        )

    assert client.calls == []


def test_committed_empty_series_recomputes_exactly() -> None:
    assert SERIES_PATH.is_file()
    assert SERIES_VERIFICATION_PATH.is_file()
    assert SERIES_AUDIT_PATH.is_file()

    series = CeqanetCsvEvidenceSeries.model_validate(_load_json(SERIES_PATH))
    stored = CeqanetCsvEvidenceSeriesVerification.model_validate(
        _load_json(SERIES_VERIFICATION_PATH)
    )
    recomputed = verify_ceqanet_csv_evidence_series(
        _sources(),
        _original_execution(),
        _replay(),
        _replay_verification(),
        _maturity(),
        _maturity_verification(),
        _policy(),
        _policy_verification(),
        [],
        series,
    )

    assert series.series_digest == (
        "b2a18770ec5ca28dfb907ce74b0b5ba120e6bb028ee35e3acd5188d42c182634"
    )
    assert series.status is CeqanetCsvEvidenceSeriesStatus.COLLECTING
    assert series.observation_count == 0
    assert recomputed == stored
    series.assert_integrity()


def test_verification_detects_forked_predecessor_digest() -> None:
    empty = _build_series([])
    artifact_ref, execution, _ = _execute(empty, [], day=14)
    series = _build_series([(artifact_ref, execution)])
    forked = series.model_copy(update={"predecessor_series_digest": "0" * 64})

    verification = verify_ceqanet_csv_evidence_series(
        _sources(),
        _original_execution(),
        _replay(),
        _replay_verification(),
        _maturity(),
        _maturity_verification(),
        _policy(),
        _policy_verification(),
        [(artifact_ref, execution)],
        forked,
    )

    assert verification.passed is False
    assert verification.ready_for_maturity_review is False
    assert any("does not match" in item for item in verification.findings)


def test_row_retention_preflight_does_not_call_http_client() -> None:
    series = _build_series([])
    request = build_ceqanet_csv_export_request(sch_number="2026030377")
    client = _Client(
        _Response(
            status_code=200,
            content=PROJECT_FIXTURE.read_bytes(),
            url=request.source_url,
            headers={"content-type": "text/csv"},
        )
    )

    with pytest.raises(
        ValueError,
        match="max_retained_rows must be between 0 and 1000",
    ):
        execute_ceqanet_csv_evidence_request(
            _sources(),
            _original_execution(),
            _replay(),
            _replay_verification(),
            _maturity(),
            _maturity_verification(),
            _policy(),
            _policy_verification(),
            series,
            [],
            request,
            execute_live=True,
            client=client,
            authorization_granted_at=datetime(
                2026,
                7,
                14,
                12,
                tzinfo=UTC,
            ),
            max_retained_rows=1_001,
        )

    assert client.calls == []


def test_ready_series_preflight_does_not_call_http_client() -> None:
    executions: list[EvidenceExecutionInput] = []
    series = _build_series(executions)
    for day, document in [(14, False), (15, True), (16, False), (17, True)]:
        artifact_ref, execution, _ = _execute(
            series,
            executions,
            day=day,
            document=document,
        )
        executions.append((artifact_ref, execution))
        series = _build_series(executions)
    assert series.status is CeqanetCsvEvidenceSeriesStatus.READY_FOR_MATURITY_REVIEW

    request = build_ceqanet_csv_export_request(sch_number="2026030377")
    client = _Client(
        _Response(
            status_code=200,
            content=PROJECT_FIXTURE.read_bytes(),
            url=request.source_url,
            headers={"content-type": "text/csv"},
        )
    )
    with pytest.raises(ValueError, match="requires a collecting series"):
        execute_ceqanet_csv_evidence_request(
            _sources(),
            _original_execution(),
            _replay(),
            _replay_verification(),
            _maturity(),
            _maturity_verification(),
            _policy(),
            _policy_verification(),
            series,
            executions,
            request,
            execute_live=True,
            client=client,
            authorization_granted_at=datetime(
                2026,
                7,
                18,
                12,
                tzinfo=UTC,
            ),
        )

    assert client.calls == []


def test_committed_first_observation_recomputes_exactly() -> None:
    assert OBSERVATION_EXECUTION_PATH.is_file()
    assert SEQUENCE_ONE_SERIES_PATH.is_file()
    assert SEQUENCE_ONE_VERIFICATION_PATH.is_file()
    assert OBSERVATION_AUDIT_PATH.is_file()

    evidence_execution = CeqanetCsvEvidenceExecution.model_validate(
        _load_json(OBSERVATION_EXECUTION_PATH)
    )
    series = CeqanetCsvEvidenceSeries.model_validate(_load_json(SEQUENCE_ONE_SERIES_PATH))
    stored_verification = CeqanetCsvEvidenceSeriesVerification.model_validate(
        _load_json(SEQUENCE_ONE_VERIFICATION_PATH)
    )
    recomputed = verify_ceqanet_csv_evidence_series(
        _sources(),
        _original_execution(),
        _replay(),
        _replay_verification(),
        _maturity(),
        _maturity_verification(),
        _policy(),
        _policy_verification(),
        [(OBSERVATION_ARTIFACT_REF, evidence_execution)],
        series,
    )

    assert evidence_execution.evidence_execution_digest == (
        "57c2c3a64f65f6cd7ca8e512c862d02fe92b04fcaa7cc1bb6eaeb7b091857f10"
    )
    assert evidence_execution.live_execution.status_code == 200
    assert evidence_execution.live_execution.retry_count == 0
    assert evidence_execution.live_execution.retained_body_complete is True
    assert evidence_execution.live_execution.retained_body_byte_length == 7_832
    assert evidence_execution.live_execution.body_sha256 == (
        "5b1bc503c81d12ed0f00e52539edb437b42ae4c3a539a25e1c82a02b84273163"
    )
    assert evidence_execution.live_verification.passed is True
    assert evidence_execution.live_verification.finding_count == 0
    evidence_execution.assert_integrity()

    assert series.series_sequence == 1
    assert series.predecessor_series_digest == (
        "b2a18770ec5ca28dfb907ce74b0b5ba120e6bb028ee35e3acd5188d42c182634"
    )
    assert series.series_digest == (
        "a6f6e548d675ee9716822fef87cc02d8a4d169f16ab151bae0f297321b8c07df"
    )
    assert series.status is CeqanetCsvEvidenceSeriesStatus.COLLECTING
    assert series.observation_count == 1
    assert series.successful_observation_count == 1
    assert recomputed == stored_verification
    assert recomputed.ready_for_maturity_review is False
    series.assert_integrity()


def test_socks_proxy_transport_is_declared_and_installed() -> None:
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert '"httpx[socks]==0.28.1"' in pyproject
    assert socksio is not None
