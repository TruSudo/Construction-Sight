"""Approved ArcGIS probe transport composition.

This module is the only owner of the temporary HTTP client used to execute the
four-request bounded ArcGIS probe. The CLI receives typed proof objects only.
"""

from __future__ import annotations

import httpx

from constructionsight.parcel_source_acquisition import build_arcgis_probe_plan
from constructionsight.parcel_source_acquisition_http import (
    ParcelArcGISHTTPPolicy,
    execute_arcgis_probe_plan,
    fetch_arcgis_capability_snapshot,
)
from constructionsight.parcel_source_acquisition_models import (
    ParcelArcGISCapabilitySnapshot,
    ParcelArcGISProbeObservation,
    ParcelArcGISProbePlan,
)
from constructionsight.parcel_source_verification_models import ParcelSourceVerificationProfile


def execute_arcgis_bounded_probe(
    profile: ParcelSourceVerificationProfile,
    *,
    sample_size: int,
    timeout_seconds: float,
) -> tuple[
    ParcelArcGISCapabilitySnapshot,
    ParcelArcGISProbePlan,
    tuple[ParcelArcGISProbeObservation, ...],
]:
    """Execute the exact metadata/count/page/replay probe with redirects denied."""

    policy = ParcelArcGISHTTPPolicy(timeout_seconds=timeout_seconds)
    with httpx.Client(follow_redirects=False) as client:
        snapshot = fetch_arcgis_capability_snapshot(
            profile,
            client,
            limitations=(
                "Advertised capabilities require executed probe proof.",
                "This command executes a bounded probe, not a complete acquisition.",
            ),
            policy=policy,
        )
        plan = build_arcgis_probe_plan(snapshot, sample_size=sample_size)
        observations = execute_arcgis_probe_plan(
            snapshot,
            plan,
            client,
            policy=policy,
        )
    return snapshot, plan, observations
