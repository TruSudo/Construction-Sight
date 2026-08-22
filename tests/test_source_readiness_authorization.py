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


def test_offline_readiness_does_not_acquire_network_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checker = _Checker()
    monkeypatch.setattr(readiness_service, "_check_source_http_reachability", checker)

    report = build_source_readiness_report(
        _sources(),
        default_adapter_family_specs(),
        check_http=False,
    )

    assert report.source_count == 2
    assert checker.calls == []
    assert all(not row.http_reachability.checked for row in report.rows)


def test_offline_readiness_rejects_live_http_request() -> None:
    with pytest.raises(ValueError, match="requires build_authorized"):
        build_source_readiness_report(
            _sources(),
            default_adapter_family_specs(),
            check_http=True,
        )


def test_authorized_readiness_binds_exact_source_set_and_runs_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checker = _Checker()
    monkeypatch.setattr(readiness_service, "_check_source_http_reachability", checker)
    sources = _sources()

    report = build_authorized_source_readiness_report(
        sources,
        default_adapter_family_specs(),
        caller_confirmation=True,
        authorization_reason="Perform one reviewed reachability check.",
        operator_id="operator:tyler",
        now=lambda: _NOW,
    )

    assert report.source_count == len(sources)
    assert checker.calls == [str(source.public_url) for source in sources]
    assert all(row.http_reachability.checked for row in report.rows)


def test_boolean_confirmation_cannot_be_omitted_for_live_readiness(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checker = _Checker()
    monkeypatch.setattr(readiness_service, "_check_source_http_reachability", checker)

    with pytest.raises(AuthorizationDeniedError, match="in addition"):
        build_authorized_source_readiness_report(
            _sources(),
            default_adapter_family_specs(),
            caller_confirmation=False,
            authorization_reason="Attempt live readiness without confirmation.",
            operator_id="operator:tyler",
            now=lambda: _NOW,
        )

    assert checker.calls == []


def test_shared_ledger_rejects_repeated_source_set_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checker = _Checker()
    monkeypatch.setattr(readiness_service, "_check_source_http_reachability", checker)
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
        )

    assert len(checker.calls) == len(sources)


def test_authorized_readiness_does_not_accept_caller_selected_http_checker() -> None:
    assert "http_checker" not in inspect.signature(
        build_authorized_source_readiness_report
    ).parameters
