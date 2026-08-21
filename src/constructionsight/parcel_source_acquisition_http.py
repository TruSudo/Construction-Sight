"""Bounded HTTP execution for ArcGIS capability and probe plans."""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import httpx

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


@contextmanager
def open_arcgis_http_client() -> Iterator[httpx.Client]:
    """Yield the approved redirect-denying client used by bounded ArcGIS probes."""

    with httpx.Client(follow_redirects=False) as client:
        yield client


def fetch_arcgis_capability_snapshot(
    profile: ParcelSourceVerificationProfile,
    client: httpx.Client,
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
        client,
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
    client: httpx.Client,
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
            client,
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


def _get_json_object(
    client: httpx.Client,
    url: str,
    *,
    parameters: dict[str, str | int | bool],
    policy: ParcelArcGISHTTPPolicy,
    sleep: Callable[[float], None],
) -> dict[str, Any]:
    if not url.startswith("https://"):
        raise ValueError("ArcGIS HTTP reads require HTTPS")
    last_error: Exception | None = None
    for attempt in range(policy.max_attempts):
        try:
            with client.stream(
                "GET",
                url,
                params=parameters,
                timeout=policy.timeout_seconds,
                headers={"Accept": "application/json"},
                follow_redirects=False,
            ) as response:
                if response.history:
                    raise ParcelArcGISProbeExecutionError(
                        "ArcGIS HTTP redirects are forbidden"
                    )
                if response.status_code in policy.retry_status_codes:
                    raise _RetryableStatus(response.status_code)
                if response.status_code != 200:
                    raise ParcelArcGISProbeExecutionError(
                        f"ArcGIS request returned HTTP {response.status_code}"
                    )
                response_body = _read_bounded_response(response, policy.max_response_bytes)
            payload: Any = json.loads(response_body)
            if not isinstance(payload, dict):
                raise ParcelArcGISProbeExecutionError(
                    "ArcGIS response must be a JSON object"
                )
            return {str(key): value for key, value in payload.items()}
        except ParcelArcGISProbeExecutionError:
            raise
        except (httpx.TransportError, _RetryableStatus) as exc:
            last_error = exc
            if attempt + 1 >= policy.max_attempts:
                break
            sleep(policy.retry_delays_seconds[attempt])
        except ValueError as exc:
            raise ParcelArcGISProbeExecutionError(
                "ArcGIS response was not valid JSON"
            ) from exc
    raise ParcelArcGISProbeExecutionError(
        f"ArcGIS request failed after {policy.max_attempts} attempts"
    ) from last_error


def _read_bounded_response(response: httpx.Response, limit: int) -> bytes:
    declared_length = response.headers.get("content-length")
    if declared_length is not None:
        try:
            declared_size = int(declared_length)
        except ValueError as exc:
            raise ParcelArcGISProbeExecutionError(
                "ArcGIS response Content-Length is malformed"
            ) from exc
        if declared_size < 0:
            raise ParcelArcGISProbeExecutionError(
                "ArcGIS response Content-Length is malformed"
            )
        if declared_size > limit:
            raise ParcelArcGISProbeExecutionError(
                "ArcGIS response exceeded the configured byte limit"
            )
    body = bytearray()
    observed_size = 0
    for chunk in response.iter_bytes():
        observed_size += len(chunk)
        if observed_size > limit:
            raise ParcelArcGISProbeExecutionError(
                "ArcGIS response exceeded the configured byte limit"
            )
        body.extend(chunk)
    return bytes(body)


class _RetryableStatus(Exception):
    def __init__(self, status_code: int) -> None:
        super().__init__(f"retryable ArcGIS HTTP status: {status_code}")


def _utc_now() -> datetime:
    return datetime.now(UTC)
