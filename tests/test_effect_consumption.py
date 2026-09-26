from __future__ import annotations

import inspect
import json
import multiprocessing
import os
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from queue import Empty
from threading import Event, Lock

import pytest

import constructionsight.effect_consumption as effect_consumption
from constructionsight.authorization_decision_models import authorization_digest
from constructionsight.effect_consumption import _execute_owned_effect
from constructionsight.effect_consumption_models import (
    EffectConsumptionStatus,
    EffectOperation,
    EffectReplayPolicy,
)
from constructionsight.local_operator_authorization import (
    LocalAuthorizationResult,
    authorize_local_operator_operation,
)
from constructionsight.storage.effect_consumption_store import (
    EffectConsumptionError,
    EffectConsumptionStore,
    EffectOutcomeUnavailableError,
    EffectReplayConflictError,
)

_NOW = datetime(2026, 8, 22, 12, 0, tzinfo=UTC)


def _authorization(
    reason: str = "Exercise the durable protected-effect boundary.",
) -> LocalAuthorizationResult:
    return authorize_local_operator_operation(
        action="execute-consumption-test",
        resource_type="test-effect",
        resource_id="resource:effect-consumption",
        exact_scope=("content:one", "operation:test"),
        current_state_identity="state:reviewed",
        expected_identity="state:reviewed",
        granted_authority=("execute one exact protected test effect",),
        denied_authority=("repeat protected effect", "scope expansion"),
        reason=reason,
        caller_confirmation=True,
        limitations=("test authority only",),
        operator_id="operator:test",
    )


def _run(
    authorization: LocalAuthorizationResult,
    effect,
    *,
    allowance_identity: str = "allowance:one",
    content_identity: str = "content:one",
    replay_policy: EffectReplayPolicy = EffectReplayPolicy.EXACT,
) -> dict[str, object]:
    return _execute_owned_effect(
        authorization,
        allowance_identity=allowance_identity,
        content_identity=content_identity,
        implementation_id="tests.test_effect_consumption.owned_effect",
        replay_policy=replay_policy,
        effect=effect,
        encode_result=lambda result: result,
        decode_result=lambda payload: dict(payload),
    )


def _operation() -> EffectOperation:
    return EffectOperation(
        reservation_key="effect-reservation:" + "1" * 64,
        operation_digest="effect-operation:" + "2" * 64,
        decision_id="authorization-decision:" + "3" * 64,
        authority_digest="logical-authorization:" + "4" * 64,
        actor_id="operator:test",
        action="execute-consumption-test",
        resource_type="test-effect",
        resource_id="resource:effect-consumption",
        exact_scope_digest="effect-exact-scope:" + "5" * 64,
        current_state_identity="state:reviewed",
        allowance_identity="allowance:one",
        content_identity="content:one",
        implementation_id="tests.test_effect_consumption.owned_effect",
        replay_policy=EffectReplayPolicy.EXACT,
    )


def _crash_after_start(database_path: str, operation: EffectOperation) -> None:
    store = EffectConsumptionStore(Path(database_path))
    store.reserve(operation, reserved_at=_NOW)
    store.mark_effect_started(operation, started_at=_NOW)
    os._exit(0)


def _process_file_effect(
    database_path: str,
    evidence_path: str,
    authorization: LocalAuthorizationResult,
    start,
    results,
) -> None:
    effect_consumption._CONSUMPTION_DATABASE_PATH = Path(database_path)
    start.wait(10)

    def append_evidence(_trusted_at: datetime) -> dict[str, object]:
        with Path(evidence_path).open("a", encoding="utf-8") as stream:
            stream.write("retained-evidence\n")
            stream.flush()
            os.fsync(stream.fileno())
        return {"artifact": "retained-evidence", "sequence": 1}

    try:
        value = _run(
            authorization,
            append_evidence,
            allowance_identity="ceqanet-daily:2026-08-22",
            content_identity="ceqanet-series:reviewed-sequence-1",
        )
    except Exception as exc:
        results.put(("error", type(exc).__name__))
    else:
        results.put(("ok", value["artifact"]))


def test_sequential_exact_replay_returns_retained_result_without_effect() -> None:
    authorization = _authorization()
    calls = 0

    def effect(_trusted_at: datetime) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"outcome": "committed", "revision": 1}

    first = _run(authorization, effect)
    replay = _run(_authorization(), effect)

    assert first == {"outcome": "committed", "revision": 1}
    assert replay == first
    assert calls == 1


