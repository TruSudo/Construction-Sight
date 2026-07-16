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
from constructionsight.source_readiness_service import (
    build_authorized_source_readiness_report,
    build_source_readiness_report,
)

ROOT = Path(__file__).resolve().parents[1]
_NOW = datetime(2026, 7, 15, 12, 0, tzinfo=UTC)


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


def test_offline_readiness_does_not_acquire_network_authority() -> None:
    checker = _Checker()

    report = build_source_readiness_report(
        _sources(),
        default_adapter_family_specs(),
        check_http=False,
        http_checker=checker,
    )

    assert report.source_count == 2
    assert checker.calls == []
    assert all(not row.http_reachability.checked for row in report.rows)


def test_authorized_readiness_binds_exact_source_set_and_runs_once() -> None:
    checker = _Checker()
    sources = _sources()

    report = build_authorized_source_readiness_report(
        sources,
        default_adapter_family_specs(),
        caller_confirmation=True,
        authorization_reason="Perform one reviewed reachability check.",
        operator_id="operator:tyler",
        now=lambda: _NOW,
        http_checker=checker,
    )

    assert report.source_count == len(sources)
    assert checker.calls == [str(source.public_url) for source in sources]
    assert all(row.http_reachability.checked for row in report.rows)


def test_boolean_confirmation_cannot_be_omitted_for_live_readiness() -> None:
    checker = _Checker()

    with pytest.raises(AuthorizationDeniedError, match="in addition"):
        build_authorized_source_readiness_report(
            _sources(),
            default_adapter_family_specs(),
            caller_confirmation=False,
            authorization_reason="Attempt live readiness without confirmation.",
            operator_id="operator:tyler",
            now=lambda: _NOW,
            http_checker=checker,
        )

    assert checker.calls == []


def test_shared_ledger_rejects_repeated_source_set_check() -> None:
    checker = _Checker()
    ledger = AuthorizationUseLedger()
    sources = _sources()

    build_authorized_source_readiness_report(
        sources,
        default_adapter_family_specs(),
        caller_confirmation=True,
        authorization_reason="Perform one reviewed reachability check.",
        operator_id="operator:tyler",
        now=lambda: _NOW,
        ledger=ledger,
        http_checker=checker,
    )
    with pytest.raises(AuthorizationDeniedError, match="already consumed"):
        build_authorized_source_readiness_report(
            sources,
            default_adapter_family_specs(),
            caller_confirmation=True,
            authorization_reason="Perform one reviewed reachability check.",
            operator_id="operator:tyler",
            now=lambda: _NOW,
            ledger=ledger,
            http_checker=checker,
        )

    assert len(checker.calls) == len(sources)
