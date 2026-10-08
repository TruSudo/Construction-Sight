"""Local operator GUI with read-only source data and guarded watchlist persistence."""

from __future__ import annotations

import argparse
import json
import webbrowser
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Timer
from typing import cast
from urllib.parse import parse_qs, urlparse

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from constructionsight.bid_pricing_models import BidPriceLineInput, BidPricingPreview
from constructionsight.bid_pricing_service import (
    BidPricingPreviewError,
    build_persisted_bid_pricing_preview,
)
from constructionsight.bid_proposal_models import BidProposalDraft
from constructionsight.bid_proposal_service import (
    BidProposalDraftError,
    build_persisted_bid_proposal_draft,
)
from constructionsight.bid_request_models import BidRequestChannel, BidRequestEvidence
from constructionsight.bid_request_service import (
    BidRequestEvidenceError,
    build_persisted_bid_request_evidence,
)
from constructionsight.ceqanet_ingestion_inbox import build_ceqanet_ingestion_inbox
from constructionsight.domain_types import PartyRole
from constructionsight.lead_workflow_models import LeadWorkflowStatus
from constructionsight.operator_capture_queue import (
    empty_operator_capture_queue,
    load_operator_capture_queue,
)
from constructionsight.operator_dashboard import (
    build_dashboard_snapshot,
    build_entity_neighborhood,
    build_geographic_footprint,
    build_historical_timeline,
    build_workflow_snapshot,
    build_workflow_status_summary,
)
from constructionsight.operator_dashboard_models import RecordSelection
from constructionsight.operator_entity_index import build_entity_index
from constructionsight.operator_parcel_candidates import inspect_parcel_candidates
from constructionsight.operator_results import build_result_ledger_snapshot
from constructionsight.operator_source_aliases import load_source_attribution_aliases
from constructionsight.operator_source_candidate import (
    SourceRecordNotFound,
    build_source_candidate_preview,
)
from constructionsight.operator_source_registry import build_operator_source_registry
from constructionsight.operator_source_revision import build_source_revision_snapshot
from constructionsight.operator_watchlist import (
    add_source_watch,
    archive_source_watch,
    build_operator_watchlist_snapshot,
    create_operator_watchlist_engine,
)
from constructionsight.outreach_preview_models import (
    OutreachChannel,
    OutreachContactReference,
)
from constructionsight.outreach_preview_service import (
    OutreachPreviewError,
    build_persisted_outreach_preview,
)
from constructionsight.storage.operator_read_store import (
    create_operator_read_engine,
    verify_operator_schema,
)
from constructionsight.storage.runtime_artifacts import read_runtime_artifact

_ASSETS = {
    "/": ("operator_command_center.html", "text/html; charset=utf-8"),
    "/workspace": ("operator_ui.html", "text/html; charset=utf-8"),
    "/operator_command_center.js": ("operator_command_center.js", "text/javascript; charset=utf-8"),
    "/operator_command_center.css": ("operator_command_center.css", "text/css; charset=utf-8"),
    "/operator_brand.webp": ("operator_brand.webp", "image/webp"),
    "/operator_ui.js": ("operator_ui.js", "text/javascript; charset=utf-8"),
    "/operator_ui.css": ("operator_ui.css", "text/css; charset=utf-8"),
}


@dataclass(frozen=True)
class _RequestParameters:
    """Validated HTTP query arguments; never forward arbitrary dictionaries to services."""

    kind: RecordSelection
    query: str
    county: str
    limit: int
    offset: int
    entity_key: str | None
    record_id: str | None = None
    role_filter: str = ""


