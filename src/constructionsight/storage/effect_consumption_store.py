"""SQLite-backed atomic reservation store for protected effects."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from constructionsight.effect_consumption_models import (
    EffectConsumptionRecord,
    EffectConsumptionStatus,
    EffectOperation,
    EffectReplayPolicy,
    EffectReservation,
)


class EffectConsumptionError(RuntimeError):
    """Base failure for durable consumption state."""


class EffectAlreadyConsumedError(EffectConsumptionError):
    """The exact single-use operation already reached or entered execution."""


class EffectReplayConflictError(EffectConsumptionError):
    """A reservation key was reused with different authority or content."""


class EffectOutcomeUnavailableError(EffectConsumptionError):
    """A duplicate has no safe committed result and may not execute again."""


_SCHEMA = """
CREATE TABLE IF NOT EXISTS effect_consumptions (
    reservation_key TEXT PRIMARY KEY,
    operation_digest TEXT NOT NULL,
    decision_id TEXT NOT NULL,
    authority_digest TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    action TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id TEXT NOT NULL,
    exact_scope_digest TEXT NOT NULL,
    current_state_identity TEXT NOT NULL,
    allowance_identity TEXT NOT NULL,
    content_identity TEXT NOT NULL,
    implementation_id TEXT NOT NULL,
    replay_policy TEXT NOT NULL CHECK (replay_policy IN ('deny', 'exact')),
    status TEXT NOT NULL CHECK (
        status IN ('reserved', 'in_progress', 'succeeded', 'failed')
    ),
    reserved_at TEXT NOT NULL,
    effect_started_at TEXT,
    completed_at TEXT,
    result_json TEXT,
    result_digest TEXT,
    failure_phase TEXT,
    failure_type TEXT,
    failure_digest TEXT
)
"""


class EffectConsumptionStore:
    """Own cross-process reservation, transition, and replay state."""

    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(
            self._database_path,
            timeout=30.0,
            isolation_level=None,
        )
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA busy_timeout = 30000")
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute("PRAGMA synchronous = FULL")
            connection.execute(_SCHEMA)
            yield connection
        finally:
            connection.close()

    def reserve(self, operation: EffectOperation, *, reserved_at: datetime) -> EffectReservation:
        """Atomically insert one operation or classify its exact durable duplicate."""

        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(
                    """
                    INSERT INTO effect_consumptions (
                        reservation_key, operation_digest, decision_id,
                        authority_digest, actor_id, action, resource_type,
                        resource_id, exact_scope_digest, current_state_identity,
                        allowance_identity, content_identity, implementation_id,
                        replay_policy, status, reserved_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        operation.reservation_key,
                        operation.operation_digest,
                        operation.decision_id,
                        operation.authority_digest,
                        operation.actor_id,
                        operation.action,
                        operation.resource_type,
                        operation.resource_id,
                        operation.exact_scope_digest,
                        operation.current_state_identity,
                        operation.allowance_identity,
                        operation.content_identity,
                        operation.implementation_id,
                        operation.replay_policy.value,
                        EffectConsumptionStatus.RESERVED.value,
                        reserved_at.isoformat(),
                    ),
                )
            except sqlite3.IntegrityError:
                row = connection.execute(
                    "SELECT * FROM effect_consumptions WHERE reservation_key = ?",
                    (operation.reservation_key,),
                ).fetchone()
                if row is None:
                    connection.rollback()
                    raise EffectConsumptionError(
                        "atomic reservation conflict could not be read back"
                    ) from None
                record = _record_from_row(row)
                if record.operation.operation_digest != operation.operation_digest:
                    connection.rollback()
                    raise EffectReplayConflictError(
                        "consumption reservation key was reused with changed scope, "
                        "state, content, authority, or implementation"
                    ) from None
                if (
                    record.status is EffectConsumptionStatus.SUCCEEDED
                    and operation.replay_policy is EffectReplayPolicy.EXACT
                    and record.result_json is not None
                    and record.result_digest is not None
                ):
                    connection.commit()
                    return EffectReservation(record=record, exact_replay=True)
                connection.rollback()
                if record.status is EffectConsumptionStatus.FAILED:
                    raise EffectOutcomeUnavailableError(
                        "protected effect has a terminal failure and requires explicit "
                        "adjudication before any separately authorized recovery"
                    ) from None
                if record.status in {
                    EffectConsumptionStatus.RESERVED,
                    EffectConsumptionStatus.IN_PROGRESS,
                }:
                    raise EffectOutcomeUnavailableError(
                        "protected effect is reserved or indeterminate; automatic "
                        "re-execution is prohibited"
                    ) from None
                raise EffectAlreadyConsumedError(
                    "single-use protected effect was already consumed"
                ) from None
            row = connection.execute(
                "SELECT * FROM effect_consumptions WHERE reservation_key = ?",
                (operation.reservation_key,),
            ).fetchone()
            connection.commit()
        if row is None:
            raise EffectConsumptionError("new atomic reservation was not retained")
        return EffectReservation(record=_record_from_row(row), exact_replay=False)

    def mark_effect_started(self, operation: EffectOperation, *, started_at: datetime) -> None:
        """Atomically cross the last boundary before invoking the owned effect."""

        self._transition(
            operation,
            expected=EffectConsumptionStatus.RESERVED,
            target=EffectConsumptionStatus.IN_PROGRESS,
            assignments=("effect_started_at = ?",),
            values=(started_at.isoformat(),),
        )

    def commit_success(
        self,
        operation: EffectOperation,
        *,
        completed_at: datetime,
        result_json: str,
        result_digest: str,
    ) -> None:
        """Persist the exact terminal result without permitting a second effect."""

        self._transition(
            operation,
            expected=EffectConsumptionStatus.IN_PROGRESS,
            target=EffectConsumptionStatus.SUCCEEDED,
            assignments=(
                "completed_at = ?",
                "result_json = ?",
                "result_digest = ?",
                "failure_phase = NULL",
                "failure_type = NULL",
                "failure_digest = NULL",
            ),
            values=(completed_at.isoformat(), result_json, result_digest),
        )

    def commit_failure(
        self,
        operation: EffectOperation,
        *,
        completed_at: datetime,
        effect_started: bool,
        failure_type: str,
        failure_digest: str,
    ) -> None:
        """Persist a terminal pre-effect or post-start failure without reopening use."""

        expected = (
            EffectConsumptionStatus.IN_PROGRESS
            if effect_started
            else EffectConsumptionStatus.RESERVED
        )
        self._transition(
            operation,
            expected=expected,
            target=EffectConsumptionStatus.FAILED,
            assignments=(
                "completed_at = ?",
                "failure_phase = ?",
                "failure_type = ?",
                "failure_digest = ?",
                "result_json = NULL",
                "result_digest = NULL",
            ),
            values=(
                completed_at.isoformat(),
                "after_effect_start" if effect_started else "before_effect",
                failure_type,
                failure_digest,
            ),
        )

    def load(self, reservation_key: str) -> EffectConsumptionRecord | None:
        """Load durable state for audit, recovery adjudication, or exact replay."""

        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM effect_consumptions WHERE reservation_key = ?",
                (reservation_key,),
            ).fetchone()
        return _record_from_row(row) if row is not None else None

    def _transition(
        self,
        operation: EffectOperation,
        *,
        expected: EffectConsumptionStatus,
        target: EffectConsumptionStatus,
        assignments: tuple[str, ...],
        values: tuple[str, ...],
    ) -> None:
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            cursor = connection.execute(
                "UPDATE effect_consumptions SET status = ?, "
                + ", ".join(assignments)
                + " WHERE reservation_key = ? AND operation_digest = ? AND status = ?",
                (
                    target.value,
                    *values,
                    operation.reservation_key,
                    operation.operation_digest,
                    expected.value,
                ),
            )
            if cursor.rowcount != 1:
                connection.rollback()
                raise EffectConsumptionError(
                    "consumption terminal transition lost its exact-state compare-and-swap"
                )
            connection.commit()


