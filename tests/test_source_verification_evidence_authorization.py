from __future__ import annotations

import inspect
import json
from pathlib import Path

import pytest

import constructionsight.source_readiness_service as readiness_service
from constructionsight.adapters import default_adapter_family_specs
from constructionsight.authorization_decision import AuthorizationDeniedError
from constructionsight.models import PublicSource
from constructionsight.source_readiness_models import HttpReachabilityResult
from constructionsight.source_verification_evidence_service import (
    build_authorized_source_verification_evidence_package,
)

ROOT = Path(__file__).resolve().parents[1]
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
):
    return build_authorized_source_verification_evidence_package(
        _sources(),
        default_adapter_family_specs(),
        caller_confirmation=confirmation,
        authorization_reason="Build one reviewed source evidence package.",
        operator_id="operator:tyler",
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


def test_exact_replay_returns_evidence_without_repeating_checks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checker = _Checker()
    monkeypatch.setattr(readiness_service, "_check_source_http_reachability", checker)
    first = _build()
    replay = _build()

    assert replay.source_count == first.source_count
    assert [row.source_key for row in replay.rows] == [
        row.source_key for row in first.rows
    ]
    assert all(row.http_checked for row in replay.rows)
    assert len(checker.calls) == 2


def test_authorized_evidence_package_does_not_accept_http_checker() -> None:
    parameters = inspect.signature(
        build_authorized_source_verification_evidence_package
    ).parameters
    assert "http_checker" not in parameters
    assert "ledger" not in parameters
    assert "now" not in parameters
