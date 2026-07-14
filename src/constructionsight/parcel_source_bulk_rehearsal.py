"""Governed complete ArcGIS object-ID rehearsal with durable checkpoint proof."""

from __future__ import annotations

import json
import math
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from constructionsight.parcel_source_acquisition import build_arcgis_bulk_manifest
from constructionsight.parcel_source_acquisition_models import (
    ParcelArcGISBulkManifest,
    ParcelArcGISCapabilitySnapshot,
)
from constructionsight.parcel_source_bulk_rehearsal_models import (
    ParcelArcGISBulkCheckpointEvidence,
    ParcelArcGISBulkPageEvidence,
    ParcelArcGISBulkRetryEvidence,
    build_arcgis_bulk_checkpoint_evidence,
    build_arcgis_bulk_page_evidence,
    build_arcgis_bulk_rehearsal_evidence,
    build_arcgis_bulk_resume_evidence,
    build_arcgis_bulk_retry_evidence,
    digest_json_payload,
)


class ParcelArcGISBulkRehearsalError(RuntimeError):
    """Raised when a complete rehearsal cannot establish its required proof."""


class ParcelArcGISBulkTransientError(RuntimeError):
    """A retry-eligible page-read failure with an explicit evidence classification."""

    def __init__(self, failure_kind: str, *, fault_injected: bool = False) -> None:
        if not failure_kind or failure_kind != failure_kind.strip():
            raise ValueError("ArcGIS transient failure kind must be nonempty and trimmed")
        super().__init__(failure_kind)
        self.failure_kind = failure_kind
        self.fault_injected = fault_injected


class ParcelArcGISBulkRehearsalSource(Protocol):
    """Read-only source contract for count and ordered object-ID page observations."""

    def fetch_count(self) -> int:
        """Return the source count observed at one point in the rehearsal."""

    def fetch_object_id_page(
        self,
        *,
        offset: int,
        record_count: int,
        attempt_number: int,
    ) -> Mapping[str, Any]:
        """Return one raw ArcGIS-compatible object-ID page response."""


class ParcelArcGISBulkCheckpointStore(Protocol):
    """Durable checkpoint boundary required by the rehearsal executor."""

    def save(self, checkpoint: ParcelArcGISBulkCheckpointEvidence) -> None:
        """Persist one exact checkpoint or accept its identical replay."""

    def load(self, checkpoint_id: str) -> ParcelArcGISBulkCheckpointEvidence:
        """Reload one checkpoint by its content identity."""


@dataclass(frozen=True)
class ParcelArcGISBulkRehearsalPolicy:
    """Explicit page, checkpoint, retry, and synthetic-fault limits."""

    page_size: int
    checkpoint_after_pages: int
    injected_retry_page_index: int
    max_attempts: int = 3
    retry_delays_seconds: tuple[float, ...] = (0.0, 0.0)

    def __post_init__(self) -> None:
        if self.page_size < 1:
            raise ValueError("ArcGIS rehearsal page size must be positive")
        if self.checkpoint_after_pages < 1:
            raise ValueError("ArcGIS rehearsal checkpoint must follow at least one page")
        if self.injected_retry_page_index < self.checkpoint_after_pages:
            raise ValueError("ArcGIS injected retry must occur in the resumed execution segment")
        if self.max_attempts < 2 or self.max_attempts > 5:
            raise ValueError("ArcGIS rehearsal max attempts must be between 2 and 5")
        if len(self.retry_delays_seconds) < self.max_attempts - 1:
            raise ValueError("ArcGIS rehearsal requires one delay per possible retry")
        if any(delay < 0 for delay in self.retry_delays_seconds):
            raise ValueError("ArcGIS rehearsal retry delays cannot be negative")


@dataclass(frozen=True)
class ParcelArcGISBulkRehearsalExecution:
    """Completed rehearsal output; never an authorization to perform a bulk run."""

    manifest: ParcelArcGISBulkManifest
    checkpoint_reloaded: bool
    bulk_run_authorized: bool = False

    def __post_init__(self) -> None:
        if not self.checkpoint_reloaded:
            raise ValueError("ArcGIS rehearsal execution requires checkpoint reload proof")
        if self.bulk_run_authorized:
            raise ValueError("ArcGIS rehearsal execution cannot authorize a bulk run")