def test_changed_content_conflicts_with_consumed_allowance() -> None:
    authorization = _authorization()
    _run(authorization, lambda _when: {"outcome": "committed"})

    with pytest.raises(EffectReplayConflictError, match="changed scope"):
        _run(
            _authorization(),
            lambda _when: {"outcome": "mutated"},
            content_identity="content:substituted",
        )


def test_changed_authority_reason_conflicts_with_consumed_allowance() -> None:
    _run(_authorization(), lambda _when: {"outcome": "committed"})

    with pytest.raises(EffectReplayConflictError, match="changed scope"):
        _run(
            _authorization("Substitute a different authority reason."),
            lambda _when: {"outcome": "mutated"},
        )


def test_single_use_policy_denies_duplicate_after_success() -> None:
    authorization = _authorization()
    _run(
        authorization,
        lambda _when: {"outcome": "committed"},
        replay_policy=EffectReplayPolicy.DENY,
    )

    with pytest.raises(EffectConsumptionError, match="already consumed"):
        _run(
            _authorization(),
            lambda _when: {"outcome": "reexecuted"},
            replay_policy=EffectReplayPolicy.DENY,
        )


def test_concurrent_duplicate_cannot_cross_effect_boundary_twice() -> None:
    authorization = _authorization()
    entered = Event()
    release = Event()
    calls = 0
    calls_lock = Lock()

    def effect(_trusted_at: datetime) -> dict[str, object]:
        nonlocal calls
        with calls_lock:
            calls += 1
            call_number = calls
        entered.set()
        if call_number == 1:
            assert release.wait(10)
        return {"outcome": "committed"}

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(_run, authorization, effect)
        assert entered.wait(10)
        duplicate = executor.submit(_run, _authorization(), effect)
        try:
            with pytest.raises(
                EffectOutcomeUnavailableError,
                match="reserved|indeterminate",
            ):
                duplicate.result(timeout=10)
        finally:
            release.set()
        assert first.result(timeout=10) == {"outcome": "committed"}

    assert calls == 1


def test_restart_replays_committed_result_from_new_store_instance(tmp_path: Path) -> None:
    database_path = tmp_path / "restart.sqlite3"
    operation = _operation()
    first_store = EffectConsumptionStore(database_path)
    first_store.reserve(operation, reserved_at=_NOW)
    first_store.mark_effect_started(operation, started_at=_NOW)
    payload = {"outcome": "committed", "revision": 7}
    first_store.commit_success(
        operation,
        completed_at=_NOW,
        result_json=json.dumps(payload, sort_keys=True, separators=(",", ":")),
        result_digest=authorization_digest("effect-result", payload),
    )

    replay = EffectConsumptionStore(database_path).reserve(operation, reserved_at=_NOW)

    assert replay.exact_replay is True
    assert replay.record.status is EffectConsumptionStatus.SUCCEEDED
    assert json.loads(replay.record.result_json or "null") == payload


def test_crash_after_effect_start_remains_indeterminate_after_restart(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "crash.sqlite3"
    operation = _operation()
    context = multiprocessing.get_context("fork")
    process = context.Process(
        target=_crash_after_start,
        args=(str(database_path), operation),
    )
    process.start()
    process.join(10)

    assert process.exitcode == 0
    with pytest.raises(EffectOutcomeUnavailableError, match="indeterminate"):
        EffectConsumptionStore(database_path).reserve(operation, reserved_at=_NOW)


def test_failure_before_effect_start_is_terminal_and_durable(tmp_path: Path) -> None:
    database_path = tmp_path / "failure-before.sqlite3"
    operation = _operation()
    store = EffectConsumptionStore(database_path)
    store.reserve(operation, reserved_at=_NOW)
    store.commit_failure(
        operation,
        completed_at=_NOW,
        effect_started=False,
        failure_type="tests.SyntheticPreEffectFailure",
        failure_digest="effect-failure:" + "6" * 64,
    )

    record = EffectConsumptionStore(database_path).load(operation.reservation_key)
    assert record is not None
    assert record.status is EffectConsumptionStatus.FAILED
    assert record.failure_phase == "before_effect"
    with pytest.raises(EffectOutcomeUnavailableError, match="terminal failure"):
        EffectConsumptionStore(database_path).reserve(operation, reserved_at=_NOW)


def test_failure_after_effect_is_terminal_and_never_reexecutes(tmp_path: Path) -> None:
    authorization = _authorization()
    evidence_path = tmp_path / "effect-marker.txt"

    def partial_effect(_trusted_at: datetime) -> dict[str, object]:
        with evidence_path.open("a", encoding="utf-8") as stream:
            stream.write("effect-crossed\n")
        raise RuntimeError("synthetic failure after protected effect")

    with pytest.raises(RuntimeError, match="synthetic failure"):
        _run(authorization, partial_effect)
    with pytest.raises(EffectOutcomeUnavailableError, match="terminal failure"):
        _run(_authorization(), partial_effect)

    assert evidence_path.read_text(encoding="utf-8") == "effect-crossed\n"


def test_terminal_result_persistence_failure_blocks_reexecution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0

    def effect(_trusted_at: datetime) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"outcome": "effect-completed"}

    def fail_success_commit(*_args: object, **_kwargs: object) -> None:
        raise sqlite3.OperationalError("synthetic terminal-write failure")

    monkeypatch.setattr(EffectConsumptionStore, "commit_success", fail_success_commit)
    with pytest.raises(sqlite3.OperationalError, match="terminal-write"):
        _run(_authorization(), effect)
    with pytest.raises(EffectOutcomeUnavailableError, match="terminal failure"):
        _run(_authorization(), effect)

    assert calls == 1


