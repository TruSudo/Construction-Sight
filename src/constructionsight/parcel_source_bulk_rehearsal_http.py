"""Exact-response HTTP transport and deterministic plans for ArcGIS rehearsals."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime

import httpx

from constructionsight.http_transport import execute_bounded_http
from constructionsight.http_transport_models import (
    BoundedHttpObservation,
    BoundedHttpPolicy,
    HttpFailureKind,
    canonicalize_http_url,
)
from constructionsight.parcel_source_acquisition_models import (
    ParcelArcGISCapabilitySnapshot,
)
from constructionsight.parcel_source_bulk_rehearsal import (
    ParcelArcGISBulkRehearsalPolicy,
    ParcelArcGISBulkTransientError,
)
from constructionsight.parcel_source_bulk_rehearsal_artifacts import (
    ParcelArcGISBulkCountResponse,
    ParcelArcGISBulkPageResponse,
    decode_json_object,
)

_ARCGIS_ALLOWED_HOSTS = ("arcgis.com", "*.arcgis.com", "*.gov")
_ARCGIS_ALLOWED_PATH_PREFIXES = ("/arcgis/rest/services/", "/server/rest/services/")


class ParcelArcGISBulkHTTPError(RuntimeError):
    """Raised when an HTTP response is terminal or violates the rehearsal contract."""


@dataclass(frozen=True)
class ParcelArcGISBulkHTTPPolicy:
    """One-request transport limits; retry sequencing remains owned by the executor."""

    timeout_seconds: float = 30.0
    max_response_bytes: int = 2_000_000
    retry_status_codes: frozenset[int] = frozenset({429, 500, 502, 503, 504})
    accepted_media_types: tuple[str, ...] = (
        "application/geo+json",
        "application/json",
        "text/plain",
    )

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("ArcGIS rehearsal HTTP timeout must be positive")
        if self.max_response_bytes < 1:
            raise ValueError("ArcGIS rehearsal HTTP response limit must be positive")
        if not self.retry_status_codes:
            raise ValueError("ArcGIS rehearsal HTTP retry statuses cannot be empty")
        if any(status < 400 or status > 599 for status in self.retry_status_codes):
            raise ValueError("ArcGIS rehearsal HTTP retry statuses must be HTTP errors")
        canonical_media_types = tuple(
            sorted({value.strip().casefold() for value in self.accepted_media_types})
        )
        if not canonical_media_types or canonical_media_types != self.accepted_media_types:
            raise ValueError(
                "ArcGIS rehearsal HTTP media types must be unique, sorted, and canonical"
            )

    def bounded_policy(self, request_url: str) -> BoundedHttpPolicy:
        """Bind one exact rehearsal request to the central one-attempt HTTP engine."""

        return BoundedHttpPolicy(
            policy_id="CS-NET-005",
            allowed_methods=("GET",),
            allowed_hosts=_ARCGIS_ALLOWED_HOSTS,
            allowed_path_prefixes=_ARCGIS_ALLOWED_PATH_PREFIXES,
            connect_timeout_seconds=self.timeout_seconds,
            read_timeout_seconds=self.timeout_seconds,
            write_timeout_seconds=self.timeout_seconds,
            pool_timeout_seconds=self.timeout_seconds,
            max_response_bytes=self.max_response_bytes,
            accepted_media_types=self.accepted_media_types,
            accepted_encodings=("utf-8",),
            user_agent="ConstructionSight-ArcGISBulkRehearsal/1.0",
            allowed_request_urls=(request_url,),
            request_accept="application/json",
        )


@dataclass(frozen=True)
class ParcelArcGISBulkRehearsalPlan:
    """Digest-bound, non-authorizing plan for one complete rehearsal attempt."""

    plan_id: str
    snapshot_id: str
    profile_id: str
    source_key: str
    county: str
    query_url: str
    object_id_field: str
    page_size: int
    checkpoint_after_pages: int
    injected_retry_page_index: int
    max_attempts: int
    retry_delays_seconds: tuple[float, ...]
    timeout_seconds: float
    max_response_bytes: int
    retry_status_codes: tuple[int, ...]
    accepted_media_types: tuple[str, ...]
    generated_at: datetime
    bulk_run_authorized: bool = False

    def __post_init__(self) -> None:
        if self.generated_at.tzinfo is None or self.generated_at.utcoffset() is None:
            raise ValueError("ArcGIS rehearsal plan generated_at must be timezone-aware")
        if not self.query_url.startswith("https://") or not self.query_url.endswith("/query"):
            raise ValueError("ArcGIS rehearsal plan requires an HTTPS query endpoint")
        if not self.object_id_field or self.object_id_field != self.object_id_field.strip():
            raise ValueError("ArcGIS rehearsal plan object-ID field must be trimmed")
        if self.bulk_run_authorized:
            raise ValueError("ArcGIS rehearsal plans cannot authorize a bulk run")
        _ = self.rehearsal_policy
        _ = self.http_policy
        expected_id = _plan_identity(self.to_dict(include_plan_id=False))
        if self.plan_id != expected_id:
            raise ValueError("ArcGIS rehearsal plan identity does not match its content")

    @property
    def rehearsal_policy(self) -> ParcelArcGISBulkRehearsalPolicy:
        """Return the exact executor policy bound into this plan."""

        return ParcelArcGISBulkRehearsalPolicy(
            page_size=self.page_size,
            checkpoint_after_pages=self.checkpoint_after_pages,
            injected_retry_page_index=self.injected_retry_page_index,
            max_attempts=self.max_attempts,
            retry_delays_seconds=self.retry_delays_seconds,
        )

    @property
    def http_policy(self) -> ParcelArcGISBulkHTTPPolicy:
        """Return the exact one-request HTTP policy bound into this plan."""

        return ParcelArcGISBulkHTTPPolicy(
            timeout_seconds=self.timeout_seconds,
            max_response_bytes=self.max_response_bytes,
            retry_status_codes=frozenset(self.retry_status_codes),
            accepted_media_types=self.accepted_media_types,
        )

    def to_dict(self, *, include_plan_id: bool = True) -> dict[str, object]:
        """Return a deterministic JSON-compatible plan payload."""

        payload: dict[str, object] = {
            "snapshot_id": self.snapshot_id,
            "profile_id": self.profile_id,
            "source_key": self.source_key,
            "county": self.county,
            "query_url": self.query_url,
            "object_id_field": self.object_id_field,
            "page_size": self.page_size,
            "checkpoint_after_pages": self.checkpoint_after_pages,
            "injected_retry_page_index": self.injected_retry_page_index,
            "max_attempts": self.max_attempts,
            "retry_delays_seconds": list(self.retry_delays_seconds),
            "timeout_seconds": self.timeout_seconds,
            "max_response_bytes": self.max_response_bytes,
            "retry_status_codes": list(self.retry_status_codes),
            "accepted_media_types": list(self.accepted_media_types),
            "generated_at": self.generated_at.isoformat(),
            "bulk_run_authorized": self.bulk_run_authorized,
        }
        if include_plan_id:
            payload = {"plan_id": self.plan_id, **payload}
        return payload


def build_arcgis_bulk_rehearsal_plan(
    snapshot: ParcelArcGISCapabilitySnapshot,
    *,
    generated_at: datetime,
    page_size: int | None = None,
    checkpoint_after_pages: int = 1,
    injected_retry_page_index: int = 1,
    max_attempts: int = 3,
    retry_delays_seconds: tuple[float, ...] = (0.0, 0.0),
    timeout_seconds: float = 30.0,
    max_response_bytes: int = 2_000_000,
    retry_status_codes: tuple[int, ...] = (429, 500, 502, 503, 504),
    accepted_media_types: tuple[str, ...] = (
        "application/geo+json",
        "application/json",
        "text/plain",
    ),
) -> ParcelArcGISBulkRehearsalPlan:
    """Build a deterministic plan without executing or authorizing a live rehearsal."""

    if not snapshot.advertised_ready_for_probe:
        raise ValueError("ArcGIS capability snapshot does not advertise rehearsal primitives")
    selected_page_size = page_size or snapshot.max_record_count
    if selected_page_size > snapshot.max_record_count:
        raise ValueError("ArcGIS rehearsal plan page size exceeds the capability snapshot")
    query_url = snapshot.layer_url.rstrip("/") + "/query"
    canonical_retry_statuses = tuple(sorted(set(retry_status_codes)))
    canonical_media_types = tuple(
        sorted({value.strip().casefold() for value in accepted_media_types})
    )
    payload: dict[str, object] = {
        "snapshot_id": snapshot.snapshot_id,
        "profile_id": snapshot.profile_id,
        "source_key": snapshot.source_key,
        "county": snapshot.county,
        "query_url": query_url,
        "object_id_field": snapshot.object_id_field,
        "page_size": selected_page_size,
        "checkpoint_after_pages": checkpoint_after_pages,
        "injected_retry_page_index": injected_retry_page_index,
        "max_attempts": max_attempts,
        "retry_delays_seconds": list(retry_delays_seconds),
        "timeout_seconds": timeout_seconds,
        "max_response_bytes": max_response_bytes,
        "retry_status_codes": list(canonical_retry_statuses),
        "accepted_media_types": list(canonical_media_types),
        "generated_at": generated_at.isoformat(),
        "bulk_run_authorized": False,
    }
    return ParcelArcGISBulkRehearsalPlan(
        plan_id=_plan_identity(payload),
        snapshot_id=snapshot.snapshot_id,
        profile_id=snapshot.profile_id,
        source_key=snapshot.source_key,
        county=snapshot.county,
        query_url=query_url,
        object_id_field=snapshot.object_id_field,
        page_size=selected_page_size,
        checkpoint_after_pages=checkpoint_after_pages,
        injected_retry_page_index=injected_retry_page_index,
        max_attempts=max_attempts,
        retry_delays_seconds=retry_delays_seconds,
        timeout_seconds=timeout_seconds,
        max_response_bytes=max_response_bytes,
        retry_status_codes=canonical_retry_statuses,
        accepted_media_types=canonical_media_types,
        generated_at=generated_at,
    )


class HTTPParcelArcGISBulkRehearsalSource:
    """Official ArcGIS query adapter that performs one exact request per source call."""

    def __init__(
        self,
        snapshot: ParcelArcGISCapabilitySnapshot,
        plan: ParcelArcGISBulkRehearsalPlan,
    ) -> None:
        _validate_plan_scope(snapshot, plan)
        self._snapshot = snapshot
        self._plan = plan
        self._http_policy = plan.http_policy

    def fetch_count(self) -> ParcelArcGISBulkCountResponse:
        """Fetch and preserve one exact count response."""

        response_body = self._request_exact(
            {
                "f": "json",
                "returnCountOnly": "true",
                "returnGeometry": "false",
                "where": "1=1",
            }
        )
        payload = _decode_service_payload(response_body, self._http_policy)
        count = payload.get("count")
        if isinstance(count, bool) or not isinstance(count, int) or count < 1:
            raise ParcelArcGISBulkHTTPError("ArcGIS count response must contain a positive integer")
        return ParcelArcGISBulkCountResponse(count=count, response_body=response_body)

    def fetch_object_id_page(
        self,
        *,
        offset: int,
        record_count: int,
        attempt_number: int,
    ) -> ParcelArcGISBulkPageResponse:
        """Fetch one ordered, geometry-disabled page with no internal retry loop."""

        if offset < 0:
            raise ValueError("ArcGIS rehearsal page offset cannot be negative")
        if record_count != self._plan.page_size:
            raise ValueError("ArcGIS rehearsal page size does not match the plan")
        if offset % record_count != 0:
            raise ValueError("ArcGIS rehearsal page offset must align with the page size")
        if attempt_number < 1 or attempt_number > self._plan.max_attempts:
            raise ValueError("ArcGIS rehearsal attempt number is outside the plan")
        response_body = self._request_exact(
            {
                "f": "json",
                "orderByFields": f"{self._snapshot.object_id_field} ASC",
                "outFields": self._snapshot.object_id_field,
                "resultOffset": str(offset),
                "resultRecordCount": str(record_count),
                "returnGeometry": "false",
                "where": "1=1",
            }
        )
        _decode_service_payload(response_body, self._http_policy)
        return ParcelArcGISBulkPageResponse(response_body=response_body)

    def _request_exact(self, parameters: dict[str, str]) -> bytes:
        request_url = canonicalize_http_url(
            str(httpx.URL(self._plan.query_url, params=parameters))
        )
        observation = execute_bounded_http(
            request_url,
            "GET",
            self._http_policy.bounded_policy(request_url),
        )
        return _require_exact_body(observation, self._http_policy)


def _require_exact_body(
    observation: BoundedHttpObservation,
    policy: ParcelArcGISBulkHTTPPolicy,
) -> bytes:
    if observation.status_code in policy.retry_status_codes:
        raise ParcelArcGISBulkTransientError(f"http_{observation.status_code}")
    if observation.failure_kind in {HttpFailureKind.TIMEOUT, HttpFailureKind.TRANSPORT}:
        raise ParcelArcGISBulkTransientError("transport")
    if observation.failure_kind is HttpFailureKind.REDIRECT:
        raise ParcelArcGISBulkHTTPError("ArcGIS rehearsal HTTP redirects are forbidden")
    if observation.failure_kind is HttpFailureKind.OVERSIZED_RESPONSE:
        raise ParcelArcGISBulkHTTPError("ArcGIS response exceeded the configured byte limit")
    if observation.failure_kind is HttpFailureKind.MALFORMED_RESPONSE:
        raise ParcelArcGISBulkHTTPError("ArcGIS response Content-Length is malformed")
    if observation.failure_kind is HttpFailureKind.MEDIA_TYPE:
        raise ParcelArcGISBulkHTTPError(
            f"ArcGIS response media type is not permitted: {observation.content_type}"
        )
    if observation.failure_kind is HttpFailureKind.ENCODING:
        raise ParcelArcGISBulkHTTPError("ArcGIS response was not strict UTF-8 JSON")
    if observation.status_code != 200:
        raise ParcelArcGISBulkHTTPError(
            f"ArcGIS rehearsal request returned HTTP {observation.status_code}"
        )
    if observation.failure_kind is not HttpFailureKind.NONE:
        detail = observation.error_type or observation.failure_kind.value
        raise ParcelArcGISBulkHTTPError(f"ArcGIS rehearsal HTTP failed: {detail}")
    if not observation.response_body:
        raise ParcelArcGISBulkHTTPError("ArcGIS response body cannot be empty")
    return observation.response_body


def _validate_plan_scope(
    snapshot: ParcelArcGISCapabilitySnapshot,
    plan: ParcelArcGISBulkRehearsalPlan,
) -> None:
    expected_query_url = snapshot.layer_url.rstrip("/") + "/query"
    if (
        plan.snapshot_id != snapshot.snapshot_id
        or plan.profile_id != snapshot.profile_id
        or plan.source_key != snapshot.source_key
        or plan.county != snapshot.county
        or plan.object_id_field != snapshot.object_id_field
        or plan.query_url != expected_query_url
    ):
        raise ValueError("ArcGIS rehearsal HTTP plan does not match the snapshot")
    if plan.page_size > snapshot.max_record_count:
        raise ValueError("ArcGIS rehearsal HTTP page size exceeds the snapshot")
    if not snapshot.advertised_ready_for_probe:
        raise ValueError("ArcGIS rehearsal HTTP source lacks advertised query primitives")


def _decode_service_payload(
    response_body: bytes,
    policy: ParcelArcGISBulkHTTPPolicy,
) -> dict[str, object]:
    try:
        payload = decode_json_object(response_body)
    except ValueError as exc:
        raise ParcelArcGISBulkHTTPError("ArcGIS response was not strict UTF-8 JSON") from exc
    service_error = payload.get("error")
    if service_error is not None:
        if not isinstance(service_error, dict):
            raise ParcelArcGISBulkHTTPError("ArcGIS service error payload is malformed")
        code = service_error.get("code")
        if isinstance(code, int) and not isinstance(code, bool):
            if code in policy.retry_status_codes:
                raise ParcelArcGISBulkTransientError(f"arcgis_{code}")
            raise ParcelArcGISBulkHTTPError(f"ArcGIS service returned terminal error {code}")
        raise ParcelArcGISBulkHTTPError("ArcGIS service returned an unclassified error")
    return {str(key): value for key, value in payload.items()}


def _plan_identity(payload: dict[str, object]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    return f"parcel-arcgis-bulk-rehearsal-plan:{digest}"