class JSONFileParcelArcGISCheckpointStore:
    """Atomic local JSON checkpoint storage with exact-replay semantics."""

    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def path_for(self, checkpoint_id: str) -> Path:
        prefix = "parcel-arcgis-bulk-checkpoint:"
        if not checkpoint_id.startswith(prefix):
            raise ValueError("ArcGIS checkpoint identity is malformed")
        digest = checkpoint_id.removeprefix(prefix)
        if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            raise ValueError("ArcGIS checkpoint identity digest is malformed")
        return self._directory / f"{digest}.json"

    def save(self, checkpoint: ParcelArcGISBulkCheckpointEvidence) -> None:
        self._directory.mkdir(parents=True, exist_ok=True)
        path = self.path_for(checkpoint.checkpoint_id)
        canonical = (
            json.dumps(
                checkpoint.to_dict(),
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        )
        if path.exists():
            existing = ParcelArcGISBulkCheckpointEvidence.model_validate_json(
                path.read_text(encoding="utf-8")
            )
            if existing != checkpoint:
                raise ParcelArcGISBulkRehearsalError(
                    "ArcGIS checkpoint identity conflicts with retained content"
                )
            return
        temporary = path.with_suffix(".tmp")
        temporary.write_text(canonical, encoding="utf-8")
        temporary.replace(path)

    def load(self, checkpoint_id: str) -> ParcelArcGISBulkCheckpointEvidence:
        path = self.path_for(checkpoint_id)
        if not path.is_file():
            raise ParcelArcGISBulkRehearsalError("ArcGIS checkpoint was not retained")
        checkpoint = ParcelArcGISBulkCheckpointEvidence.model_validate_json(
            path.read_text(encoding="utf-8")
        )
        if checkpoint.checkpoint_id != checkpoint_id:
            raise ParcelArcGISBulkRehearsalError(
                "ArcGIS checkpoint reload returned a different identity"
            )
        return checkpoint


def execute_arcgis_complete_rehearsal(
    snapshot: ParcelArcGISCapabilitySnapshot,
    source: ParcelArcGISBulkRehearsalSource,
    checkpoint_store: ParcelArcGISBulkCheckpointStore,
    *,
    policy: ParcelArcGISBulkRehearsalPolicy,
    now: Callable[[], datetime] | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> ParcelArcGISBulkRehearsalExecution:
    """Execute a count-reconciled rehearsal with real save/reload and retry proof.

    The executor reads only counts and ordered object IDs. It has no persistence,
    profile-promotion, scheduling, parcel-import, or bulk-run authorization path.
    """

    if policy.page_size > snapshot.max_record_count:
        raise ValueError("ArcGIS rehearsal page size exceeds the capability snapshot")
    clock = now or _utc_now
    started_at = clock()
    starting_count = _require_positive_count(source.fetch_count(), "starting")
    expected_page_count = math.ceil(starting_count / policy.page_size)
    if expected_page_count < 2:
        raise ParcelArcGISBulkRehearsalError(
            "ArcGIS complete rehearsal requires at least two data pages"
        )
    if policy.checkpoint_after_pages >= expected_page_count:
        raise ValueError("ArcGIS checkpoint must precede at least one data page")
    if policy.injected_retry_page_index >= expected_page_count:
        raise ValueError("ArcGIS injected retry page is outside the expected page range")

    query_field = snapshot.object_id_field
    page_evidence: list[ParcelArcGISBulkPageEvidence] = []
    retry_evidence: list[ParcelArcGISBulkRetryEvidence] = []
    observed_ids: list[int] = []

    for page_index in range(policy.checkpoint_after_pages):
        page, retry = _fetch_page_with_retry(
            source,
            query_field=query_field,
            page_index=page_index,
            page_size=policy.page_size,
            expected_count=starting_count,
            observed_ids=observed_ids,
            policy=policy,
            clock=clock,
            sleep=sleep,
        )
        page_evidence.append(page)
        if retry is not None:
            retry_evidence.append(retry)

    checkpoint = build_arcgis_bulk_checkpoint_evidence(
        page_evidence,
        completed_page_count=policy.checkpoint_after_pages,
        page_size=policy.page_size,
        created_at=clock(),
    )
    checkpoint_store.save(checkpoint)
    reloaded_checkpoint = checkpoint_store.load(checkpoint.checkpoint_id)
    if reloaded_checkpoint != checkpoint:
        raise ParcelArcGISBulkRehearsalError(
            "ArcGIS checkpoint did not survive exact durable reload"
        )
    resumed_at = clock()

    for page_index in range(policy.checkpoint_after_pages, expected_page_count):
        page, retry = _fetch_page_with_retry(
            source,
            query_field=query_field,
            page_index=page_index,
            page_size=policy.page_size,
            expected_count=starting_count,
            observed_ids=observed_ids,
            policy=policy,
            clock=clock,
            sleep=sleep,
        )
        page_evidence.append(page)
        if retry is not None:
            retry_evidence.append(retry)

    if len(observed_ids) != starting_count:
        raise ParcelArcGISBulkRehearsalError(
            "ArcGIS rehearsal retrieved count does not match the starting count"
        )
    ending_count = _require_positive_count(source.fetch_count(), "ending")
    if ending_count != starting_count:
        raise ParcelArcGISBulkRehearsalError(
            "ArcGIS rehearsal source count changed during execution"
        )

    resume = build_arcgis_bulk_resume_evidence(
        checkpoint,
        page_evidence[policy.checkpoint_after_pages],
        resumed_at=resumed_at,
    )
    rehearsal_evidence = build_arcgis_bulk_rehearsal_evidence(
        snapshot,
        page_size=policy.page_size,
        page_evidence=page_evidence,
        checkpoint=checkpoint,
        resume=resume,
        retry_events=retry_evidence,
        created_at=clock(),
    )
    completed_at = clock()
    manifest = build_arcgis_bulk_manifest(
        snapshot,
        started_at=started_at,
        completed_at=completed_at,
        starting_count=starting_count,
        ending_count=ending_count,
        rehearsal_evidence=rehearsal_evidence,
    )
    return ParcelArcGISBulkRehearsalExecution(
        manifest=manifest,
        checkpoint_reloaded=True,
    )


def parse_arcgis_object_id_page(
    payload: Mapping[str, Any],
    *,
    object_id_field: str,
) -> tuple[int, ...]:
    """Normalize object IDs from either ArcGIS `objectIds` or `features` output."""

    if payload.get("error") is not None:
        raise ParcelArcGISBulkRehearsalError("ArcGIS page response contains an error")
    direct_ids = payload.get("objectIds")
    if direct_ids is not None:
        if not isinstance(direct_ids, Sequence) or isinstance(direct_ids, (str, bytes, bytearray)):
            raise ParcelArcGISBulkRehearsalError("ArcGIS objectIds response must be an array")
        return _normalize_object_ids(direct_ids)

    features = payload.get("features")
    if not isinstance(features, Sequence) or isinstance(features, (str, bytes, bytearray)):
        raise ParcelArcGISBulkRehearsalError(
            "ArcGIS page response must contain objectIds or features"
        )
    values: list[Any] = []
    for feature in features:
        if not isinstance(feature, Mapping):
            raise ParcelArcGISBulkRehearsalError("ArcGIS feature must be an object")
        attributes = feature.get("attributes")
        if not isinstance(attributes, Mapping) or object_id_field not in attributes:
            raise ParcelArcGISBulkRehearsalError("ArcGIS feature is missing the object-ID field")
        values.append(attributes[object_id_field])
    return _normalize_object_ids(values)


def _fetch_page_with_retry(
    source: ParcelArcGISBulkRehearsalSource,
    *,
    query_field: str,
    page_index: int,
    page_size: int,
    expected_count: int,
    observed_ids: list[int],
    policy: ParcelArcGISBulkRehearsalPolicy,
    clock: Callable[[], datetime],
    sleep: Callable[[float], None],
) -> tuple[ParcelArcGISBulkPageEvidence, ParcelArcGISBulkRetryEvidence | None]:
    failure_kind: str | None = None
    fault_injected = False
    retry_recorded_at: datetime | None = None
    payload: Mapping[str, Any] | None = None
    attempt_count = 0

    for attempt_number in range(1, policy.max_attempts + 1):
        attempt_count = attempt_number
        try:
            if page_index == policy.injected_retry_page_index and attempt_number == 1:
                raise ParcelArcGISBulkTransientError(
                    "injected_pre_request_transient",
                    fault_injected=True,
                )
            payload = source.fetch_object_id_page(
                offset=page_index * page_size,
                record_count=page_size,
                attempt_number=attempt_number,
            )
            break
        except ParcelArcGISBulkTransientError as exc:
            if failure_kind is None:
                failure_kind = exc.failure_kind
                retry_recorded_at = clock()
            elif failure_kind != exc.failure_kind:
                raise ParcelArcGISBulkRehearsalError(
                    "ArcGIS page retry failure classification changed"
                ) from exc
            fault_injected = fault_injected or exc.fault_injected
            if attempt_number >= policy.max_attempts:
                raise ParcelArcGISBulkRehearsalError(
                    f"ArcGIS page {page_index} exhausted bounded retries"
                ) from exc
            sleep(policy.retry_delays_seconds[attempt_number - 1])

    if payload is None:
        raise ParcelArcGISBulkRehearsalError("ArcGIS page returned no payload")
    object_ids = parse_arcgis_object_id_page(
        payload,
        object_id_field=query_field,
    )
    if not object_ids:
        raise ParcelArcGISBulkRehearsalError(
            "ArcGIS rehearsal encountered an empty expected data page"
        )
    if len(object_ids) > page_size:
        raise ParcelArcGISBulkRehearsalError(
            "ArcGIS rehearsal page exceeded the requested page size"
        )
    if object_ids != tuple(sorted(set(object_ids))):
        raise ParcelArcGISBulkRehearsalError(
            "ArcGIS rehearsal page object IDs are not unique and ascending"
        )
    if observed_ids and object_ids[0] <= observed_ids[-1]:
        raise ParcelArcGISBulkRehearsalError(
            "ArcGIS rehearsal object IDs are not globally ascending and unique"
        )
    projected_count = len(observed_ids) + len(object_ids)
    if projected_count > expected_count:
        raise ParcelArcGISBulkRehearsalError(
            "ArcGIS rehearsal retrieved more object IDs than the count observation"
        )
    terminal_page = projected_count == expected_count
    if len(object_ids) < page_size and not terminal_page:
        raise ParcelArcGISBulkRehearsalError(
            "ArcGIS rehearsal reached a short page before count reconciliation"
        )
    observed_at = clock()
    page = build_arcgis_bulk_page_evidence(
        page_index=page_index,
        page_size=page_size,
        object_ids=object_ids,
        response_digest=digest_json_payload(dict(payload)),
        attempt_count=attempt_count,
        terminal_page=terminal_page,
        observed_at=observed_at,
    )
    observed_ids.extend(object_ids)

    retry: ParcelArcGISBulkRetryEvidence | None = None
    if attempt_count > 1:
        if failure_kind is None or retry_recorded_at is None:
            raise ParcelArcGISBulkRehearsalError("ArcGIS retried page is missing failure evidence")
        retry = build_arcgis_bulk_retry_evidence(
            page,
            failure_kind=failure_kind,
            failed_attempt_count=attempt_count - 1,
            fault_injected=fault_injected,
            recorded_at=retry_recorded_at,
        )
    return page, retry


def _normalize_object_ids(values: Sequence[Any]) -> tuple[int, ...]:
    normalized: list[int] = []
    for value in values:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ParcelArcGISBulkRehearsalError("ArcGIS object IDs must be JSON integers")
        if value < 0:
            raise ParcelArcGISBulkRehearsalError("ArcGIS object IDs cannot be negative")
        normalized.append(value)
    return tuple(normalized)


def _require_positive_count(value: int, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ParcelArcGISBulkRehearsalError(f"ArcGIS {label} count must be a positive integer")
    return value


def _utc_now() -> datetime:
    return datetime.now(UTC)
