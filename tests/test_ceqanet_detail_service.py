from __future__ import annotations

from datetime import UTC, datetime

import pytest

from constructionsight.authorization_decision import (
    AuthorizationDeniedError,
    AuthorizationUseLedger,
)
from constructionsight.ceqanet_detail_service import execute_authorized_ceqanet_detail
from constructionsight.legal import SourceAccessProfile

_DETAIL_URL = "https://ceqanet.lci.ca.gov/Project/Example"
_NOW = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)


class _Executor:
    def __init__(self) -> None:
        self.calls: list[tuple[str, float, int]] = []

    def __call__(
        self,
        url: str,
        *,
        timeout_seconds: float,
        max_body_bytes: int,
    ) -> dict[str, object]:
        self.calls.append((url, timeout_seconds, max_body_bytes))
        return {
            "policy_id": "CS-NET-006",
            "method": "GET",
            "request_url": url,
            "final_url": url,
            "status_code": 200,
            "content_type": "text/html",
            "content_encoding": "utf-8",
            "body_text": "detail",
            "body_length": 6,
            "body_truncated": False,
            "executed": True,
            "failure_kind": "none",
            "error": None,
            "reachable": True,
            "attempt_count": 1,
        }


def _profile(**changes: object) -> SourceAccessProfile:
    return SourceAccessProfile(
        public_url="https://ceqanet.lci.ca.gov/",
        **changes,
    )


def _execute(
    executor: _Executor,
    *,
    profile: SourceAccessProfile | None = None,
    confirmation: bool = True,
    ledger: AuthorizationUseLedger | None = None,
    timeout_seconds: float = 20.0,
    max_body_bytes: int = 50_000,
) -> dict[str, object]:
    return execute_authorized_ceqanet_detail(
        detail_url=_DETAIL_URL,
        access_profile=profile or _profile(),
        operator_id="operator:tyler",
        authorization_reason="Review one exact public project page.",
        caller_confirmation=confirmation,
        timeout_seconds=timeout_seconds,
        max_body_bytes=max_body_bytes,
        now=lambda: _NOW,
        ledger=ledger,
        executor=executor,
    )


def test_detail_service_emits_scope_bound_authorization_and_snapshot() -> None:
    executor = _Executor()

    payload = _execute(executor)

    metadata = payload["metadata"]
    assert isinstance(metadata, dict)
    authorization = metadata["authorization"]
    assert isinstance(authorization, dict)
    assert str(authorization["decision_id"]).startswith("authorization-decision:")
    assert str(authorization["preflight_id"]).startswith("authorization-preflight:")
    assert authorization["actor_id"] == "operator:tyler"
    assert authorization["action"] == "execute-ceqanet-detail-read"
    assert "credential use" in authorization["denied_authority"]
    assert "repeat execution" in authorization["denied_authority"]
    assert metadata["successful_response_count"] == 1
    assert executor.calls == [(_DETAIL_URL, 20.0, 50_000)]


def test_boolean_confirmation_is_insufficient_without_complete_decision() -> None:
    executor = _Executor()

    with pytest.raises(AuthorizationDeniedError, match="in addition"):
        _execute(executor, confirmation=False)

    assert executor.calls == []


def test_lawful_access_denial_prevents_transport_execution() -> None:
    executor = _Executor()

    with pytest.raises(AuthorizationDeniedError, match="requires_login"):
        _execute(executor, profile=_profile(requires_login=True))

    assert executor.calls == []


@pytest.mark.parametrize(
    ("timeout_seconds", "max_body_bytes", "message"),
    (
        (20.001, 50_000, "timeout_seconds"),
        (20.0, 50_001, "max_body_bytes"),
    ),
)
def test_runtime_cannot_raise_declared_policy_ceilings(
    timeout_seconds: float,
    max_body_bytes: int,
    message: str,
) -> None:
    executor = _Executor()

    with pytest.raises(ValueError, match=message):
        _execute(
            executor,
            timeout_seconds=timeout_seconds,
            max_body_bytes=max_body_bytes,
        )

    assert executor.calls == []


def test_detail_service_rejects_non_ceqanet_or_credentialed_url() -> None:
    executor = _Executor()
    cases = (
        "https://example.com/Project/Example",
        "https://user:secret@ceqanet.lci.ca.gov/Project/Example",
        "http://ceqanet.lci.ca.gov/Project/Example",
    )
    for url in cases:
        with pytest.raises(ValueError):
            execute_authorized_ceqanet_detail(
                detail_url=url,
                access_profile=_profile(),
                operator_id="operator:tyler",
                authorization_reason="Review one exact public project page.",
                caller_confirmation=True,
                timeout_seconds=20.0,
                max_body_bytes=50_000,
                now=lambda: _NOW,
                executor=executor,
            )

    assert executor.calls == []


def test_shared_ledger_rejects_repeated_identical_execution() -> None:
    executor = _Executor()
    ledger = AuthorizationUseLedger()

    first = _execute(executor, ledger=ledger)
    assert first["metadata"]
    with pytest.raises(AuthorizationDeniedError, match="already consumed"):
        _execute(executor, ledger=ledger)

    assert executor.calls == [(_DETAIL_URL, 20.0, 50_000)]