def _parameters(
    query: str,
    *,
    workflow: bool = False,
    footprint: bool = False,
    entity: bool = False,
    entity_index: bool = False,
    candidate: bool = False,
    timeline: bool = False,
    results: bool = False,
) -> _RequestParameters:
    values = parse_qs(query, keep_blank_values=True, max_num_fields=5)
    allowed = (
        {"limit", "offset"}
        if workflow
        else {"kind", "record_id"}
        if candidate
        else {"kind", "q", "county", "entity_key"}
        if timeline
        else {"kind", "county", "role"}
        if entity_index
        else {"kind", "county", "entity_key"}
        if entity
        else {"kind", "q", "county"}
        if footprint
        else {"kind", "q", "county", "limit", "offset"}
    )
    if set(values) - allowed or any(len(value) != 1 for value in values.values()):
        raise ValueError("unsupported or repeated query parameter")
    limit = int(values.get("limit", ["25" if results else "100"])[0])
    offset = int(values.get("offset", ["0"])[0])
    if not 1 <= limit <= (50 if results else 500) or not 0 <= offset <= 1_000_000:
        raise ValueError("invalid page bounds")
    if workflow:
        return _RequestParameters(
            kind="all", query="", county="", limit=limit, offset=offset, entity_key=None
        )
    raw_kind = values.get("kind", ["all"])[0]
    query_text = values.get("q", [""])[0]
    county = values.get("county", [""])[0]
    if raw_kind not in {"all", "ceqa", "permit"} or len(query_text) > 200:
        raise ValueError("invalid record kind or search length")
    if county not in {"", "San Bernardino", "Riverside"}:
        raise ValueError("unsupported county filter")
    role_filter = values.get("role", [""])[0] if entity_index else ""
    if role_filter and role_filter not in {item.value for item in PartyRole}:
        raise ValueError("invalid source-claimed role filter")
    record_id = values["record_id"][0] if "record_id" in values else None
    if candidate and (
        raw_kind not in {"ceqa", "permit"}
        or record_id is None or not record_id or len(record_id) > 255
        or record_id != record_id.strip()
        or any(ord(c) < 32 or ord(c) == 127 for c in record_id)
    ):
        raise ValueError("invalid exact source record selection")
    entity_key = values["entity_key"][0] if "entity_key" in values else None
    if entity and (
        entity_key is None
        or not entity_key
        or entity_key != entity_key.strip()
        or len(entity_key) > 255
    ):
        raise ValueError("invalid or missing entity key")
    if timeline and entity_key is not None and (
        not entity_key or entity_key != entity_key.strip() or len(entity_key) > 255
        or any(ord(char) < 32 or ord(char) == 127 for char in entity_key)
    ):
        raise ValueError("invalid timeline entity key")
    return _RequestParameters(
        kind=cast(RecordSelection, raw_kind),
        query=query_text,
        county=county,
        limit=limit,
        offset=offset,
        entity_key=entity_key,
        record_id=record_id,
        role_filter=role_filter,
    )


