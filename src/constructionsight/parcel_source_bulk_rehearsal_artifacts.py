"""Exact response envelopes and atomic artifact retention for ArcGIS rehearsals."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

from constructionsight.parcel_source_bulk_rehearsal_models import digest_json_payload
from constructionsight.storage.runtime_artifacts import (
    RuntimeArtifactError,
    open_runtime_artifact,
    publish_runtime_artifact,
    read_bounded_artifact_stream,
    read_runtime_artifact,
    runtime_artifact_parts,
)

_MAX_RETAINED_RESPONSE_BYTES = 16 * 1024 * 1024


class ParcelArcGISBulkArtifactError(RuntimeError):
    """Raised when exact rehearsal response evidence cannot be retained."""


class ParcelArcGISBulkArtifactKind(StrEnum):
    """Ordered response classes retained by one complete rehearsal."""

    STARTING_COUNT = "starting_count"
    PAGE = "page"
    ENDING_COUNT = "ending_count"


@dataclass(frozen=True)
class ParcelArcGISBulkCountResponse:
    """Exact ArcGIS count response body with a validated positive count."""

    count: int
    response_body: bytes

    def __post_init__(self) -> None:
        if isinstance(self.count, bool) or not isinstance(self.count, int) or self.count < 1:
            raise ValueError("ArcGIS count response must contain a positive integer")
        payload = decode_json_object(self.response_body)
        if payload.get("count") != self.count:
            raise ValueError("ArcGIS count response body does not match its count")

    @property
    def response_digest(self) -> str:
        return digest_response_body(self.response_body)

    @classmethod
    def from_count(cls, count: int) -> ParcelArcGISBulkCountResponse:
        """Build a deterministic response for tests and offline fixtures."""

        return cls(
            count=count,
            response_body=canonical_json_bytes({"count": count}),
        )


@dataclass(frozen=True)
class ParcelArcGISBulkPageResponse:
    """Exact successful ArcGIS object-ID page response body."""

    response_body: bytes

    def __post_init__(self) -> None:
        decode_json_object(self.response_body)

    @property
    def response_digest(self) -> str:
        return digest_response_body(self.response_body)

    def payload(self) -> dict[str, Any]:
        return decode_json_object(self.response_body)

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> ParcelArcGISBulkPageResponse:
        """Build a deterministic exact response for tests and offline fixtures."""

        return cls(response_body=canonical_json_bytes(payload))


@dataclass(frozen=True)
class ParcelArcGISBulkArtifactReceipt:
    """Receipt binding one exact response body to its retained artifact."""

    kind: ParcelArcGISBulkArtifactKind
    sequence_index: int
    response_digest: str
    response_size: int
    artifact_reference: str

    def __post_init__(self) -> None:
        if self.sequence_index < 0:
            raise ValueError("ArcGIS artifact sequence index cannot be negative")
        if len(self.response_digest) != 64 or any(
            character not in "0123456789abcdef" for character in self.response_digest
        ):
            raise ValueError("ArcGIS artifact response digest is malformed")
        if self.response_size < 1:
            raise ValueError("ArcGIS artifact response body cannot be empty")
        if (
            not self.artifact_reference
            or self.artifact_reference != self.artifact_reference.strip()
        ):
            raise ValueError("ArcGIS artifact reference must be nonempty and trimmed")
        try:
            parts = runtime_artifact_parts(self.artifact_reference)
        except RuntimeArtifactError as exc:
            raise ValueError("ArcGIS artifact reference must be one safe file name") from exc
        if len(parts) != 1:
            raise ValueError("ArcGIS artifact reference must be one safe file name")


class ParcelArcGISBulkArtifactStore(Protocol):
    """Durable exact-byte retention boundary for successful rehearsal responses."""

    def retain(
        self,
        *,
        kind: ParcelArcGISBulkArtifactKind,
        sequence_index: int,
        response_body: bytes,
    ) -> ParcelArcGISBulkArtifactReceipt:
        """Persist exact bytes or accept an identical existing artifact."""


class JSONFileParcelArcGISBulkArtifactStore:
    """Atomic exact-byte response storage with digest-addressed file names."""

    def __init__(self, directory: Path) -> None:
        self._directory = directory

    def retain(
        self,
        *,
        kind: ParcelArcGISBulkArtifactKind,
        sequence_index: int,
        response_body: bytes,
    ) -> ParcelArcGISBulkArtifactReceipt:
        if sequence_index < 0:
            raise ValueError("ArcGIS artifact sequence index cannot be negative")
        if not response_body:
            raise ValueError("ArcGIS artifact response body cannot be empty")
        if len(response_body) > _MAX_RETAINED_RESPONSE_BYTES:
            raise ParcelArcGISBulkArtifactError("ArcGIS response exceeds artifact byte limit")
        digest = digest_response_body(response_body)
        filename = f"{sequence_index:08d}-{kind.value}-{digest}.json"
        path = self._directory / filename
        try:
            publish_runtime_artifact(
                path, (response_body,), max_bytes=_MAX_RETAINED_RESPONSE_BYTES,
            )
        except FileExistsError:
            try:
                with open_runtime_artifact(path, durable=True) as retained_file:
                    retained_bytes = read_bounded_artifact_stream(
                        retained_file, max_bytes=len(response_body),
                    )
                    if retained_bytes != response_body:
                        raise ParcelArcGISBulkArtifactError(
                            "ArcGIS artifact digest conflicts with retained response bytes"
                        ) from None
            except (OSError, RuntimeArtifactError) as exc:
                raise ParcelArcGISBulkArtifactError(
                    "ArcGIS artifact digest conflicts with retained response bytes"
                ) from exc
        return ParcelArcGISBulkArtifactReceipt(
            kind=kind,
            sequence_index=sequence_index,
            response_digest=digest,
            response_size=len(response_body),
            artifact_reference=filename,
        )

    def read(self, receipt: ParcelArcGISBulkArtifactReceipt) -> bytes:
        """Reload exact retained bytes and revalidate the receipt digest and size."""

        path = self._directory / receipt.artifact_reference
        if receipt.response_size > _MAX_RETAINED_RESPONSE_BYTES:
            raise ParcelArcGISBulkArtifactError("ArcGIS response exceeds artifact byte limit")
        try:
            response_body = read_runtime_artifact(path, max_bytes=receipt.response_size)
        except FileNotFoundError as exc:
            raise ParcelArcGISBulkArtifactError(
                "ArcGIS response artifact was not retained"
            ) from exc
        except RuntimeArtifactError as exc:
            raise ParcelArcGISBulkArtifactError(
                "ArcGIS response artifact size changed or its path is unsafe"
            ) from exc
        if len(response_body) != receipt.response_size:
            raise ParcelArcGISBulkArtifactError("ArcGIS response artifact size changed")
        if digest_response_body(response_body) != receipt.response_digest:
            raise ParcelArcGISBulkArtifactError("ArcGIS response artifact digest changed")
        return response_body


def decode_json_object(response_body: bytes) -> dict[str, Any]:
    """Decode one strict UTF-8 JSON object from exact retained response bytes."""

    if not response_body:
        raise ValueError("ArcGIS response body cannot be empty")
    try:
        payload = json.loads(response_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("ArcGIS response body must be strict UTF-8 JSON") from exc
    if not isinstance(payload, dict):
        raise ValueError("ArcGIS response body must contain a JSON object")
    return payload


def canonical_json_bytes(payload: dict[str, Any]) -> bytes:
    """Return deterministic UTF-8 JSON bytes for fixtures and offline replay."""

    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return encoded.encode("utf-8")


def digest_response_body(response_body: bytes) -> str:
    """Return SHA-256 over exact response bytes."""

    return hashlib.sha256(response_body).hexdigest()


def canonical_payload_digest(payload: dict[str, Any]) -> str:
    """Expose the separate normalized-payload digest when comparison needs it."""

    return digest_json_payload(payload)