def _record_from_row(row: sqlite3.Row) -> EffectConsumptionRecord:
    operation = EffectOperation(
        reservation_key=str(row["reservation_key"]),
        operation_digest=str(row["operation_digest"]),
        decision_id=str(row["decision_id"]),
        authority_digest=str(row["authority_digest"]),
        actor_id=str(row["actor_id"]),
        action=str(row["action"]),
        resource_type=str(row["resource_type"]),
        resource_id=str(row["resource_id"]),
        exact_scope_digest=str(row["exact_scope_digest"]),
        current_state_identity=str(row["current_state_identity"]),
        allowance_identity=str(row["allowance_identity"]),
        content_identity=str(row["content_identity"]),
        implementation_id=str(row["implementation_id"]),
        replay_policy=EffectReplayPolicy(str(row["replay_policy"])),
    )
    return EffectConsumptionRecord(
        operation=operation,
        status=EffectConsumptionStatus(str(row["status"])),
        reserved_at=datetime.fromisoformat(str(row["reserved_at"])),
        effect_started_at=(
            datetime.fromisoformat(str(row["effect_started_at"]))
            if row["effect_started_at"] is not None
            else None
        ),
        completed_at=(
            datetime.fromisoformat(str(row["completed_at"]))
            if row["completed_at"] is not None
            else None
        ),
        result_json=str(row["result_json"]) if row["result_json"] is not None else None,
        result_digest=(
            str(row["result_digest"]) if row["result_digest"] is not None else None
        ),
        failure_phase=(
            str(row["failure_phase"]) if row["failure_phase"] is not None else None
        ),
        failure_type=(
            str(row["failure_type"]) if row["failure_type"] is not None else None
        ),
        failure_digest=(
            str(row["failure_digest"]) if row["failure_digest"] is not None else None
        ),
    )