def _build_ceqanet_ingestion_payload(
    session: Session,
    *,
    listing_evidence: Path | None,
    queue_evidence: Path | None,
) -> dict[str, object]:
    """Reconcile configured immutable CEQAnet discovery artifacts without side effects."""

    if listing_evidence is None and queue_evidence is None:
        return {
            "schema_version": "ceqanet_ingestion_inbox.v1",
            "configured": False,
            "read_only": True,
            "network_executed": False,
            "persistence_mutated": False,
            "commercial_leads_created": False,
            "candidate_count": 0,
            "pending_capture_count": 0,
            "persisted_candidate_count": 0,
            "conflict_candidate_count": 0,
            "county_unavailable_candidate_count": 0,
            "next_pending_sch": None,
            "candidates": [],
            "limitations": [
                "No exact CEQAnet listing and review-queue evidence pair is configured."
            ],
        }
    if listing_evidence is None or queue_evidence is None:
        raise ValueError("CEQAnet listing and queue evidence must be configured together")
    if listing_evidence.absolute() == queue_evidence.absolute():
        raise ValueError("CEQAnet listing and queue evidence must be distinct artifacts")
    try:
        listing_raw = read_runtime_artifact(listing_evidence, max_bytes=16 * 1024 * 1024)
        queue_raw = read_runtime_artifact(queue_evidence, max_bytes=16 * 1024 * 1024)
        listing_payload = json.loads(listing_raw.decode("utf-8"))
        queue_payload = json.loads(queue_raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise ValueError(f"configured CEQAnet ingestion evidence is unreadable: {exc}") from exc
    if not isinstance(listing_payload, dict) or not isinstance(queue_payload, dict):
        raise ValueError("configured CEQAnet ingestion evidence must contain JSON objects")
    payload = build_ceqanet_ingestion_inbox(
        session,
        listing_payload=listing_payload,
        listing_bytes=listing_raw,
        queue_payload=queue_payload,
        queue_bytes=queue_raw,
    ).model_dump(mode="json")
    payload["configured"] = True
    return cast(dict[str, object], payload)


def create_handler(
    database_path: Path,
    *,
    capture_queue_path: Path | None = None,
    source_attribution_aliases_path: Path | None = None,
    ceqanet_listing_evidence: Path | None = None,
    ceqanet_queue_evidence: Path | None = None,
) -> type[BaseHTTPRequestHandler]:
    """Bind to an existing database without schema creation or migration.\n\n    Source/commercial reads use SQLite mode=ro. A separate guarded engine may\n    mutate only the persisted local watchlist table.\n    """

    if (ceqanet_listing_evidence is None) != (ceqanet_queue_evidence is None):
        raise ValueError("CEQAnet listing and queue evidence must be configured together")
    capture_queue = (
        empty_operator_capture_queue()
        if capture_queue_path is None
        else load_operator_capture_queue(capture_queue_path)
    )
    source_aliases = (
        None
        if source_attribution_aliases_path is None
        else load_source_attribution_aliases(source_attribution_aliases_path)
    )
    engine = create_operator_read_engine(database_path)
    try:
        watchlist_engine = create_operator_watchlist_engine(database_path)
    except Exception:
        engine.dispose()
        raise

    class OperatorHandler(BaseHTTPRequestHandler):
        """Serve loopback reads plus same-origin, watchlist-only local mutations."""

        def do_GET(self) -> None:
            address = self.server.server_address
            if not isinstance(address, tuple):
                raise ValueError("TCP server address required")
            port = address[1]
            allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
            hosts = self.headers.get_all("Host", [])
            origins = self.headers.get_all("Origin", [])
            if (
                len(hosts) != 1
                or hosts[0] not in allowed_hosts
                or (origins and origins != [f"http://{hosts[0]}"])
                or self.headers.get("Sec-Fetch-Site") == "cross-site"
            ):
                self._send_json(
                    {"error": "Local same-origin access required."}, status=HTTPStatus.FORBIDDEN
                )
                return
            try:
                parsed = urlparse(self.path)
                if parsed.scheme or parsed.netloc or parsed.fragment:
                    raise ValueError("local request path required")
                path = parsed.path
                if path in _ASSETS:
                    name, content_type = _ASSETS[path]
                    self._send(
                        HTTPStatus.OK, content_type, Path(__file__).with_name(name).read_bytes()
                    )
                    return
                if path not in {
                    "/api/health",
                    "/api/source-registry",
                    "/api/source-revision",
                    "/api/snapshot",
                    "/api/footprint",
                    "/api/timeline",
                    "/api/entity-neighborhood",
                    "/api/entity-index",
                    "/api/candidate-preview",
                    "/api/capture-queue",
                    "/api/parcel-candidates",
                    "/api/workflows",
                    "/api/results",
                    "/api/watchlist",
                    "/api/workflow-summary",
                    "/api/ingestion-inbox",
                }:
                    self._send_json({"error": "Not found."}, status=HTTPStatus.NOT_FOUND)
                    return
                if (
                    path
                    in {
                        "/api/workflow-summary",
                        "/api/source-registry",
                        "/api/source-revision",
                        "/api/capture-queue",
                        "/api/ingestion-inbox",
                        "/api/watchlist",
                    }
                    and parsed.query
                ):
                    raise ValueError("unfiltered status inspection rejects query parameters")
                parameters = _parameters(
                    parsed.query,
                    workflow=path in {"/api/workflows", "/api/results"},
                    results=path == "/api/results",
                    footprint=path == "/api/footprint",
                    timeline=path == "/api/timeline",
                    entity=path == "/api/entity-neighborhood",
                    entity_index=path == "/api/entity-index",
                    candidate=path in {"/api/candidate-preview", "/api/parcel-candidates"},
                )
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                return
            try:
                with Session(engine, autoflush=False) as session:
                    if path == "/api/health":
                        verify_operator_schema(session)
                        payload: object = {
                            "status": "database_readable",
                            "read_only": True,
                            "live_collection_enabled": False,
                            "watchlist_persistence_enabled": True,
                            "watchlist_source_monitoring_enabled": False,
                            "watchlist_retained_change_detection_enabled": True,
                            "watchlist_remote_source_polling_enabled": False,
                            "outreach_preview_enabled": True,
                            "outreach_send_enabled": False,
                            "bid_request_evidence_enabled": True,
                            "bid_pricing_preview_enabled": True,
                            "bid_proposal_draft_preview_enabled": True,
                            "bid_pricing_enabled": False,
                            "bid_preparation_enabled": False,
                            "bid_submission_enabled": False,
                            "bid_authorization_enabled": False,
                        }
                    elif path == "/api/capture-queue":
                        payload = capture_queue
                    elif path == "/api/source-registry":
                        payload = build_operator_source_registry(
                            session, source_aliases=source_aliases
                        ).model_dump(mode="json")
                    elif path == "/api/source-revision":
                        payload = build_source_revision_snapshot(session)
                    elif path == "/api/ingestion-inbox":
                        payload = _build_ceqanet_ingestion_payload(
                            session,
                            listing_evidence=ceqanet_listing_evidence,
                            queue_evidence=ceqanet_queue_evidence,
                        )
                    elif path == "/api/workflow-summary":
                        payload = build_workflow_status_summary(session)
                    elif path == "/api/results":
                        payload = build_result_ledger_snapshot(
                            session, limit=parameters.limit, offset=parameters.offset
                        )
                    elif path == "/api/watchlist":
                        payload = build_operator_watchlist_snapshot(session)
                    elif path == "/api/workflows":
                        payload = build_workflow_snapshot(
                            session, limit=parameters.limit, offset=parameters.offset
                        )
                    elif path == "/api/parcel-candidates":
                        if parameters.record_id is None or parameters.kind == "all":
                            raise ValueError("missing exact source record selection")
                        payload = inspect_parcel_candidates(
                            session, kind=parameters.kind,
                            record_id=parameters.record_id,
                        ).model_dump(mode="json")
                    elif path == "/api/candidate-preview":
                        if parameters.record_id is None or parameters.kind == "all":
                            raise ValueError("missing exact source record selection")
                        payload = build_source_candidate_preview(
                            session, kind=parameters.kind,
                            record_id=parameters.record_id,
                        ).model_dump(mode="json")
                    elif path == "/api/entity-index":
                        payload = build_entity_index(
                            session, kind=parameters.kind, county=parameters.county,
                            role=parameters.role_filter,
                        ).model_dump(mode="json")
                    elif path == "/api/entity-neighborhood":
                        if parameters.entity_key is None:
                            raise ValueError("missing entity key")
                        payload = build_entity_neighborhood(
                            session,
                            entity_key=parameters.entity_key,
                            kind=parameters.kind,
                            county=parameters.county,
                        ).model_dump(mode="json")
                    elif path == "/api/timeline":
                        payload = build_historical_timeline(
                            session,
                            kind=parameters.kind,
                            query=parameters.query,
                            county=parameters.county,
                            entity_key=parameters.entity_key,
                        ).model_dump(mode="json")
                    elif path == "/api/footprint":
                        payload = build_geographic_footprint(
                            session,
                            kind=parameters.kind,
                            query=parameters.query,
                            county=parameters.county,
                        ).model_dump(mode="json")
                    else:
                        payload = build_dashboard_snapshot(
                            session,
                            kind=parameters.kind,
                            query=parameters.query,
                            county=parameters.county,
                            limit=parameters.limit,
                            offset=parameters.offset,
                        ).model_dump(mode="json")
                self._send_json(payload)
            except SourceRecordNotFound:
                self._send_json(
                    {"error": "Source record not found."}, status=HTTPStatus.NOT_FOUND
                )
            except (SQLAlchemyError, ValueError, TypeError, KeyError):
                self._send_json(
                    {
                        "error": "Stored data could not be read. "
                        "Check the database schema and records; "
                        "the operator does not create or repair the database."
                    },
                    status=HTTPStatus.SERVICE_UNAVAILABLE,
                )


        def do_POST(self) -> None:
            path = urlparse(self.path).path
            if path == "/api/watchlist":
                self._mutate_watchlist(archive=False)
                return
            if path == "/api/outreach-preview":
                self._build_outreach_preview()
                return
            if path == "/api/bid-request-evidence":
                self._build_bid_request_evidence()
                return
            if path == "/api/bid-pricing-preview":
                self._build_bid_pricing_preview()
                return
            if path == "/api/bid-proposal-draft":
                self._build_bid_proposal_draft()
                return
            self._send_json(
                {"error": "Method not implemented."},
                status=HTTPStatus.NOT_IMPLEMENTED,
            )

        def do_DELETE(self) -> None:
            if urlparse(self.path).path != "/api/watchlist":
                self._send_json(
                    {"error": "Method not implemented."},
                    status=HTTPStatus.NOT_IMPLEMENTED,
                )
                return
            self._mutate_watchlist(archive=True)

        def _read_bounded_json_mapping(
            self,
            *,
            expected_fields: frozenset[str],
            label: str,
            max_bytes: int = 65_536,
        ) -> dict[str, object]:
            """Read one exact, bounded JSON object with no undeclared top-level fields."""

            if self.headers.get("Transfer-Encoding") is not None:
                raise ValueError(f"chunked {label} bodies are not supported")
            lengths = self.headers.get_all("Content-Length", [])
            if len(lengths) != 1:
                raise ValueError("exactly one Content-Length header is required")
            try:
                content_length = int(lengths[0], 10)
            except ValueError as exc:
                raise ValueError(f"invalid {label} Content-Length") from exc
            if content_length < 1 or content_length > max_bytes:
                raise ValueError(f"{label} body exceeds bounded request size")
            content_type = self.headers.get("Content-Type", "")
            if content_type.split(";", 1)[0].strip().lower() != "application/json":
                raise ValueError(f"{label} requires application/json")
            raw = self.rfile.read(content_length)
            if len(raw) != content_length:
                raise ValueError(f"incomplete {label} request body")
            try:
                decoded = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError(f"invalid {label} JSON body") from exc
            if not isinstance(decoded, dict):
                raise ValueError(f"{label} body must be a JSON object")
            if set(decoded) != expected_fields:
                raise ValueError(f"{label} requires the exact documented request fields")
            return {str(field): decoded[field] for field in expected_fields}

        def _read_bounded_json_object(
            self,
            *,
            expected_fields: frozenset[str],
            label: str,
            max_bytes: int = 32_768,
        ) -> dict[str, str]:
            """Read one exact bounded JSON object containing only string fields."""

            decoded = self._read_bounded_json_mapping(
                expected_fields=expected_fields,
                label=label,
                max_bytes=max_bytes,
            )
            if any(not isinstance(decoded[field], str) for field in expected_fields):
                raise ValueError(f"{label} request fields must be strings")
            return {field: str(decoded[field]) for field in expected_fields}

        def _build_outreach_preview(self) -> None:
            """Build one same-origin, read-only outreach preview and nothing else."""

            if not self._local_request_allowed(require_origin=True):
                self._send_json(
                    {"error": "Local same-origin preview request required."},
                    status=HTTPStatus.FORBIDDEN,
                )
                return
            try:
                parsed = urlparse(self.path)
                if (
                    parsed.scheme
                    or parsed.netloc
                    or parsed.fragment
                    or parsed.query
                    or parsed.path != "/api/outreach-preview"
                ):
                    raise ValueError("exact outreach preview path required")
                decoded = self._read_bounded_json_object(
                    expected_fields=frozenset(
                        {
                            "workflow_id",
                            "expected_current_status",
                            "channel",
                            "destination",
                            "business_role",
                            "source_name",
                            "source_reference",
                            "contact_review_basis",
                            "subject",
                            "body",
                        }
                    ),
                    label="outreach preview",
                )
                contact = OutreachContactReference(
                    channel=OutreachChannel(decoded["channel"]),
                    destination=decoded["destination"],
                    business_role=decoded["business_role"],
                    source_name=decoded["source_name"],
                    source_reference=decoded["source_reference"],
                    contact_review_basis=decoded["contact_review_basis"],
                )
                with Session(engine, autoflush=False) as session:
                    preview = build_persisted_outreach_preview(
                        session,
                        workflow_id=decoded["workflow_id"],
                        expected_current_status=LeadWorkflowStatus(
                            decoded["expected_current_status"]
                        ),
                        contact=contact,
                        subject=decoded["subject"],
                        body=decoded["body"],
                    )
                self._send_json(preview.to_dict())
            except OutreachPreviewError as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.CONFLICT)
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            except SQLAlchemyError:
                self._send_json(
                    {
                        "error": "Outreach preview is unavailable; "
                        "no external communication was sent."
                    },
                    status=HTTPStatus.SERVICE_UNAVAILABLE,
                )

        def _build_bid_request_evidence(self) -> None:
            """Build one same-origin, read-only proof of a prospect-requested bid."""

            if not self._local_request_allowed(require_origin=True):
                self._send_json(
                    {"error": "Local same-origin bid evidence request required."},
                    status=HTTPStatus.FORBIDDEN,
                )
                return
            try:
                parsed = urlparse(self.path)
                if (
                    parsed.scheme
                    or parsed.netloc
                    or parsed.fragment
                    or parsed.query
                    or parsed.path != "/api/bid-request-evidence"
                ):
                    raise ValueError("exact bid request evidence path required")
                decoded = self._read_bounded_json_object(
                    expected_fields=frozenset(
                        {
                            "workflow_id",
                            "expected_current_status",
                            "request_channel",
                            "requester_business_name",
                            "requester_business_role",
                            "request_source_name",
                            "request_source_reference",
                            "request_review_basis",
                            "request_observed_at",
                            "request_text",
                            "scope_summary",
                        }
                    ),
                    label="bid request evidence",
                )
                try:
                    observed_at = datetime.fromisoformat(
                        decoded["request_observed_at"]
                    )
                except ValueError as exc:
                    raise ValueError(
                        "bid request observed time must be ISO 8601"
                    ) from exc
                with Session(engine, autoflush=False) as session:
                    evidence = build_persisted_bid_request_evidence(
                        session,
                        workflow_id=decoded["workflow_id"],
                        expected_current_status=LeadWorkflowStatus(
                            decoded["expected_current_status"]
                        ),
                        request_channel=BidRequestChannel(
                            decoded["request_channel"]
                        ),
                        requester_business_name=decoded[
                            "requester_business_name"
                        ],
                        requester_business_role=decoded[
                            "requester_business_role"
                        ],
                        request_source_name=decoded["request_source_name"],
                        request_source_reference=decoded[
                            "request_source_reference"
                        ],
                        request_review_basis=decoded[
                            "request_review_basis"
                        ],
                        request_observed_at=observed_at,
                        request_text=decoded["request_text"],
                        scope_summary=decoded["scope_summary"],
                    )
                self._send_json(evidence.to_dict())
            except BidRequestEvidenceError as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.CONFLICT)
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            except SQLAlchemyError:
                self._send_json(
                    {
                        "error": "Bid request evidence is unavailable; "
                        "no pricing, bid preparation, or submission occurred."
                    },
                    status=HTTPStatus.SERVICE_UNAVAILABLE,
                )

        def _build_bid_pricing_preview(self) -> None:
            """Build one same-origin, read-only exact-money pricing preview."""

            if not self._local_request_allowed(require_origin=True):
                self._send_json(
                    {"error": "Local same-origin pricing preview request required."},
                    status=HTTPStatus.FORBIDDEN,
                )
                return
            try:
                parsed = urlparse(self.path)
                if (
                    parsed.scheme
                    or parsed.netloc
                    or parsed.fragment
                    or parsed.query
                    or parsed.path != "/api/bid-pricing-preview"
                ):
                    raise ValueError("exact bid pricing preview path required")
                decoded = self._read_bounded_json_mapping(
                    expected_fields=frozenset(
                        {
                            "request_evidence",
                            "currency_code",
                            "line_items",
                            "assumptions",
                            "exclusions",
                            "validity_note",
                        }
                    ),
                    label="bid pricing preview",
                )
                request_evidence = BidRequestEvidence.model_validate(
                    decoded["request_evidence"]
                )
                raw_lines = decoded["line_items"]
                raw_assumptions = decoded["assumptions"]
                raw_exclusions = decoded["exclusions"]
                if not isinstance(raw_lines, list):
                    raise ValueError("bid pricing preview line_items must be an array")
                if not isinstance(raw_assumptions, list) or not all(
                    isinstance(value, str) for value in raw_assumptions
                ):
                    raise ValueError("bid pricing preview assumptions must be strings")
                if not isinstance(raw_exclusions, list) or not all(
                    isinstance(value, str) for value in raw_exclusions
                ):
                    raise ValueError("bid pricing preview exclusions must be strings")
                currency_code = decoded["currency_code"]
                validity_note = decoded["validity_note"]
                if not isinstance(currency_code, str) or not isinstance(
                    validity_note, str
                ):
                    raise ValueError(
                        "bid pricing currency and validity note must be strings"
                    )
                lines = [
                    BidPriceLineInput.model_validate(item)
                    for item in raw_lines
                ]
                with Session(engine, autoflush=False) as session:
                    preview = build_persisted_bid_pricing_preview(
                        session,
                        request_evidence=request_evidence,
                        currency_code=currency_code,
                        line_items=lines,
                        assumptions=[str(value) for value in raw_assumptions],
                        exclusions=[str(value) for value in raw_exclusions],
                        validity_note=validity_note,
                    )
                self._send_json(preview.to_dict())
            except BidPricingPreviewError as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.CONFLICT)
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            except SQLAlchemyError:
                self._send_json(
                    {
                        "error": "Bid pricing preview is unavailable; "
                        "no commercial terms or submission were authorized."
                    },
                    status=HTTPStatus.SERVICE_UNAVAILABLE,
                )

        def _build_bid_proposal_draft(self) -> None:
            """Build one same-origin, read-only internal proposal draft."""

            if not self._local_request_allowed(require_origin=True):
                self._send_json(
                    {"error": "Local same-origin proposal draft request required."},
                    status=HTTPStatus.FORBIDDEN,
                )
                return
            try:
                parsed = urlparse(self.path)
                if (
                    parsed.scheme
                    or parsed.netloc
                    or parsed.fragment
                    or parsed.query
                    or parsed.path != "/api/bid-proposal-draft"
                ):
                    raise ValueError("exact bid proposal draft path required")
                decoded = self._read_bounded_json_mapping(
                    expected_fields=frozenset(
                        {
                            "request_evidence",
                            "pricing_preview",
                            "proposal_title",
                            "cover_note",
                            "additional_terms",
                        }
                    ),
                    label="bid proposal draft",
                )
                request_evidence = BidRequestEvidence.model_validate(
                    decoded["request_evidence"]
                )
                pricing_preview = BidPricingPreview.model_validate(
                    decoded["pricing_preview"]
                )
                proposal_title = decoded["proposal_title"]
                cover_note = decoded["cover_note"]
                raw_terms = decoded["additional_terms"]
                if not isinstance(proposal_title, str) or not isinstance(
                    cover_note, str
                ):
                    raise ValueError(
                        "bid proposal title and cover note must be strings"
                    )
                if not isinstance(raw_terms, list) or not all(
                    isinstance(value, str) for value in raw_terms
                ):
                    raise ValueError(
                        "bid proposal additional_terms must be strings"
                    )
                with Session(engine, autoflush=False) as session:
                    proposal = build_persisted_bid_proposal_draft(
                        session,
                        request_evidence=request_evidence,
                        pricing_preview=pricing_preview,
                        proposal_title=proposal_title,
                        cover_note=cover_note,
                        additional_terms=[str(value) for value in raw_terms],
                    )
                self._send_json(proposal.to_dict())
            except BidProposalDraftError as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.CONFLICT)
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            except SQLAlchemyError:
                self._send_json(
                    {
                        "error": "Bid proposal draft is unavailable; "
                        "no commercial terms or submission were authorized."
                    },
                    status=HTTPStatus.SERVICE_UNAVAILABLE,
                )

        def _mutate_watchlist(self, *, archive: bool) -> None:
            """Apply one same-origin local watchlist mutation and nothing else."""

            if not self._local_request_allowed(require_origin=True):
                self._send_json(
                    {"error": "Local same-origin write required."},
                    status=HTTPStatus.FORBIDDEN,
                )
                return
            try:
                parsed = urlparse(self.path)
                if (
                    parsed.scheme
                    or parsed.netloc
                    or parsed.fragment
                    or parsed.path != "/api/watchlist"
                ):
                    raise ValueError("watchlist mutation path required")
                values = parse_qs(parsed.query, keep_blank_values=True, max_num_fields=2)
                if set(values) != {"kind", "record_id"} or any(
                    len(value) != 1 for value in values.values()
                ):
                    raise ValueError("exact watchlist kind and record_id are required")
                kind = values["kind"][0]
                record_id = values["record_id"][0]
                with Session(watchlist_engine, autoflush=False) as session:
                    with session.begin():
                        if archive:
                            archive_source_watch(
                                session, kind=kind, record_id=record_id
                            )
                        else:
                            add_source_watch(session, kind=kind, record_id=record_id)
                        payload = build_operator_watchlist_snapshot(session)
                payload["mutation"] = "archived" if archive else "added"
                self._send_json(payload)
            except LookupError:
                self._send_json(
                    {"error": "Exact source/watchlist record not found."},
                    status=HTTPStatus.NOT_FOUND,
                )
            except ValueError as exc:
                self._send_json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
            except (SQLAlchemyError, RuntimeError):
                self._send_json(
                    {
                        "error": "Watchlist persistence is unavailable; "
                        "no source or commercial record was changed."
                    },
                    status=HTTPStatus.SERVICE_UNAVAILABLE,
                )

        def _local_request_allowed(self, *, require_origin: bool = False) -> bool:
            """Require one loopback Host and, for writes, an exact same-origin Origin."""

            address = self.server.server_address
            if not isinstance(address, tuple):
                return False
            port = address[1]
            allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
            hosts = self.headers.get_all("Host", [])
            origins = self.headers.get_all("Origin", [])
            if len(hosts) != 1 or hosts[0] not in allowed_hosts:
                return False
            if self.headers.get("Sec-Fetch-Site") == "cross-site":
                return False
            expected_origin = f"http://{hosts[0]}"
            if require_origin:
                return origins == [expected_origin]
            return not origins or origins == [expected_origin]

        def _send_json(self, payload: object, *, status: HTTPStatus = HTTPStatus.OK) -> None:
            body = json.dumps(payload, sort_keys=True, allow_nan=False).encode("utf-8")
            self._send(status, "application/json; charset=utf-8", body)

        def _send(self, status: HTTPStatus, content_type: str, body: bytes) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", _content_security_policy())
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            return

    return OperatorHandler


