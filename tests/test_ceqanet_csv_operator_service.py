from __future__ import annotations

import base64
import hashlib
from datetime import UTC, datetime

import pytest

from constructionsight.authorization_decision import (
    AuthorizationDeniedError,
    AuthorizationUseLedger,
)
from constructionsight.ceqanet_csv_live_models import (
    CeqanetCsvLiveExecution,
    CeqanetCsvLiveVerification,
)
from constructionsight.ceqanet_csv_models import CeqanetCsvExportRequest
from constructionsight.ceqanet_csv_service import build_ceqanet_csv_export_request
from constructionsight.legal import SourceAccessProfile
from constructionsight.operator_services.ceqanet_csv_service import (
    execute_authorized_ceqanet_csv,
)

_NOW = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)


class _Executor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, bool, float, int, int]] = []

    def __call__(
        self,
        request: CeqanetCsvExportRequest,
        *,
        execute_live: bool,
        timeout_seconds: float,
        max_body_bytes: int,
        max_retained_rows: int,
        executed_at: datetime | None = None,
    ) -> CeqanetCsvLiveExecution:
        self.calls.append(
            (
                request.source_url,
                execute_live,
                timeout_seconds,
                max_body_bytes,
                max_retained_rows,
            )
        )
        body = b"synthetic terminal response"
        draft = CeqanetCsvLiveExecution(
            request=request,
            request_url=request.source_url,
            final_url=request.source_url,
            status_code=500,
            content_type="text/plain",
            content_disposition=None,
            observed_body_byte_length=len(body),
            retained_body_base64=base64.b64encode(body).decode("ascii"),
            retained_body_byte_length=len(body),
            retained_body_complete=True,
            body_sha256=hashlib.sha256(body).hexdigest(),
            error="synthetic_terminal_response",
            inspection=None,
            inspection_error=None,
            executed_at=executed_at or _NOW,
            execution_digest="0" * 64,
        )
        return draft.model_copy(update={"execution_digest": draft.computed_digest()})


class _Verifier:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def __call__(
        self,
        execution: CeqanetCsvLiveExecution,
    ) -> CeqanetCsvLiveVerification:
        self.calls.append(execution.execution_digest)
        return CeqanetCsvLiveVerification(
            passed=True,
            finding_count=0,
            findings=[],
            request_url=execution.request_url,
            status_code=execution.status_code,
            inspection_digest=None,
            execution_digest=execution.execution_digest,
        )


def _profile(**changes: object) -> SourceAccessProfile:
    return SourceAccessProfile(
        public_url="https://ceqanet.lci.ca.gov/",
        **changes,
    )


def _execute(
    executor: _Executor,
    verifier: _Verifier,
    *,
    confirmation: bool = True,
    profile: SourceAccessProfile | None = None,
    ledger: AuthorizationUseLedger | None = None,
):
    return execute_authorized_ceqanet_csv(
        request=build_ceqanet_csv_export_request(sch_number="2026030377"),
        access_profile=profile or _profile(),
        authorization_reason="Execute one reviewed CEQAnet CSV evidence request.",
        caller_confirmation=confirmation,
        timeout_seconds=20.0,
        max_body_bytes=10_000_000,
        max_retained_rows=1_000,
        operator_id="operator:tyler",
        now=lambda: _NOW,
        ledger=ledger,
        executor=executor,
        verifier=verifier,
    )


def test_csv_service_binds_exact_request_policy_and_negative_authority() -> None:
    executor = _Executor()
    verifier = _Verifier()

    result = _execute(executor, verifier)

    authorization = result.authorization.to_dict()
    assert authorization["action"] == "execute-ceqanet-csv-evidence-request"
    assert str(authorization["decision_id"]).startswith("authorization-decision:")
    assert str(authorization["preflight_id"]).startswith("authorization-preflight:")
    assert "retry" in authorization["denied_authority"]
    assert "request mutation" in authorization["denied_authority"]
    assert executor.calls == [
        (
            "https://ceqanet.lci.ca.gov/Search?OutputFormat=CSV&Sch=2026030377",
            True,
            20.0,
            10_000_000,
            1_000,
        )
    ]
    assert verifier.calls == [result.execution.execution_digest]
    assert result.verification.passed is True


def test_boolean_confirmation_cannot_authorize_csv_execution() -> None:
    executor = _Executor()
    verifier = _Verifier()

    with pytest.raises(AuthorizationDeniedError, match="in addition"):
        _execute(executor, verifier, confirmation=False)

    assert executor.calls == []
    assert verifier.calls == []


def test_lawful_access_state_blocks_csv_execution_before_transport() -> None:
    executor = _Executor()
    verifier = _Verifier()

    with pytest.raises(AuthorizationDeniedError, match="requires_login"):
        _execute(executor, verifier, profile=_profile(requires_login=True))

    assert executor.calls == []
    assert verifier.calls == []


def test_shared_ledger_rejects_repeated_csv_execution() -> None:
    executor = _Executor()
    verifier = _Verifier()
    ledger = AuthorizationUseLedger()

    first = _execute(executor, verifier, ledger=ledger)
    assert first.verification.passed is True
    with pytest.raises(AuthorizationDeniedError, match="already consumed"):
        _execute(executor, verifier, ledger=ledger)

    assert len(executor.calls) == 1
    assert len(verifier.calls) == 1


def test_csv_service_rejects_scope_expansion_beyond_policy() -> None:
    executor = _Executor()
    verifier = _Verifier()

    with pytest.raises(ValueError, match="between 0 and 1000"):
        execute_authorized_ceqanet_csv(
            request=build_ceqanet_csv_export_request(sch_number="2026030377"),
            access_profile=_profile(),
            authorization_reason="Attempt an excessive retained-row scope.",
            caller_confirmation=True,
            timeout_seconds=20.0,
            max_body_bytes=10_000_000,
            max_retained_rows=1_001,
            operator_id="operator:tyler",
            now=lambda: _NOW,
            executor=executor,
            verifier=verifier,
        )

    assert executor.calls == []
    assert verifier.calls == []