def test_stale_authorization_fails_before_reservation_or_effect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authorization = _authorization()
    calls = 0

    def effect(_trusted_at: datetime) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"outcome": "should-not-run"}

    monkeypatch.setattr(
        effect_consumption,
        "trusted_utc_now",
        lambda: authorization.decision.expires_at,
    )
    with pytest.raises(EffectConsumptionError, match="validity window"):
        _run(authorization, effect)

    assert calls == 0


def test_unavailable_consumption_database_fails_closed_before_effect(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = tmp_path / "directory-not-database"
    database_path.mkdir()
    monkeypatch.setattr(
        effect_consumption,
        "_CONSUMPTION_DATABASE_PATH",
        database_path,
    )
    calls = 0

    def effect(_trusted_at: datetime) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"outcome": "should-not-run"}

    with pytest.raises(EffectConsumptionError):
        _run(_authorization(), effect)

    assert calls == 0


def test_cross_process_daily_file_effect_is_written_at_most_once(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "process.sqlite3"
    evidence_path = tmp_path / "evidence.txt"
    context = multiprocessing.get_context("fork")
    start = context.Event()
    results = context.Queue()
    authorization = _authorization()
    processes = [
        context.Process(
            target=_process_file_effect,
            args=(
                str(database_path),
                str(evidence_path),
                authorization,
                start,
                results,
            ),
        )
        for _ in range(2)
    ]
    for process in processes:
        process.start()
    start.set()
    for process in processes:
        process.join(15)
        assert process.exitcode == 0

    observed: list[tuple[str, str]] = []
    for _ in processes:
        try:
            observed.append(results.get(timeout=10))
        except Empty as exc:
            raise AssertionError("worker did not report a result") from exc

    assert evidence_path.read_text(encoding="utf-8") == "retained-evidence\n"
    assert all(
        (status, value)
        in {
            ("ok", "retained-evidence"),
            ("error", "EffectOutcomeUnavailableError"),
            ("error", "OperationalError"),
        }
        for status, value in observed
    ), observed
    assert any(status == "ok" for status, _value in observed)
    effect_consumption._CONSUMPTION_DATABASE_PATH = database_path
    replay = _run(
        _authorization(),
        lambda _when: pytest.fail("committed cross-process effect was re-executed"),
        allowance_identity="ceqanet-daily:2026-08-22",
        content_identity="ceqanet-series:reviewed-sequence-1",
    )
    assert replay == {"artifact": "retained-evidence", "sequence": 1}


def test_store_rejects_same_allowance_with_changed_operation_digest(
    tmp_path: Path,
) -> None:
    store = EffectConsumptionStore(tmp_path / "conflict.sqlite3")
    operation = _operation()
    store.reserve(operation, reserved_at=_NOW)

    with pytest.raises(EffectReplayConflictError):
        store.reserve(
            replace(
                operation,
                content_identity="content:changed",
                operation_digest="effect-operation:" + "9" * 64,
            ),
            reserved_at=_NOW,
        )


def test_owned_store_and_runner_accept_no_caller_selected_backend() -> None:
    assert tuple(inspect.signature(effect_consumption._owned_store).parameters) == ()
    assert effect_consumption._CONSUMPTION_DATABASE_PATH.is_absolute()
    assert "store" not in inspect.signature(_execute_owned_effect).parameters
    assert "database_path" not in inspect.signature(_execute_owned_effect).parameters
    assert "ledger" not in inspect.signature(_execute_owned_effect).parameters


def test_owned_store_identity_is_independent_of_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    before = effect_consumption._owned_store()._database_path
    monkeypatch.chdir(tmp_path)
    after = effect_consumption._owned_store()._database_path

    assert before == after
    assert before.is_absolute()


def test_consumption_store_rejects_symbolic_link_database(tmp_path: Path) -> None:
    target = tmp_path / "real.sqlite3"
    target.touch(mode=0o600)
    link = tmp_path / "redirect.sqlite3"
    link.symlink_to(target)

    with pytest.raises(EffectConsumptionError, match="symbolic link"):
        EffectConsumptionStore(link).load("effect-reservation:" + "1" * 64)


def test_required_utc_date_is_rechecked_after_durable_start_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import constructionsight.local_operator_authorization as local_authorization

    database_path = tmp_path / "date-boundary.sqlite3"
    monkeypatch.setattr(effect_consumption, "_CONSUMPTION_DATABASE_PATH", database_path)
    before_midnight = datetime(2026, 8, 22, 23, 59, 59, 900000, tzinfo=UTC)
    monkeypatch.setattr(
        local_authorization,
        "_trusted_authorization_time",
        lambda: before_midnight,
    )
    authorization = _authorization()
    after_midnight = datetime(2026, 8, 23, 0, 0, 0, 100000, tzinfo=UTC)
    times = iter((before_midnight, before_midnight, after_midnight))
    monkeypatch.setattr(effect_consumption, "trusted_utc_now", lambda: next(times))
    calls = 0

    def effect(_trusted_at: datetime) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {"outcome": "should-not-run"}

    with pytest.raises(EffectConsumptionError, match="date changed"):
        _execute_owned_effect(
            authorization,
            allowance_identity="ceqanet-daily:2026-08-22",
            content_identity="ceqanet-series:reviewed-sequence-1",
            implementation_id="tests.test_effect_consumption.date_bound_effect",
            replay_policy=EffectReplayPolicy.EXACT,
            effect=effect,
            encode_result=lambda result: result,
            decode_result=lambda payload: dict(payload),
            required_utc_date=before_midnight.date(),
        )

    assert calls == 0


def test_existing_wal_store_never_reissues_journal_mode_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Concurrent reservations must not reconfigure an existing WAL database."""

    store = EffectConsumptionStore(tmp_path / "stable-wal.sqlite3")
    operation = _operation()
    store.reserve(operation, reserved_at=_NOW)
    observed: list[str] = []
    real_connect = sqlite3.connect

    def traced_connect(*args, **kwargs):
        connection = real_connect(*args, **kwargs)
        connection.set_trace_callback(observed.append)
        return connection

    monkeypatch.setattr(sqlite3, "connect", traced_connect)
    with pytest.raises(EffectOutcomeUnavailableError, match="reserved|indeterminate"):
        store.reserve(operation, reserved_at=_NOW)
    assert store.load(operation.reservation_key) is not None
    assert not any(
        statement.strip().lower().startswith("pragma journal_mode =")
        for statement in observed
    )


def test_parallel_first_use_initializes_wal_without_lock_error(tmp_path: Path) -> None:
    """Fresh concurrent stores must serialize reservation, including WAL bootstrap."""

    for index in range(5):
        store_path = tmp_path / f"parallel-wal-{index}.sqlite3"
        barrier = threading.Barrier(2)
        operation = _operation()

        def reserve_once(barrier, store_path, operation):
            barrier.wait(timeout=10)
            try:
                return EffectConsumptionStore(store_path).reserve(
                    operation, reserved_at=_NOW
                )
            except EffectOutcomeUnavailableError as exc:
                return exc

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(reserve_once, barrier, store_path, operation)
                for _ in range(2)
            ]
            outcomes = [future.result(timeout=20) for future in futures]

        assert sum(not isinstance(outcome, Exception) for outcome in outcomes) == 1
        retained = EffectConsumptionStore(store_path).load(operation.reservation_key)
        assert retained is not None
        assert retained.status is EffectConsumptionStatus.RESERVED
        with sqlite3.connect(store_path) as connection:
            assert connection.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