def _content_security_policy() -> str:
    return "; ".join(
        [
            "default-src 'none'",
            "script-src 'self'",
            "style-src 'self'",
            "img-src 'self' data:",
            "connect-src 'self'",
            "frame-ancestors 'none'",
            "base-uri 'none'",
            "form-action 'none'",
        ]
    )


def main(*, open_browser_by_default: bool = False) -> None:
    """Run the local-only operator application against an existing database."""

    parser = argparse.ArgumentParser(description="ConstructionSight operator GUI (read only)")
    parser.add_argument("--database", type=Path, default=Path("data/constructionsight.sqlite3"))
    parser.add_argument(
        "--capture-queue",
        type=Path,
        help="Optional retained exact-SCH review queue for read-only dashboard inspection.",
    )
    parser.add_argument(
        "--source-attribution-aliases",
        type=Path,
        default=None,
        help=(
            "Optional retained constructionsight.source_attribution_aliases.v1 JSON "
            "for explicit local provenance attribution."
        ),
    )
    parser.add_argument(
        "--ceqanet-listing-evidence",
        type=Path,
        help="Optional exact governed CEQAnet listing evidence for read-only ingestion status.",
    )
    parser.add_argument(
        "--ceqanet-queue-evidence",
        type=Path,
        help="Optional exact reviewed SCH queue paired with --ceqanet-listing-evidence.",
    )
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--open-browser", action="store_true", default=open_browser_by_default,
        help="Open the local operator in the default browser after the server binds.",
    )
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    try:
        handler_kwargs: dict[str, Path] = {}
        if args.capture_queue is not None:
            handler_kwargs["capture_queue_path"] = args.capture_queue
        if args.source_attribution_aliases is not None:
            handler_kwargs["source_attribution_aliases_path"] = args.source_attribution_aliases
        if args.ceqanet_listing_evidence is not None:
            handler_kwargs["ceqanet_listing_evidence"] = args.ceqanet_listing_evidence
        if args.ceqanet_queue_evidence is not None:
            handler_kwargs["ceqanet_queue_evidence"] = args.ceqanet_queue_evidence
        handler = create_handler(args.database, **handler_kwargs)
    except (OSError, ValueError) as exc:
        parser.error(f"--database must name an existing SQLite file: {exc}")
    except SQLAlchemyError:
        parser.error(
            "--database is unreadable or its schema is incompatible with the operator. "
            "Use a fresh test-drive database initialized by this checkout; preserve the old "
            "database for an explicit upgrade."
        )
    with ThreadingHTTPServer(("127.0.0.1", args.port), handler) as server:
        local_url = f"http://127.0.0.1:{server.server_address[1]}"
        print(f"ConstructionSight operator GUI: {local_url}", flush=True)
        if args.open_browser:
            opener = Timer(0.2, webbrowser.open, args=(local_url,))
            opener.daemon = True
            opener.start()
        with suppress(KeyboardInterrupt):
            server.serve_forever()


def desktop_main() -> None:
    """Launch the explicit local operator browser workspace."""

    main(open_browser_by_default=True)


if __name__ == "__main__":
    main()
