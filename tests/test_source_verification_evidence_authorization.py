from __future__ import annotations

import inspect
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

import constructionsight.source_readiness_service as readiness_service
from constructionsight.adapters import default_adapter_family_specs
from constructionsight.authorization_decision import (
    AuthorizationDeniedError,
    AuthorizationUseLedger,
)
from constructionsight.models import PublicSource
from constructionsight.source_readiness_models import HttpReachabilityResult
from constructionsight.source_verification_evidence_service import (
    build_authorized_source_verification_evidence_package,
)

ROOT = Path(__file__).resolve().parents[1]
_NOW = datetime(2026, 7, 16, 12, 0, tzinfo=UTC)


def _sources() -> list[PublicSource]:
    payload = json.loads((ROOT / "data/source_registry.seed.json").read_text())
    assert isinstance(payload, list)
    return [PublicSource.model_validate(item) for item in payload[:2]]


class _Checker:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def __call__(self, source: PublicSource) -> HttpReachabilityResult:
        self.calls.append(str(source.public_url))
        return HttpReachabilityResult(
            checked=True,
            reachable=True,
            status_code=200,
            method="HEAD",
            final_url=str(source.public_url),
            error=None,
        )


def _build(
    *,
    confirmation: bool = True,
    ledger: AuthorizationUseLedger | None = None,
):
    return build_authorized_source_verification_evidence_package(
        _sources(),
        default_adapter_family_specs(),
        caller_confirmation=confirmation,
        authorization_reason="Build one reviewed source evidence package.",
        operator_id="operator:tyler",
        now=lambda: _NOW,
        ledger=ledger,
    )


def test_authorized_evidence_package_executes_exact_source_set_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checker = _Checker()
    monkeypatch.setattr(readiness_service, "_check_source_http_reachability", checker)

    package = _build()

    assert package.source_count == 2
    assert checker.calls == [str(source.public_url) for source in _sources()]
    assert all(row.http_checked for row in package.rows)


def test_evidence_package_requires_scope_bound_confirmation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checker = _Checker()
    monkeypatch.setattr(readiness_service, "_check_source_http_reachability", checker)

    with pytest.raises(AuthorizationDeniedError, match="in addition"):
        _build(confirmation=False)

    assert checker.calls == []


def test_shared_ledger_rejects_repeated_evidence_package_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checker = _Checker()
    monkeypatch.setattr(readiness_service, "_check_source_http_reachability", checker)
    ledger = AuthorizationUseLedger()

    _build(ledger=ledger)
    with pytest.raises(AuthorizationDeniedError, match="already consumed"):
        _build(ledger=ledger)

    assert len(checker.calls) == 2


def test_authorized_evidence_package_does_not_accept_http_checker() -> None:
    assert "http_checker" not in inspect.signature(
        build_authorized_source_verification_evidence_package
    ).parameters
