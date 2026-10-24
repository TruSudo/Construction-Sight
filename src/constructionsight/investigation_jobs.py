"""Durable local investigation jobs over the existing immutable runtime-event store.

Jobs hold orchestration state, not a second copy of investigative knowledge.
Claims use SQLite's writer reservation; successful knowledge writes and completion
are committed in the same application transaction by the worker.
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import Engine, Select, func, select
from sqlalchemy.orm import Session

from constructionsight.intelligence.investigation_service import _identity
from constructionsight.intelligence.schemas import RuntimeEvent, RuntimeEventType
from constructionsight.storage.database import managed_session, session_factory
from constructionsight.storage.intelligence_orm import IntelligenceRuntimeEventRecord
from constructionsight.storage.intelligence_store import IntelligenceStore

JobKind = Literal["smarts_replay", "retained_json_replay", "correlate_source", "parcel_assess"]
JobStatus = Literal["queued", "running", "retry_wait", "completed", "failed", "blocked"]
CHANNEL = "investigation_job:"
EVENTS: dict[str, RuntimeEventType] = {
    "queued": RuntimeEventType.BACKGROUND_JOB_QUEUED,
    "running": RuntimeEventType.BACKGROUND_JOB_STARTED,
    "retry_wait": RuntimeEventType.BACKGROUND_JOB_RETRY,
    "completed": RuntimeEventType.BACKGROUND_JOB_COMPLETED,
    "failed": RuntimeEventType.BACKGROUND_JOB_FAILED,
    "blocked": RuntimeEventType.BACKGROUND_JOB_BLOCKED,
}


def _now() -> float:
    return time.time()


class JobDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: JobKind
    inputs: dict[str, Any]
    depends_on: list[str] = Field(default_factory=list, max_length=32)
    max_attempts: int = Field(default=3, ge=1, le=5, strict=True)
    lease_seconds: int = Field(default=120, ge=10, le=600, strict=True)

    @field_validator("depends_on")
    @classmethod
    def canonical_dependencies(cls, value: list[str]) -> list[str]:
        return sorted(value)

    @model_validator(mode="after")
    def validate_definition(self) -> JobDefinition:
        if len(set(self.depends_on)) != len(self.depends_on) or any(
            not item.strip() for item in self.depends_on
        ):
            raise ValueError("job dependencies must be unique nonblank identities")
        if len(json.dumps(self.inputs, sort_keys=True, allow_nan=False).encode()) > 16384:
            raise ValueError("job inputs exceed the orchestration metadata bound")
        return self

    @property
    def job_id(self) -> str:
        payload = self.model_dump(mode="json", round_trip=True)
        payload["depends_on"] = sorted(self.depends_on)
        return _identity("job:investigation", payload)


class JobState(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    job_id: str
    definition: JobDefinition
    status: JobStatus
    attempt: int = Field(default=0, ge=0, le=5, strict=True)
    created_at: float = Field(ge=0, allow_inf_nan=False)
    updated_at: float = Field(ge=0, allow_inf_nan=False)
    available_at: float = Field(ge=0, allow_inf_nan=False)
    worker_id: str | None = Field(default=None, max_length=200)
    lease_token: str | None = None
    lease_expires: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    result: dict[str, Any] = Field(default_factory=dict)
    error_code: str | None = Field(default=None, max_length=200)

    @model_validator(mode="after")
    def validate_state(self) -> JobState:
        if len(json.dumps(self.result, sort_keys=True, allow_nan=False).encode()) > 131072:
            raise ValueError("job result exceeds the bounded summary size")
        if self.job_id != self.definition.job_id:
            raise ValueError("job identity does not match its immutable definition")
        if self.attempt > self.definition.max_attempts:
            raise ValueError("job attempts exceed the permitted bound")
        if self.status == "running" and not (
            self.worker_id and self.lease_token and self.lease_expires is not None
        ):
            raise ValueError("running job requires an owned expiring lease")
        if self.status != "running" and self.lease_token is not None:
            raise ValueError("terminal or waiting jobs cannot hold a worker lease")
        return self


class StaleJobLease(ValueError):
    pass


class InvestigationJobQueue:
    """Restart-safe dependency-aware jobs, serialized through one local database."""

    def __init__(self, engine: Engine) -> None:
        if engine.dialect.name != "sqlite":
            raise ValueError("local investigation queue currently supports SQLite only")
        self.factory = session_factory(engine)

    @staticmethod
    def begin_write(session: Session) -> None:
        # Queue entry points use fresh sessions. Reserve the writer before reading
        # eligibility so two processes cannot claim the same attempt.
        session.connection().exec_driver_sql("BEGIN IMMEDIATE")

    @staticmethod
    def _save(store: IntelligenceStore, state: JobState) -> None:
        state = JobState.model_validate(state.model_dump(mode="json", round_trip=True))
        payload = state.model_dump(mode="json", round_trip=True)
        store.add_runtime_event(
            RuntimeEvent(
                event_id=_identity("event:investigation-job", payload),
                event_type=EVENTS[state.status],
                source_service=CHANNEL + state.job_id,
                correlation_id=state.job_id,
                created_at=datetime.fromtimestamp(state.updated_at, UTC),
                payload=payload,
                message=f"Investigation job {state.definition.kind}: {state.status}.",
                requires_user_attention=state.status in {"failed", "blocked"},
            )
        )

    @staticmethod
    def _decode(event: RuntimeEvent) -> JobState:
        state = JobState.model_validate(event.payload)
        if (
            event.event_type != EVENTS[state.status]
            or event.source_service != CHANNEL + state.job_id
            or event.event_id != _identity("event:investigation-job", event.payload)
        ):
            raise ValueError("retained job event failed identity or state validation")
        return state

    def current(self, store: IntelligenceStore, job_id: str) -> JobState | None:
        row = store.session.scalar(
            select(IntelligenceRuntimeEventRecord)
            .where(
                IntelligenceRuntimeEventRecord.source_service == CHANNEL + job_id,
            )
            .order_by(IntelligenceRuntimeEventRecord.id.desc())
            .limit(1)
        )
        return self._decode(RuntimeEvent.model_validate_json(row.payload_json)) if row else None

    def enqueue_in_transaction(
        self, store: IntelligenceStore, definition: JobDefinition
    ) -> JobState:
        definition = JobDefinition.model_validate(
            definition.model_dump(mode="json", round_trip=True)
        )
        existing = self.current(store, definition.job_id)
        if existing is not None:
            if existing.definition != definition:
                raise ValueError("job identity collision changed the definition")
            return existing
        for dependency in definition.depends_on:
            if dependency == definition.job_id or self.current(store, dependency) is None:
                raise ValueError("job requires already retained, distinct dependencies")
        now = _now()
        state = JobState(
            job_id=definition.job_id,
            definition=definition,
            status="queued",
            created_at=now,
            updated_at=now,
            available_at=now,
        )
        self._save(store, state)
        return state

    def enqueue(self, definition: JobDefinition) -> JobState:
        with managed_session(self.factory) as session:
            self.begin_write(session)
            return self.enqueue_in_transaction(IntelligenceStore(session), definition)

    def _latest_rows(
        self, session: Session, *, due_at: float | None, limit: int
    ) -> Select[tuple[IntelligenceRuntimeEventRecord]]:
        latest = (
            select(func.max(IntelligenceRuntimeEventRecord.id))
            .where(
                IntelligenceRuntimeEventRecord.source_service.startswith(CHANNEL),
            )
            .group_by(IntelligenceRuntimeEventRecord.source_service)
        )
        statement = select(IntelligenceRuntimeEventRecord).where(
            IntelligenceRuntimeEventRecord.id.in_(latest)
        )
        if due_at is not None:
            status = func.json_extract(
                IntelligenceRuntimeEventRecord.payload_json, "$.payload.status"
            )
            available = func.json_extract(
                IntelligenceRuntimeEventRecord.payload_json, "$.payload.available_at"
            )
            expires = func.json_extract(
                IntelligenceRuntimeEventRecord.payload_json, "$.payload.lease_expires"
            )
            statement = statement.where(
                ((status.in_(["queued", "retry_wait"])) & (available <= due_at))
                | ((status == "running") & (expires <= due_at))
            )
        created = func.json_extract(
            IntelligenceRuntimeEventRecord.payload_json, "$.payload.created_at"
        )
        return statement.order_by(created, IntelligenceRuntimeEventRecord.id).limit(limit)

    def list_jobs(self, *, limit: int = 100) -> list[JobState]:
        if type(limit) is not int or not 1 <= limit <= 500:
            raise ValueError("job list limit must be between 1 and 500")
        with managed_session(self.factory) as session:
            return [
                self._decode(RuntimeEvent.model_validate_json(row.payload_json))
                for row in session.scalars(self._latest_rows(session, due_at=None, limit=limit))
            ]

    def pending_original_replay(
        self, store: IntelligenceStore, source_entity_id: str,
    ) -> JobState | None:
        """Find pending reviewed work for one exact source under the caller's write lock."""

        rows = list(store.session.scalars(
            self._latest_rows(store.session, due_at=None, limit=2).where(
                func.json_extract(
                    IntelligenceRuntimeEventRecord.payload_json,
                    "$.payload.definition.inputs.original_replay_approval.source_entity_id",
                ) == source_entity_id,
                func.json_extract(
                    IntelligenceRuntimeEventRecord.payload_json, "$.payload.status",
                ).in_(["queued", "running", "retry_wait"]),
            )
        ))
        if len(rows) > 1:
            raise ValueError(
                "source has multiple pending reviewed replays; individual review required"
            )
        if not rows:
            return None
        return self._decode(RuntimeEvent.model_validate_json(rows[0].payload_json))

    def claim(self, worker_id: str) -> JobState | None:
        if not worker_id.strip() or len(worker_id) > 200:
            raise ValueError("worker identity must be nonblank and bounded")
        with managed_session(self.factory) as session:
            self.begin_write(session)
            store = IntelligenceStore(session)
            now = _now()
            rows = session.scalars(self._latest_rows(session, due_at=now, limit=500)).all()
            for row in rows:
                state = self._decode(RuntimeEvent.model_validate_json(row.payload_json))
                dependencies = [
                    self.current(store, identity) for identity in state.definition.depends_on
                ]
                if any(
                    item is None or item.status in {"failed", "blocked"} for item in dependencies
                ):
                    self._finish_state(
                        store, state, status="blocked", error_code="dependency_failed"
                    )
                    continue
                if any(item.status != "completed" for item in dependencies if item is not None):
                    continue
                if state.attempt >= state.definition.max_attempts:
                    self._finish_state(
                        store, state, status="failed", error_code="lease_attempts_exhausted"
                    )
                    continue
                claimed = JobState.model_validate(
                    state.model_copy(
                        update={
                            "status": "running",
                            "attempt": state.attempt + 1,
                            "updated_at": now,
                            "worker_id": worker_id,
                            "lease_token": uuid.uuid4().hex,
                            "lease_expires": now + state.definition.lease_seconds,
                            "error_code": None,
                        }
                    ).model_dump(mode="json")
                )
                self._save(store, claimed)
                return claimed
        return None

    def validate_claim(self, store: IntelligenceStore, claim: JobState) -> JobState:
        current = self.current(store, claim.job_id)
        if (
            current is None
            or current.status != "running"
            or current.lease_token != claim.lease_token
            or current.worker_id != claim.worker_id
            or current.definition != claim.definition
            or current.lease_expires is None
            or current.lease_expires <= _now()
        ):
            raise StaleJobLease("job lease changed or expired; no completion may be committed")
        return current

    def _finish_state(
        self,
        store: IntelligenceStore,
        state: JobState,
        *,
        status: JobStatus,
        error_code: str | None = None,
        result: dict[str, Any] | None = None,
        available_at: float | None = None,
    ) -> JobState:
        now = _now()
        finished = JobState.model_validate(
            state.model_copy(
                update={
                    "status": status,
                    "updated_at": now,
                    "error_code": error_code,
                    "result": result or {},
                    "lease_token": None,
                    "lease_expires": None,
                    "available_at": now if available_at is None else available_at,
                }
            ).model_dump(mode="json")
        )
        self._save(store, finished)
        return finished

    def complete_in_transaction(
        self,
        store: IntelligenceStore,
        claim: JobState,
        result: dict[str, Any],
    ) -> JobState:
        current = self.validate_claim(store, claim)
        return self._finish_state(store, current, status="completed", result=result)

    def fail(self, claim: JobState, *, error_code: str, retryable: bool) -> JobState:
        with managed_session(self.factory) as session:
            self.begin_write(session)
            store = IntelligenceStore(session)
            current = self.current(store, claim.job_id)
            if (
                current is None
                or current.status != "running"
                or current.lease_token != claim.lease_token
                or current.worker_id != claim.worker_id
                or current.definition != claim.definition
            ):
                raise StaleJobLease("a stale worker cannot fail or reschedule another attempt")
            retry = retryable and current.attempt < current.definition.max_attempts
            return self._finish_state(
                store,
                current,
                status="retry_wait" if retry else "failed",
                error_code=error_code,
                available_at=_now() + min(3600, 5 * 2**current.attempt) if retry else None,
            )
