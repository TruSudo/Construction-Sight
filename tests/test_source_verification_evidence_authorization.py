from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

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
    checker: _Checker,
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
        http_checker=checker,
    )


def test_authorized_evidence_package_executes_exact_source_set_once() -> None:
    checker = _Checker()

    package = _build(checker)

    assert package.source_count == 2
    assert checker.calls == [str(source.public_url) for source in _sources()]
    assert all(row.http_checked for row in package.rows)


def test_evidence_package_requires_scope_bound_confirmation() -> None:
    checker = _Checker()

    with pytest.raises(AuthorizationDeniedError, match="in addition"):
        _build(checker, confirmation=False)

    assert checker.calls == []


def test_shared_ledger_rejects_repeated_evidence_package_check() -> None:
    checker = _Checker()
    ledger = AuthorizationUseLedger()

    _build(checker, ledger=ledger)
    with pytest.raises(AuthorizationDeniedError, match="already consumed"):
        _build(checker, ledger=ledger)

    assert len(checker.calls) == 2
