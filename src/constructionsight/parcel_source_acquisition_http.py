"""Bounded HTTP execution for ArcGIS capability and probe plans."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx

from constructionsight.http_transport import execute_bounded_http
from constructionsight.http_transport_models import (
    BoundedHttpObservation,
    BoundedHttpPolicy,
    HttpFailureKind,
    canonicalize_http_url,
)
from constructionsight.parcel_source_acquisition import (
    parse_arcgis_capability_snapshot,
    parse_arcgis_probe_observation,
)
from constructionsight.parcel_source_acquisition_models import (
    ParcelArcGISCapabilitySnapshot,
    ParcelArcGISProbeObservation,
    ParcelArcGISProbePlan,
)
from constructionsight.parcel_source_verification_models import (
    ParcelSourceVerificationProfile,
)

_ARCGIS_ALLOWED_HOSTS = ("arcgis.com", "*.arcgis.com", "*.gov")
_ARCGIS_ALLOWED_PATH_PREFIXES = ("/arcgis/rest/services/", "/server/rest/services/")
_ARCGIS_ACCEPTED_MEDIA_TYPES = ("application/json", "text/plain")


class ParcelArcGISProbeExecutionError(RuntimeError):
    """Raised when a bounded ArcGIS request fails closed."""


@dataclass(frozen=True)
class ParcelArcGISHTTPPolicy:
    """Explicit request, response-size, and retry limits for public ArcGIS reads."""

    timeout_seconds: float = 30.0
    max_response_bytes: int = 2_000_000
    max_attempts: int = 3
    retry_delays_seconds: tuple[float, ...] = (0.25, 1.0)
    retry_status_codes: frozenset[int] = field(
        default_factory=lambda: frozenset({429, 500, 502, 503, 504})
    )

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("ArcGIS timeout must be positive")
        if self.max_response_bytes < 1:
            raise ValueError("ArcGIS response limit must be positive")
        if self.max_attempts < 1 or self.max_attempts > 5:
            raise ValueError("ArcGIS max attempts must be between 1 and 5")
        if len(self.retry_delays_seconds) < self.max_attempts - 1:
            raise ValueError("ArcGIS retry policy requires a delay per retry")
        if any(delay < 0 for delay in self.retry_delays_seconds):
            raise ValueError("ArcGIS retry delays cannot be negative")

    def bounded_policy(self, request_url: str) -> BoundedHttpPolicy:
        """Bind one exact ArcGIS request identity to the central HTTP engine."""

        return BoundedHttpPolicy(
            policy_id="CS-NET-004",
            allowed_methods=("GET",),
            allowed_hosts=_ARCGIS_ALLOWED_HOSTS,
            allowed_path_prefixes=_ARCGIS_ALLOWED_PATH_PREFIXES,
            connect_timeout_seconds=self.timeout_seconds,
            read_timeout_seconds=self.timeout_seconds,
            write_timeout_seconds=self.timeout_seconds,
            pool_timeout_seconds=self.timeout_seconds,
            max_response_bytes=self.max_response_bytes,
            accepted_media_types=_ARCGIS_ACCEPTED_MEDIA_TYPES,
            accepted_encodings=("utf-8",),
            user_agent="ConstructionSight-ArcGISProbe/1.0",
            allowed_request_urls=(request_url,),
        )


def fetch_arcgis_capability_snapshot(
    profile: ParcelSourceVerificationProfile,
    *,
    limitations: tuple[str, ...],
    policy: ParcelArcGISHTTPPolicy | None = None,
    now: Callable[[], datetime] | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> ParcelArcGISCapabilitySnapshot:
    """Fetch one live layer metadata document and parse its exact schema projection."""

    if not profile.source_url or not profile.source_url.startswith("https://"):
        raise ValueError("ArcGIS capability fetch requires a verified HTTPS source URL")
    payload = _get_json_object(
        profile.source_url,
        parameters={"f": "json"},
        policy=policy or ParcelArcGISHTTPPolicy(),
        sleep=sleep,
    )
    return parse_arcgis_capability_snapshot(
        profile,
        payload,
        observed_at=(now or _utc_now)(),
        limitations=limitations,
    )


def execute_arcgis_probe_plan(
    snapshot: ParcelArcGISCapabilitySnapshot,
    plan: ParcelArcGISProbePlan,
    *,
    policy: ParcelArcGISHTTPPolicy | None = None,
    now: Callable[[], datetime] | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> list[ParcelArcGISProbeObservation]:
    """Execute only the four bounded, non-geometry requests in a validated plan."""

    if (
        plan.snapshot_id != snapshot.snapshot_id
        or plan.profile_id != snapshot.profile_id
        or plan.source_key != snapshot.source_key
        or plan.county != snapshot.county
    ):
        raise ValueError("ArcGIS HTTP probe plan scope does not match snapshot")
    if any(
        request.object_id_field != snapshot.object_id_field
        or request.schema_fingerprint != snapshot.schema_fingerprint
        for request in plan.requests
    ):
        raise ValueError("ArcGIS HTTP probe requests do not match snapshot schema")
    if plan.bulk_run_authorized:
        raise ValueError("ArcGIS HTTP executor refuses bulk-authorized plans")
    query_url = snapshot.layer_url.rstrip("/") + "/query"
    active_policy = policy or ParcelArcGISHTTPPolicy()
    clock = now or _utc_now
    observations: list[ParcelArcGISProbeObservation] = []
    for request in plan.requests:
        payload = _get_json_object(
            query_url,
            parameters=request.query_parameters,
            policy=active_policy,
            sleep=sleep,
        )
        observations.append(
            parse_arcgis_probe_observation(
                request,
                payload,
                observed_at=clock(),
            )
        )
    return observations


def _exact_request_url(
    url: str,
    parameters: dict[str, str | int | bool],
) -> str:
    if not url.startswith("https://"):
        raise ValueError("ArcGIS HTTP reads require HTTPS")
    request_url = str(httpx.URL(url, params=parameters))
    return canonicalize_http_url(request_url)


def _get_json_object(
    url: str,
    *,
    parameters: dict[str, str | int | bool],
    policy: ParcelArcGISHTTPPolicy,
    sleep: Callable[[float], None],
) -> dict[str, Any]:
    request_url = _exact_request_url(url, parameters)
    last_error: Exception | None = None
    for attempt in range(policy.max_attempts):
        observation = execute_bounded_http(
            request_url,
            "GET",
            policy.bounded_policy(request_url),
        )
        retry_error = _retryable_error(observation, policy)
        if retry_error is not None:
            last_error = retry_error
            if attempt + 1 >= policy.max_attempts:
                break
            sleep(policy.retry_delays_seconds[attempt])
            continue
        response_body = _require_success_body(observation)
        try:
            payload: Any = json.loads(response_body)
        except ValueError as exc:
            raise ParcelArcGISProbeExecutionError(
                "ArcGIS response was not valid JSON"
            ) from exc
        if not isinstance(payload, dict):
            raise ParcelArcGISProbeExecutionError(
                "ArcGIS response must be a JSON object"
            )
        return {str(key): value for key, value in payload.items()}
    raise ParcelArcGISProbeExecutionError(
        f"ArcGIS request failed after {policy.max_attempts} attempts"
    ) from last_error


def _retryable_error(
    observation: BoundedHttpObservation,
    policy: ParcelArcGISHTTPPolicy,
) -> Exception | None:
    if observation.status_code in policy.retry_status_codes:
        return _RetryableStatus(observation.status_code)
    if observation.failure_kind in {HttpFailureKind.TIMEOUT, HttpFailureKind.TRANSPORT}:
        return RuntimeError(observation.error_type or observation.failure_kind.value)
    return None


def _require_success_body(observation: BoundedHttpObservation) -> bytes:
    if observation.failure_kind is HttpFailureKind.OVERSIZED_RESPONSE:
        raise ParcelArcGISProbeExecutionError(
            "ArcGIS response exceeded the configured byte limit"
        )
    if observation.failure_kind is HttpFailureKind.MALFORMED_RESPONSE:
        raise ParcelArcGISProbeExecutionError(
            "ArcGIS response Content-Length is malformed"
        )
    if observation.failure_kind is HttpFailureKind.REDIRECT:
        status_code = observation.status_code
        raise ParcelArcGISProbeExecutionError(
            f"ArcGIS request returned HTTP {status_code}"
        )
    if observation.status_code != 200:
        raise ParcelArcGISProbeExecutionError(
            f"ArcGIS request returned HTTP {observation.status_code}"
        )
    if observation.failure_kind is not HttpFailureKind.NONE:
        raise ParcelArcGISProbeExecutionError(
            f"ArcGIS request failed: {observation.error_type or observation.failure_kind.value}"
        )
    return observation.response_body


class _RetryableStatus(Exception):
    def __init__(self, status_code: int) -> None:
        super().__init__(f"retryable ArcGIS HTTP status: {status_code}")


def _utc_now() -> datetime:
    return datetime.now(UTC)
