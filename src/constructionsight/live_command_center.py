"""One-command, read-only localhost Command Center backed by official SMARTS rows."""

from __future__ import annotations

import argparse
import csv
import io
import json
import shutil
import sqlite3
import sys
import tempfile
import threading
import webbrowser
import zipfile
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, cast
from urllib.parse import parse_qs, unquote, urlsplit
from zoneinfo import ZoneInfo

import httpx

from constructionsight import (
    calibration,
    collection_schedule,
    commercial_catalog,
    data_folder,
    offline_map,
)
from constructionsight import command_center_commercial as commercial
from constructionsight import command_center_investigation_watch as investigation_watch
from constructionsight import command_center_state as state
from constructionsight.command_center_arcgis_proofs import (
    native_arcgis_proof_inventory,
    persist_reviewed_arcgis_proof,
    retained_arcgis_proof_preview,
)
from constructionsight.command_center_canonical_leads import (
    apply_retained_canonical_result_review,
    canonical_lead_preview,
    retain_reviewed_canonical_candidate,
    retained_canonical_lead_transition_history,
    retained_canonical_lead_workflows,
    transition_retained_canonical_review,
)
from constructionsight.command_center_ceqanet_acquisition import (
    execute_reviewed_original_ceqanet_csv,
    execute_reviewed_original_ceqanet_listing,
    preview_original_ceqanet_csv,
    preview_original_ceqanet_listing,
)
from constructionsight.command_center_ceqanet_detail import (
    execute_reviewed_original_ceqanet_detail,
    preview_original_ceqanet_detail,
)
from constructionsight.command_center_ceqanet_discovery import (
    execute_reviewed_original_ceqanet_discovery,
    preview_original_ceqanet_discovery,
)
from constructionsight.command_center_ceqanet_maturity import (
    original_retained_ceqanet_maturity,
)
from constructionsight.command_center_ceqanet_policy_audit import (
    original_retained_ceqanet_policy_audit,
)
from constructionsight.command_center_ceqanet_recurring_attempt import (
    execute_reviewed_original_ceqanet_recurring_attempt,
    preview_original_ceqanet_recurring_attempt,
)
from constructionsight.command_center_ceqanet_recurring_audit import (
    original_retained_ceqanet_recurring_audit,
)
from constructionsight.command_center_ceqanet_retained_import import (
    apply_reviewed_retained_ceqanet_import,
    preview_retained_ceqanet_import,
)
from constructionsight.command_center_ceqanet_series_append import (
    apply_reviewed_original_ceqanet_series_append,
    preview_original_ceqanet_series_append,
)
from constructionsight.command_center_ceqanet_series_audit import (
    original_retained_ceqanet_series_audit,
)
from constructionsight.command_center_ceqanet_series_execution import (
    execute_reviewed_original_ceqanet_series_request,
    preview_original_ceqanet_series_request,
)
from constructionsight.command_center_external_source_intelligence import (
    original_external_source_intelligence,
)
from constructionsight.command_center_graph import graph_view
from constructionsight.command_center_investigations import (
    apply_investigation_review,
    investigation_review_preview,
    investigation_view,
)
from constructionsight.command_center_legacy_attribution import original_workflow_source_attribution
from constructionsight.command_center_legacy_export import (
    original_ceqanet_archive_path,
    original_ceqanet_artifact_bytes,
    original_ceqanet_export,
    original_ceqanet_export_status,
    original_ceqanet_report_bytes,
)
from constructionsight.command_center_legacy_lineage import original_candidate_workflow_lineage
from constructionsight.command_center_legacy_reconciliation import (
    enqueue_legacy_reconciliation,
    enqueue_legacy_reconciliation_batch,
    original_source_replay_audit,
    preview_legacy_reconciliation,
    preview_legacy_reconciliation_batch,
)
from constructionsight.command_center_original_checklist import (
    apply_reviewed_original_source_registry_update,
    preview_original_manual_checklist,
    review_original_manual_checklist,
)
from constructionsight.command_center_parcel_readiness import (
    parcel_source_readiness_snapshot,
    preview_retained_parcel_sample,
)
from constructionsight.command_center_parcel_reconciliation import (
    enqueue_original_parcel_reconciliation,
    preview_original_parcel_reconciliation,
)
from constructionsight.command_center_retained_previews import retained_commercial_preview
from constructionsight.command_center_smarts_catalog import (
    execute_reviewed_original_smarts_catalog,
    preview_original_smarts_catalog,
)
from constructionsight.command_center_smarts_roster import (
    original_retained_smarts_roster_audit,
)
from constructionsight.command_center_smarts_roster_collection import (
    execute_reviewed_original_smarts_roster_collection,
    preview_original_smarts_roster_collection,
)
from constructionsight.command_center_smarts_source_review import (
    native_original_smarts_source_review,
)
from constructionsight.command_center_source_docket import (
    preview_original_source_docket,
    stage_reviewed_original_source_docket,
)
from constructionsight.command_center_source_reachability import (
    check_reviewed_original_source_readiness,
    preview_exact_original_source_readiness,
)
from constructionsight.command_center_sources import (
    SOURCE_INSPECTION_ROUTES,
    retained_watch_notifications,
    source_inspection,
    source_watch_action,
)
from constructionsight.contact_call_list import (
    annotate_contacts,
    bulk_import,
    call_list_csv,
    contact_coverage,
)
from constructionsight.fontana_permits import fetch_candidates, retain_candidates
from constructionsight.lead_quality import quality_report
from constructionsight.lead_watchlist import update_watch, watchlist
from constructionsight.lead_workflow import (
    REASONS,
    STATUSES,
    begin_run,
    capture_lock,
    connect,
    csv_export,
    developer_accounts,
    finish_run,
    get_feedback,
    outcome_report,
    run_history,
    save_feedback,
)
from constructionsight.operator_source_aliases import load_source_attribution_aliases
from constructionsight.parcel_use_enrichment import load_claims
from constructionsight.security_fit import WEIGHTS_PATH, load_weights, rank_leads
from constructionsight.smarts_active import collect_active
from constructionsight.smarts_api import USER_AGENT
from constructionsight.spatial_parcel_use import load_claims as load_spatial_claims
from constructionsight.storage.runtime_artifacts import open_runtime_artifact

ASSETS = Path(__file__).parent / "command_center"


READINESS_RULE = (
    "Ready for Outreach: high security fit, independently verified site, at least one "
    "sourced contact, no conflicting fields and no Do-Not-Contact flag. In Review: "
    "a human check is needed. Not Ready: low fit, excluded infrastructure or insufficient data."
)


def readiness(row: dict[str, Any]) -> str:
    if row.get("do_not_contact") or row.get("feedback", {}).get("status") == "Not a fit":
        return "not_ready"
    if row.get("fit_band") == "low" or row.get("project_type") == "infrastructure":
        return "not_ready"
    contacts = row.get("sourced_contacts", [])
    has_contact = any(
        isinstance(c, dict) and c.get("source") and (c.get("email") or c.get("phone"))
        for c in contacts
    )
    verification = row.get("site_verification", {})
    if (
        row.get("fit_band") == "high"
        and isinstance(verification, dict)
        and verification.get("verified") is True
        and verification.get("source")
        and has_contact
        and row.get("project_type") in ("industrial", "commercial", "residential")
        and not row.get("conflicting_fields")
    ):
        return "ready"
    return "review"


def projection(
    snapshot: dict[str, Any], directory: Path | None = None, *, parity: bool = False
) -> dict[str, Any]:
    if parity and (not snapshot.get("demo") or directory is not None):
        raise ValueError("Mockup parity requires an isolated Demo fixture")
    weights_path = directory / "weights.json" if directory else None
    prefs = state.settings(directory) if directory else None
    rows = rank_leads(
        snapshot["rows"], weights=prefs["weights"] if prefs else load_weights(weights_path)
    )
    parcel_warning = None
    if directory:
        try:
            parcel_claims = {**load_spatial_claims(directory, rows), **load_claims(directory, rows)}
        except (OSError, ValueError, KeyError, TypeError) as exc:
            parcel_claims = {}
            parcel_warning = "Parcel enrichment rejected; no parcel type claims applied: " + str(
                exc
            )
        for row in rows:
            if row.get("source_key") in parcel_claims:
                row["parcel_use_claim"] = parcel_claims[row["source_key"]]
        rows = rank_leads(rows, weights=prefs["weights"] if prefs else load_weights(weights_path))
    feedback = get_feedback(directory) if directory else {}
    permits_file = directory / "fontana-permits.json" if directory else None
    permits = json.loads(permits_file.read_text()) if permits_file and permits_file.exists() else {}
    for row in rows:
        row["feedback"] = feedback.get(row.get("source_key", ""), {"status": "New"})
        candidate = permits.get(row.get("source_key", ""))
        row["permit_candidates"] = (
            {k: v for k, v in candidate.items() if k != "raw_response"} if candidate else None
        )
    if directory:
        state.attach(directory, rows)
        assert prefs is not None
        rows = rank_leads(rows, weights=prefs["weights"])
    rows = annotate_contacts(rows)
    cutoff = (datetime.now(UTC) - timedelta(days=7)).isoformat()
    local_today = datetime.now(ZoneInfo("America/Los_Angeles")).date()
    for row in rows:
        row["readiness"] = readiness(row)
        row["new_week"] = bool(row.get("first_seen") and row["first_seen"] >= cutoff)
        if parity:
            view = row["parity_view"]
            row.update(view)
        first_seen = row.get("first_seen")
        row["new_today"] = bool(
            first_seen
            and datetime.fromisoformat(first_seen)
            .astimezone(ZoneInfo("America/Los_Angeles"))
            .date()
            == local_today
        )
    map_file = directory / "map.json" if directory else None
    map_settings = (
        prefs["map"]
        if prefs
        else json.loads(map_file.read_text())
        if map_file and map_file.exists()
        else {"offline_first": True, "url_template": None, "attribution": None}
    )
    template = map_settings.get("url_template")
    if template is not None and (
        not isinstance(template, str)
        or not template.startswith("https://")
        or any("{" + key + "}" not in template for key in ("z", "x", "y"))
    ):
        raise ValueError("Tile template must use HTTPS and contain {z}, {x}, {y}")
    runs = run_history(directory) if directory else []
    latest = runs[0] if runs else None
    return {
        "rows": rows,
        "settings": prefs,
        "deltas": state.deltas(directory, rows) if directory else {},
        "read_only": directory is None,
        "local_map": offline_map.metadata(directory / "basemap.pmtiles")
        if directory and (directory / "basemap.pmtiles").exists()
        else None,
        "readiness_rule": READINESS_RULE,
        "mockup_parity": parity,
        "parity_watches": snapshot.get("parity_watches", []) if parity else [],
        "warning": (
            ("Capture failed; showing last good data. " + str(latest["error"]))
            if latest and latest["outcome"] == "error"
            else (collection_schedule.warning(directory) if directory else None) or parcel_warning
        ),
        "map_settings": map_settings,
        "statuses": STATUSES,
        "reasons": REASONS,
        "captured_at": snapshot["captured_at"],
        "requests": snapshot["requests"],
        "totals": snapshot["totals"],
        "baseline": snapshot["baseline"],
        "demo": snapshot.get("demo", False),
        "missing_count": snapshot["missing_count"],
        "duplicate_rows": snapshot.get("duplicate_rows", 0),
        "missing_identity_rows": snapshot.get("missing_identity_rows", 0),
        "kpis": {
            "total": len(rows),
            "high": sum(r["fit_band"] == "high" for r in rows),
            "review": sum(r["fit_band"] == "review" for r in rows),
            "low": sum(r["fit_band"] == "low" for r in rows),
            "new_week": sum(bool(r.get("first_seen") and r["first_seen"] >= cutoff) for r in rows),
        },
    }


def make_server(
    snapshot: dict[str, Any],
    port: int,
    directory: Path | None = None,
    *,
    parity: bool = False,
    startup_directory: Path | None = None,
    operator_database: Path | None = None,
    operator_capture_queue: Path | None = None,
    operator_ceqanet_listing: Path | None = None,
    operator_ceqanet_review_queue: Path | None = None,
    operator_ceqanet_csv_evidence: Path | None = None,
    operator_ceqanet_csv_access_policy: Path | None = None,
    operator_ceqanet_csv_series_manifest: Path | None = None,
    operator_ceqanet_recurring_checklist: Path | None = None,
    operator_ceqanet_recurring_definition: Path | None = None,
    operator_ceqanet_recurring_manifest: Path | None = None,
    operator_smarts_journal: Path | None = None,
    operator_smarts_collection_roster: Path | None = None,
    operator_smarts_collection_checkpoint: Path | None = None,
    operator_smarts_history: Path | None = None,
    operator_smarts_review_manifest: Path | None = None,
    operator_ceqanet_chain_report: Path | None = None,
    operator_source_attribution_aliases: Path | None = None,
    operator_arcgis_proof_bundle: Path | None = None,
) -> ThreadingHTTPServer:
    if parity and (not snapshot.get("demo") or directory is not None):
        raise ValueError("Mockup parity requires an isolated Demo fixture")
    if operator_database is not None:
        if parity or snapshot.get("demo"):
            raise ValueError("operator source data cannot be exposed in demo/parity mode")
        if operator_database.is_symlink() or not operator_database.is_file():
            raise ValueError("operator source database must be an existing regular file")
    if operator_smarts_collection_roster is not None and (
        parity or snapshot.get("demo") or directory is None or operator_database is None
    ):
        raise ValueError("original SMARTS collection roster requires real operator data")
    if operator_smarts_collection_checkpoint is not None and (
        operator_smarts_collection_roster is None
        or operator_smarts_journal is None
        or operator_database is None
        or parity
        or snapshot.get("demo")
        or directory is None
    ):
        raise ValueError(
            "original SMARTS checkpoint requires exact roster, journal and real data"
        )
    if operator_smarts_collection_checkpoint is not None and (
        operator_smarts_collection_checkpoint.is_symlink()
        or (
            operator_smarts_collection_checkpoint.exists()
            and not operator_smarts_collection_checkpoint.is_file()
        )
    ):
        raise ValueError("original SMARTS checkpoint must be a regular file or new path")
    if operator_smarts_collection_roster is not None and (
        operator_smarts_collection_roster.is_symlink()
        or not operator_smarts_collection_roster.is_file()
    ):
        raise ValueError("original SMARTS roster must be an existing regular file")
    if operator_smarts_review_manifest is not None and (
        parity or snapshot.get("demo") or directory is None or operator_database is None
    ):
        raise ValueError("SMARTS original source review requires real operator data")
    if operator_smarts_review_manifest is not None and (
        operator_smarts_review_manifest.is_symlink()
        or not operator_smarts_review_manifest.is_file()
    ):
        raise ValueError("configured original SMARTS manifest must be a regular file")
    if operator_arcgis_proof_bundle is not None and (
        parity or snapshot.get("demo") or directory is None
    ):
        raise ValueError("retained ArcGIS proof cannot be used in demo/parity mode")
    if operator_ceqanet_csv_evidence is not None and (
        parity or snapshot.get("demo") or directory is None or operator_database is None
    ):
        raise ValueError("original CSV evidence requires real operator data and database")
    if operator_ceqanet_csv_evidence is not None and (
        operator_ceqanet_csv_evidence.is_symlink()
        or not operator_ceqanet_csv_evidence.is_file()
    ):
        raise ValueError("configured original CSV evidence must be an existing regular file")
    if operator_ceqanet_csv_access_policy is not None and (
        operator_ceqanet_csv_evidence is None
        or operator_database is None
        or parity
        or snapshot.get("demo")
        or directory is None
    ):
        raise ValueError(
            "original CEQAnet access policy requires retained CSV evidence and real data"
        )
    if operator_ceqanet_csv_access_policy is not None and (
        operator_ceqanet_csv_access_policy.is_symlink()
        or not operator_ceqanet_csv_access_policy.is_file()
    ):
        raise ValueError("original CEQAnet access policy must be an existing regular file")
    if operator_ceqanet_csv_series_manifest is not None and (
        operator_ceqanet_csv_access_policy is None
        or operator_ceqanet_csv_evidence is None
        or operator_database is None
        or parity
        or snapshot.get("demo")
        or directory is None
    ):
        raise ValueError(
            "original CEQAnet series requires original policy, retained CSV and real data"
        )
    if operator_ceqanet_csv_series_manifest is not None and (
        operator_ceqanet_csv_series_manifest.is_symlink()
        or not operator_ceqanet_csv_series_manifest.is_file()
    ):
        raise ValueError("original CEQAnet series manifest must be an existing regular file")
    if any(x is not None for x in (
        operator_ceqanet_recurring_checklist,
        operator_ceqanet_recurring_definition,
        operator_ceqanet_recurring_manifest,
    )):
        if (
            parity or snapshot.get("demo") or directory is None
            or operator_database is None
            or any(x is None for x in (
                operator_ceqanet_recurring_checklist,
                operator_ceqanet_recurring_definition,
                operator_ceqanet_recurring_manifest,
            ))
        ):
            raise ValueError(
                "original CEQAnet recurring review requires all exact retained "
                "inputs and a real operator database"
            )
        for input_path in (
            operator_ceqanet_recurring_checklist,
            operator_ceqanet_recurring_definition,
            operator_ceqanet_recurring_manifest,
        ):
            if input_path is None or input_path.is_symlink() or not input_path.is_file():
                raise ValueError(
                    "original recurring inputs must be existing regular files"
                )
    if (operator_ceqanet_listing is None) != (operator_ceqanet_review_queue is None):
        raise ValueError("CEQAnet retained listing and review-queue evidence must be paired")
    if operator_database is None and any(
        path is not None for path in (
            operator_capture_queue, operator_ceqanet_listing,
            operator_ceqanet_review_queue, operator_smarts_journal,
            operator_smarts_history, operator_ceqanet_chain_report,
            operator_source_attribution_aliases,
        )
    ):
        raise ValueError("retained source artifacts require an existing operator database")
    source_aliases = (
        load_source_attribution_aliases(operator_source_attribution_aliases)
        if operator_source_attribution_aliases is not None else None
    )
    startup_directory = startup_directory or directory
    if directory:
        directory = data_folder.resolve_folder(directory)
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        state.initialize(directory)
        commercial.initialize(directory)
        if not (directory / "map.json").exists():
            (directory / "map.json").write_text(
                json.dumps(
                    {"offline_first": True, "url_template": None, "attribution": None}, indent=2
                )
            )
        if not (directory / "weights.json").exists():
            shutil.copyfile(WEIGHTS_PATH, directory / "weights.json")

    def current() -> dict[str, Any]:
        active = directory / "active.json" if directory else None
        current_snapshot = (
            json.loads(active.read_text()) if active and active.exists() else snapshot
        )
        return projection(current_snapshot, directory, parity=parity)

    restore_previews: dict[str, tuple[tempfile.TemporaryDirectory[str], dict[str, Any]]] = {}
    maintenance = threading.RLock()

    capture_status: dict[str, Any] = {"running": False, "message": "Idle"}
    capture_mutex = threading.Lock()

    def capture() -> dict[str, Any]:
        assert directory is not None
        if not state.settings(directory)["source_enabled"]:
            raise ValueError("SMARTS is disabled")
        if not capture_mutex.acquire(blocking=False):
            raise ValueError("Capture is already running")
        capture_status.update(running=True, message="Fetching official SMARTS Active rows")

        capture_directory = directory

        def worker() -> None:
            run_id = None
            try:
                with capture_lock(capture_directory):
                    run_id = begin_run(capture_directory)
                    with httpx.Client(timeout=60, headers={"User-Agent": USER_AGENT}) as client:
                        captured = collect_active(client, capture_directory)
                    finish_run(capture_directory, run_id, captured)
                    capture_status["message"] = f"Captured {len(captured['rows'])} rows"
            except (ValueError, OSError, httpx.HTTPError) as exc:
                if run_id is not None:
                    finish_run(capture_directory, run_id, None, f"{type(exc).__name__}: {exc}")
                capture_status["message"] = str(exc)
            finally:
                capture_status["running"] = False
                capture_mutex.release()

        threading.Thread(target=worker, daemon=True).start()
        return dict(capture_status)

    class Handler(BaseHTTPRequestHandler):
        def send_error(
            self, code: int, message: str | None = None, explain: str | None = None,
        ) -> None:
            # Validation messages may contain newlines or user-entered Unicode;
            # an HTTP reason phrase must never carry control characters.
            if message is not None:
                message = " ".join(
                    "".join(c if 32 <= ord(c) <= 126 else " " for c in message).split()
                )[:2000]
            super().send_error(code, message, explain)

        def do_GET(self) -> None:
            try:
                self.get_response()
            except (ValueError, OSError) as exc:
                self.send_error(409, str(exc))

        def get_response(self) -> None:
            port = cast(ThreadingHTTPServer, self.server).server_port
            if self.headers.get("Host") not in (f"127.0.0.1:{port}", f"localhost:{port}"):
                self.send_error(403)
                return
            path = urlsplit(self.path).path
            query = parse_qs(urlsplit(self.path).query)
            value: Any
            if path == "/api/source-ceqanet-artifact-download":
                if (
                    directory is None or set(query) != {"sha256", "artifact"}
                    or len(query["sha256"]) != 1
                    or len(query["artifact"]) != 1
                ):
                    raise ValueError("select one exact verified original operator artifact")
                artifact = query["artifact"][0]
                artifact_bytes = original_ceqanet_artifact_bytes(
                    directory, expected_report_sha256=query["sha256"][0],
                    artifact=artifact,
                )
                self.send_response(200)
                self.send_header(
                    "Content-Type",
                    "text/markdown; charset=utf-8" if artifact.endswith(".md")
                    else "application/json",
                )
                self.send_header(
                    "Content-Disposition", f"attachment; filename={artifact}"
                )
                self.send_header("Content-Length", str(len(artifact_bytes)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                self.wfile.write(artifact_bytes)
                return
            if path == "/api/source-ceqanet-report-download":
                if (
                    directory is None or set(query) != {"sha256"}
                    or len(query["sha256"]) != 1
                ):
                    raise ValueError("select one verified original Markdown report")
                report_bytes = original_ceqanet_report_bytes(
                    directory, expected_report_sha256=query["sha256"][0],
                )
                self.send_response(200)
                self.send_header("Content-Type", "text/markdown; charset=utf-8")
                self.send_header(
                    "Content-Disposition", "attachment; filename=ceqanet-operator-report.md"
                )
                self.send_header("Content-Length", str(len(report_bytes)))
                self.send_header("Cache-Control", "no-store")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                self.wfile.write(report_bytes)
                return
            if path == "/api/source-ceqanet-export-download":
                if (
                    directory is None or set(query) != {"sha256"}
                    or len(query["sha256"]) != 1
                ):
                    raise ValueError("select one verified original report export")
                archive_path = original_ceqanet_archive_path(
                    directory, expected_report_sha256=query["sha256"][0]
                )
                with open_runtime_artifact(archive_path) as archive_stream:
                    size = archive_stream.seek(0, 2)
                    if not 0 < size <= 128 * 1024 * 1024:
                        raise ValueError("original export exceeds approved ZIP limit")
                    archive_stream.seek(0)
                    self.send_response(200)
                    self.send_header("Content-Type", "application/zip")
                    self.send_header(
                        "Content-Disposition", "attachment; filename=ceqanet-operator-export.zip"
                    )
                    self.send_header("Content-Length", str(size))
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("X-Content-Type-Options", "nosniff")
                    self.end_headers()
                    while chunk := archive_stream.read(65536):
                        self.wfile.write(chunk)
                return
            if path == "/api/parcel-source-readiness":
                if urlsplit(self.path).query or urlsplit(self.path).fragment:
                    raise ValueError("parcel source readiness accepts no query parameters")
                value = parcel_source_readiness_snapshot()
                body, mime = json.dumps(value, allow_nan=False).encode(), "application/json"
            elif path == "/api/parcel-arcgis-proof":
                if urlsplit(self.path).query or urlsplit(self.path).fragment:
                    raise ValueError("retained ArcGIS proof inspection takes no query")
                value = retained_arcgis_proof_preview(operator_arcgis_proof_bundle)
                body, mime = json.dumps(value, allow_nan=False).encode(), "application/json"
            elif directory and path == "/api/native-parcel-proofs":
                if urlsplit(self.path).query or urlsplit(self.path).fragment:
                    raise ValueError("native ArcGIS proof inventory takes no query")
                value = native_arcgis_proof_inventory(directory)
                body, mime = json.dumps(value, allow_nan=False).encode(), "application/json"
            elif path == "/api/source-ceqanet-export-status":
                if urlsplit(self.path).query:
                    raise ValueError("original export status rejects query parameters")
                value = original_ceqanet_export_status(operator_ceqanet_chain_report)
                body, mime = json.dumps(value, allow_nan=False).encode(), "application/json"
            elif directory and path == "/api/settings":
                body, mime = json.dumps(state.settings(directory)).encode(), "application/json"
            elif directory and path == "/api/investigation-watches":
                if urlsplit(self.path).query:
                    raise ValueError("canonical watch list accepts no query parameters")
                value = investigation_watch.watchlist(directory)
                body, mime = json.dumps(value, allow_nan=False).encode(), "application/json"
            elif directory and path == "/api/investigation-watch":
                if set(query) != {"investigation_id"} or len(query["investigation_id"]) != 1:
                    raise ValueError("one exact watched investigation selection required")
                value = investigation_watch.inspect(directory, query["investigation_id"][0])
                body, mime = json.dumps(value, allow_nan=False).encode(), "application/json"
            elif directory and path == "/api/notifications":
                try:
                    source_notices = retained_watch_notifications(operator_database)
                except (ValueError, OSError, RuntimeError):
                    source_notices = [{
                        "id": "source-watch:unavailable",
                        "message": "Retained source watches are unavailable; "
                        "open Sources & Collection to review the configured source store.",
                    }]
                source_notices += investigation_watch.notifications(directory)
                body, mime = (
                    json.dumps(state.notifications(
                        directory, current()["rows"], source_notices=source_notices,
                    )).encode(),
                    "application/json",
                )
            elif directory and path.startswith("/api/offline-map/"):
                parts = path.removesuffix(".png").split("/")
                if len(parts) != 6 or not (directory / "basemap.pmtiles").exists():
                    self.send_error(404)
                    return
                tile = offline_map.tile(
                    directory / "basemap.pmtiles", int(parts[3]), int(parts[4]), int(parts[5])
                )
                if tile is None:
                    self.send_error(404, "Outside local map coverage")
                    return
                body, mime = tile, "image/png"
            elif path == "/api/capture":
                body, mime = json.dumps(capture_status).encode(), "application/json"
            elif path == "/api/contact-coverage":
                body, mime = (
                    json.dumps(contact_coverage(current()["rows"])).encode(),
                    "application/json",
                )
            elif path == "/api/call-list.csv":
                body, mime = call_list_csv(current()["rows"]), "text/csv; charset=utf-8"
            elif path == "/api/quality":
                body, mime = (
                    json.dumps(quality_report(current()["rows"])).encode(),
                    "application/json",
                )
            elif directory and path.startswith("/api/photo/"):
                with connect(directory) as db:
                    photo = db.execute(
                        "SELECT data,mime FROM cc_photos WHERE key=?", (unquote(path[11:]),)
                    ).fetchone()
                if photo is None:
                    self.send_error(404)
                    return
                body, mime = photo["data"], photo["mime"]
            elif directory and path == "/api/backup.zip":
                with maintenance, capture_lock(directory):
                    body, mime = state.backup(directory), "application/zip"
            elif directory and path in (
                "/api/bids",
                "/api/price-book",
                "/api/scope-template",
                "/api/royalties",
                "/api/scopes",
            ):
                value = (
                    commercial.bids(directory)
                    if path == "/api/bids"
                    else commercial.prices(directory)
                    if path == "/api/price-book"
                    else commercial.ledger(directory)
                    if path == "/api/royalties"
                    else commercial_catalog.scopes(directory)
                )
                body, mime = json.dumps(value).encode(), "application/json"
            elif directory and path == "/api/catalog":
                body = json.dumps(
                    {
                        "scopes": commercial_catalog.current(directory, "scope"),
                        "prices": commercial_catalog.current(directory, "price"),
                        "scope_history": commercial_catalog.history(directory, "scope"),
                        "price_history": commercial_catalog.history(directory, "price"),
                    }
                ).encode()
                mime = "application/json"
            elif directory and path.startswith("/api/bid-history/"):
                body, mime = (
                    json.dumps(commercial.bids(directory, unquote(path[17:]))).encode(),
                    "application/json",
                )
            elif directory and path.startswith("/api/proposal/"):
                versions = commercial.bids(directory, unquote(path[14:]))
                bid = next(
                    (
                        b
                        for b in versions
                        if str(b["version"])
                        == query.get("version", [str(versions[0]["version"]) if versions else ""])[
                            0
                        ]
                    ),
                    None,
                )
                if not bid:
                    self.send_error(404)
                    return
                body, mime = (
                    commercial.proposal_pdf(bid, state.settings(directory)["profile"]["company"]),
                    "application/pdf",
                )
            elif directory and path == "/api/royalties.csv":
                stream = io.StringIO(newline="")
                writer = csv.writer(stream)
                fields = (
                    "partner",
                    "contract_minor",
                    "calculated_minor",
                    "invoiced_minor",
                    "received_minor",
                    "receivable_minor",
                    "credit_minor",
                )
                writer.writerow(fields)
                for item in commercial.ledger(directory):
                    writer.writerow(
                        [
                            (
                                "'" + str(item[k])
                                if str(item[k]).lstrip().startswith(("=", "+", "-", "@"))
                                else item[k]
                            )
                            for k in fields
                        ]
                    )
                body, mime = stream.getvalue().encode("utf-8-sig"), "text/csv; charset=utf-8"
            elif path.startswith(("/api/lead/", "/api/evidence/")):
                key = unquote(path.split("/", 3)[3])
                lead = next((r for r in current()["rows"] if r["source_key"] == key), None)
                if lead is None:
                    self.send_error(404)
                    return
                value = (
                    state.evidence(directory, lead, verify=query.get("verify") == ["1"])
                    if directory and path.startswith("/api/evidence/")
                    else {
                        **lead,
                        "activity": state.activity(directory, key) if directory else [],
                        "bids": [b for b in commercial.bids(directory) if b["source_key"] == key]
                        if directory
                        else [],
                        "royalties": [
                            r for r in commercial.ledger(directory) if r["source_key"] == key
                        ]
                        if directory
                        else [],
                    }
                )
                body, mime = json.dumps(value).encode(), "application/json"
            elif path in {
                "/api/investigation-graph",
                "/api/investigation-graph/events",
                "/api/investigation-graph/evidence",
                "/api/investigation-graph/history",
                "/api/investigation-graph/history-index",
            }:
                if directory is None:
                    self.send_error(404, "Local investigation data folder is unavailable")
                    return
                if any(len(values) != 1 for values in query.values()):
                    raise ValueError("one value permitted per graph parameter")
                mode = (
                    "events"
                    if path.endswith("/events")
                    else "evidence"
                    if path.endswith("/evidence")
                    else "history"
                    if path.endswith("/history")
                    else "history_index"
                    if path.endswith("/history-index")
                    else "snapshot"
                )
                value = graph_view(
                    directory,
                    mode=mode,
                    root=query.get("root", [None])[0],
                    depth=int(query.get("depth", ["1"])[0]),
                    after=int(query.get("after", ["0"])[0]),
                    anchor=query.get("anchor", [None])[0],
                    evidence_id=query.get("id", [None])[0],
                )
                body, mime = json.dumps(value, allow_nan=False).encode(), "application/json"
            elif path == "/api/original-workflow-attribution":
                if (
                    directory is None
                    or set(query) != {"workflow", "kind", "record_id"}
                    or len(query["workflow"]) != 1
                    or len(query["kind"]) != 1
                    or len(query["record_id"]) != 1
                    or query["kind"][0] not in {"ceqa", "permit"}
                ):
                    raise ValueError("select one exact original workflow and source record")
                value = original_workflow_source_attribution(
                    directory, operator_database,
                    workflow_id=query["workflow"][0],
                    kind="ceqa" if query["kind"][0] == "ceqa" else "permit",
                    record_id=query["record_id"][0],
                )
                body, mime = json.dumps(value, allow_nan=False).encode(), "application/json"
            elif path == "/api/source-commercial-lineage":
                if (
                    directory is None
                    or set(query) - {"kind", "record_id", "offset", "limit"}
                    or len(query.get("kind", [])) != 1
                    or len(query.get("record_id", [])) != 1
                    or len(query.get("offset", ["0"])) != 1
                    or len(query.get("limit", ["20"])) != 1
                    or query["kind"][0] not in {"ceqa", "permit"}
                ):
                    raise ValueError("select one exact original source candidate")
                value = original_candidate_workflow_lineage(
                    directory, operator_database,
                    kind="ceqa" if query["kind"][0] == "ceqa" else "permit",
                    record_id=query["record_id"][0],
                    offset=int(query.get("offset", ["0"])[0]),
                    limit=int(query.get("limit", ["20"])[0]),
                )
                body, mime = json.dumps(value, allow_nan=False).encode(), "application/json"
            elif path == "/api/source-reconciliation-audit":
                if (
                    directory is None or set(query) != {"job"}
                    or len(query["job"]) != 1
                ):
                    raise ValueError("select one existing original replay job")
                value = original_source_replay_audit(
                    directory, job_id=query["job"][0]
                )
                body, mime = json.dumps(value, allow_nan=False).encode(), "application/json"
            elif path == "/api/source-reconciliation-scope":
                from constructionsight.operator_web import _parameters

                params = _parameters(urlsplit(self.path).query, source_review_queue=True)
                if directory is None:
                    raise ValueError("select an existing native data directory")
                value = preview_legacy_reconciliation_batch(directory, operator_database, {
                    "kind": params.kind, "county": params.county, "query": params.query,
                    "offset": params.offset, "limit": params.limit,
                })
                body, mime = json.dumps(value, allow_nan=False).encode(), "application/json"
            elif path == "/api/source-parcel-reconciliation":
                if (
                    directory is None
                    or set(query) != {"parcel_record_id"}
                    or len(query["parcel_record_id"]) != 1
                ):
                    raise ValueError("exact original parcel selection required")
                value = preview_original_parcel_reconciliation(
                    directory, operator_database, query["parcel_record_id"][0],
                )
                body, mime = json.dumps(value, allow_nan=False).encode(), "application/json"
            elif path == "/api/source-reconciliation":
                from constructionsight.operator_web import _parameters

                params = _parameters(urlsplit(self.path).query, candidate=True)
                if directory is None or params.record_id is None:
                    raise ValueError("select an exact original CEQA or permit source")
                if params.kind == "all":
                    raise ValueError("select a single CEQA or permit family")
                value = preview_legacy_reconciliation(
                    directory, operator_database, kind=params.kind,
                    record_id=params.record_id,
                )
                body, mime = json.dumps(value, allow_nan=False).encode(), "application/json"
            elif path == "/api/source-smarts-roster-audit":
                if urlsplit(self.path).query or urlsplit(self.path).fragment:
                    raise ValueError("original SMARTS roster audit takes no URL parameters")
                result = original_retained_smarts_roster_audit(
                    operator_smarts_collection_roster,
                    operator_smarts_journal,
                )
                body, mime = json.dumps(result, allow_nan=False).encode(), "application/json"
            elif path == "/api/source-ceqanet-recurring-audit":
                if urlsplit(self.path).query or urlsplit(self.path).fragment:
                    raise ValueError("original recurring audit takes no URL parameters")
                result = original_retained_ceqanet_recurring_audit(
                    operator_database,
                    operator_ceqanet_recurring_checklist,
                    operator_ceqanet_recurring_definition,
                    operator_ceqanet_recurring_manifest,
                )
                body, mime = json.dumps(result, allow_nan=False).encode(), "application/json"
            elif path == "/api/source-ceqanet-series-audit":
                if urlsplit(self.path).query or urlsplit(self.path).fragment:
                    raise ValueError("original CSV series audit takes no URL parameters")
                result = original_retained_ceqanet_series_audit(
                    operator_database,
                    operator_ceqanet_csv_evidence,
                    operator_ceqanet_csv_access_policy,
                    operator_ceqanet_csv_series_manifest,
                )
                body, mime = json.dumps(result, allow_nan=False).encode(), "application/json"
            elif path == "/api/source-ceqanet-policy-audit":
                if urlsplit(self.path).query or urlsplit(self.path).fragment:
                    raise ValueError("original CSV policy audit takes no URL parameters")
                result = original_retained_ceqanet_policy_audit(
                    operator_database,
                    operator_ceqanet_csv_evidence,
                    operator_ceqanet_csv_access_policy,
                )
                body, mime = json.dumps(result, allow_nan=False).encode(), "application/json"
            elif path == "/api/source-ceqanet-maturity-audit":
                if urlsplit(self.path).query or urlsplit(self.path).fragment:
                    raise ValueError("original CSV maturity audit takes no URL parameters")
                result = original_retained_ceqanet_maturity(
                    operator_database, operator_ceqanet_csv_evidence,
                )
                body, mime = json.dumps(result, allow_nan=False).encode(), "application/json"
            elif path == "/api/source-ceqanet-retained-import":
                if urlsplit(self.path).query or urlsplit(self.path).fragment:
                    raise ValueError("original retained CSV review takes no URL parameters")
                result = preview_retained_ceqanet_import(
                    operator_database,
                    operator_ceqanet_csv_evidence,
                    operator_ceqanet_listing,
                    operator_ceqanet_review_queue,
                )
                body, mime = json.dumps(result, allow_nan=False).encode(), "application/json"
            elif path == "/api/source-ceqanet-discovery-preview":
                if urlsplit(self.path).query or urlsplit(self.path).fragment:
                    raise ValueError("offline CEQAnet discovery preview takes no parameters")
                value = preview_original_ceqanet_discovery()
                body, mime = json.dumps(value, allow_nan=False).encode(), "application/json"
            elif path == "/api/source-checklist-preview":
                if (
                    set(query) != {"source_name", "public_url"}
                    or len(query["source_name"]) != 1
                    or len(query["public_url"]) != 1
                ):
                    raise ValueError("select one exact original source for manual review")
                value = preview_original_manual_checklist(
                    operator_database,
                    source_name=query["source_name"][0],
                    public_url=query["public_url"][0],
                )
                body, mime = json.dumps(value, allow_nan=False).encode(), "application/json"
            elif path == "/api/source-http-check-preview":
                if (
                    set(query) != {"source_name", "public_url"}
                    or len(query["source_name"]) != 1
                    or len(query["public_url"]) != 1
                ):
                    raise ValueError("select one exact original public source")
                value = preview_exact_original_source_readiness(
                    operator_database,
                    source_name=query["source_name"][0],
                    public_url=query["public_url"][0],
                )
                body, mime = json.dumps(value, allow_nan=False).encode(), "application/json"
            elif path == "/api/source-smarts-original-source-review":
                if set(query) != {"county"} or len(query["county"]) != 1:
                    raise ValueError("select one exact county for original SMARTS review")
                value = native_original_smarts_source_review(
                    manifest=operator_smarts_review_manifest, county=query["county"][0],
                )
                body, mime = json.dumps(value, allow_nan=False).encode(), "application/json"
            elif path == "/api/source-review-docket":
                if (
                    set(query) != {"kind", "record_id"}
                    or any(len(query[key]) != 1 for key in query)
                    or urlsplit(self.path).fragment
                ):
                    raise ValueError("select exact original docket source family and record")
                value = preview_original_source_docket(
                    operator_database,
                    kind=query["kind"][0], record_id=query["record_id"][0],
                )
                body, mime = json.dumps(value, allow_nan=False).encode(), "application/json"
            elif path == "/api/source-external-intelligence":
                if query or urlsplit(self.path).fragment:
                    raise ValueError("original external intelligence is exact read-only")
                value = original_external_source_intelligence()
                body, mime = json.dumps(value, allow_nan=False).encode(), "application/json"
            elif path in SOURCE_INSPECTION_ROUTES:
                value = source_inspection(
                    operator_database, route=path, query=urlsplit(self.path).query,
                    capture_queue=operator_capture_queue,
                    ceqanet_listing=operator_ceqanet_listing,
                    ceqanet_review_queue=operator_ceqanet_review_queue,
                    smarts_journal=operator_smarts_journal,
                    smarts_history=operator_smarts_history,
                    source_aliases=source_aliases,
                )
                body, mime = json.dumps(value, allow_nan=False).encode(), "application/json"
            elif path == "/api/investigation-lead-workflows":
                if directory is None or set(query) - {"limit", "offset"} or any(
                    len(values) != 1 or not values[0].isdigit()
                    for values in query.values()
                ):
                    raise ValueError("invalid canonical lead workflow page")
                value = retained_canonical_lead_workflows(
                    directory,
                    limit=int(query["limit"][0]) if "limit" in query else 25,
                    offset=int(query["offset"][0]) if "offset" in query else 0,
                )
                body, mime = json.dumps(value, allow_nan=False).encode(), "application/json"
            elif path == "/api/investigation-lead-history":
                if (
                    directory is None
                    or set(query) != {"investigation_id", "workflow_id"}
                    or any(len(query[key]) != 1 for key in query)
                ):
                    raise ValueError("select exact canonical investigation and workflow history")
                value = retained_canonical_lead_transition_history(
                    directory,
                    investigation_id=query["investigation_id"][0],
                    workflow_id=query["workflow_id"][0],
                )
                body, mime = json.dumps(value, allow_nan=False).encode(), "application/json"
            elif path == "/api/investigation-lead-preview":
                if (
                    directory is None or set(query) != {"investigation_id"}
                    or len(query["investigation_id"]) != 1
                ):
                    raise ValueError("select one canonical investigation for lead review")
                value = canonical_lead_preview(
                    directory, query["investigation_id"][0],
                    original_database=operator_database,
                )
                body, mime = json.dumps(value, allow_nan=False).encode(), "application/json"
            elif path == "/api/investigation-review":
                choices = query.get("relationship", [])
                if directory is None or set(query) != {"relationship"} or len(choices) != 1:
                    raise ValueError("provide one existing candidate relationship")
                value = investigation_review_preview(directory, choices[0])
                body, mime = json.dumps(value, allow_nan=False).encode(), "application/json"
            elif path == "/api/investigations" or path.startswith("/api/investigations/"):
                if directory is None:
                    self.send_error(404, "Local investigation data folder is unavailable")
                    return
                cursor_values = query.get("after", [])
                if len(cursor_values) > 1:
                    raise ValueError("one inventory cursor permitted")
                filter_names = {
                    "q": "text",
                    "county": "county",
                    "city": "city",
                    "source": "source_family",
                    "location": "location",
                }
                filters: dict[str, str] = {}
                for parameter, argument in filter_names.items():
                    values = query.get(parameter, [])
                    if len(values) > 1:
                        raise ValueError("one value permitted per investigation filter")
                    if values:
                        filters[argument] = values[0]
                revision_values = query.get("revision", [])
                if revision_values and revision_values != ["1"]:
                    raise ValueError("invalid investigation revision query")
                investigation_id = None
                if path != "/api/investigations":
                    investigation_id = unquote(path.removeprefix("/api/investigations/"))
                    if not investigation_id or "/" in investigation_id:
                        self.send_error(404)
                        return
                value = investigation_view(
                    directory,
                    investigation_id=investigation_id,
                    after=cursor_values[0] if cursor_values else None,
                    revision_only=bool(revision_values),
                    filters=filters,
                )
                body, mime = json.dumps(value, allow_nan=False).encode(), "application/json"
            elif path == "/api/leads":
                body, mime = json.dumps(current(), allow_nan=False).encode(), "application/json"
            elif path == "/api/outreach":
                if directory:
                    with connect(directory) as db:
                        db.execute(
                            "CREATE TABLE IF NOT EXISTS outreach_queue "
                            "(source_key TEXT PRIMARY KEY, added_at TEXT NOT NULL)"
                        )
                        queued = [dict(r) for r in db.execute("SELECT * FROM outreach_queue")]
                else:
                    queued = []
                body, mime = json.dumps(queued).encode(), "application/json"
            elif path == "/api/terms":
                conditions = [
                    {
                        "source": "California SMARTS",
                        "summary": (
                            "The publisher labels this dataset public with No Restrictions on "
                            "Public Use. The State's general conditions describe information as "
                            "generally public domain, except third-party copyrighted material. No "
                            "accuracy, completeness or suitability warranty is supplied. "
                            "Regulatory Active status is not proof of physical construction."
                        ),
                        "url": "https://publish.data.ca.gov/dataset/stormwater-regulatory-including-enforcement-actions-information-and-water-quality-results",
                        "conditions_url": "https://handbook.data.ca.gov/conditions-of-use/",
                    },
                    {
                        "source": "Fontana historical property records",
                        "summary": (
                            "The city links an address-search service for researching whether a "
                            "property has permits. Its website copyright notice reserves content "
                            "rights. The observed pages do not establish a bulk commercial "
                            "API-use license. This pilot retains bounded exact-address historical "
                            "candidates only; it does not verify current project scope or fill "
                            "missing dossier facts. Current Accela access returned HTTP 403; no "
                            "bypass is attempted."
                        ),
                        "url": "https://fontanaca.gov/3123/Historical-Property-Permit-Information",
                        "conditions_url": "https://fontanaca.gov/site/copyright",
                    },
                    {
                        "source": "Map setting",
                        "summary": (
                            "Offline-first is the default; no public tile host is embedded. To "
                            "use a provider you are authorized to use, set url_template and "
                            "attribution in the local map.json. A template must use HTTPS and "
                            "{z}, {x}, {y}. Provider licensing is separate from SMARTS and "
                            "city-record access."
                        ),
                        "url": None,
                        "conditions_url": None,
                    },
                ]
                conditions += json.loads((ASSETS / "contact_source_terms.json").read_text())
                body, mime = json.dumps(conditions).encode(), "application/json"
            elif path == "/api/runs":
                body, mime = (
                    json.dumps(run_history(directory) if directory else []).encode(),
                    "application/json",
                )
            elif path == "/api/watchlist":
                body, mime = (
                    json.dumps(
                        watchlist(directory, current()["rows"]) if directory else []
                    ).encode(),
                    "application/json",
                )
            elif path == "/api/developers":
                body, mime = (
                    json.dumps(developer_accounts(current()["rows"])).encode(),
                    "application/json",
                )
            elif directory and path == "/api/schedule":
                assert startup_directory is not None
                body = json.dumps(collection_schedule.status(directory, startup_directory)).encode()
                mime = "application/json"
            elif path == "/api/calibration":
                rows = current()["rows"]
                body = json.dumps(
                    {
                        "cohorts": calibration.report(rows),
                        "weights_digest": state.fingerprint(state.settings(directory)["weights"])
                        if directory
                        else None,
                        "changes": calibration.changes(directory) if directory else [],
                    }
                ).encode()
                mime = "application/json"
            elif path == "/api/outcomes":
                rows = current()["rows"]
                if directory:
                    present = {r["source_key"] for r in rows}
                    rows += [
                        {
                            "source_key": k,
                            "security_fit": v["score_at_update"],
                            "project_type": v["project_type_at_update"],
                            "feedback": v,
                        }
                        for k, v in get_feedback(directory).items()
                        if k not in present
                    ]
                body, mime = json.dumps(outcome_report(rows)).encode(), "application/json"
            elif path == "/api/export.csv":
                query = parse_qs(urlsplit(self.path).query)
                rows = current()["rows"]
                if query.get("new_today") == ["1"]:
                    rows = [r for r in rows if r["new_today"]]
                if query.get("new_since") == ["1"]:
                    rows = [r for r in rows if r["is_new"]]
                for parameter, field in (
                    ("county", "SITE_COUNTY"),
                    ("type", "project_type"),
                    ("band", "fit_band"),
                ):
                    if query.get(parameter):
                        rows = [r for r in rows if r.get(field) == query[parameter][0]]
                if query.get("search"):
                    term = query["search"][0].casefold()
                    rows = [
                        r
                        for r in rows
                        if term
                        in " ".join(
                            str(r.get(k) or "")
                            for k in ("SITE_NAME", "DEVELOPER_NAME", "SITE_CITY", "WDID", "APP_ID")
                        ).casefold()
                    ]
                if query.get("status"):
                    rows = [r for r in rows if r["feedback"]["status"] == query["status"][0]]
                body, mime = csv_export(rows), "text/csv; charset=utf-8"
            elif path == "/parity-photo.png" and parity:
                body = (Path(__file__).parents[2] / "tests/visual/parity-photo.png").read_bytes()
                mime = "image/png"
            elif path == "/" or (
                path.startswith("/")
                and ".." not in path
                and (ASSETS / path.lstrip("/")).is_file()
                and Path(path).suffix in (".css", ".js", ".png", ".json", ".woff2", ".svg")
                and Path(path).name not in ("demo.json",)
            ):
                asset = ASSETS / ("index.html" if path == "/" else path.lstrip("/"))
                body = asset.read_bytes()
                mime = {
                    ".html": "text/html",
                    ".css": "text/css",
                    ".js": "application/javascript",
                    ".png": "image/png",
                    ".svg": "image/svg+xml",
                    ".json": "application/json",
                    ".woff2": "font/woff2",
                }[asset.suffix]
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:
            with maintenance:
                self.local_post()

        def local_post(self) -> None:
            nonlocal directory, operator_ceqanet_csv_series_manifest
            path = urlsplit(self.path).path
            is_local = path in (
                "/api/settings",
                "/api/weights-reviewed",
                "/api/schedule",
                "/api/schedule-install",
                "/api/schedule-disable",
                "/api/notifications/read",
                "/api/capture",
                "/api/price-book",
                "/api/royalty-contract",
                "/api/scope-template",
                "/api/royalty-entry",
                "/api/investigation-review",
                "/api/investigation-lead-handoff",
                "/api/investigation-lead-review-transition",
                "/api/investigation-lead-result-review",
                "/api/source-watchlist-action",
                "/api/source-http-check",
                "/api/source-checklist-review",
                "/api/source-ceqanet-discovery",
                "/api/source-ceqanet-detail-preview",
                "/api/source-ceqanet-detail",
                "/api/source-smarts-catalog-preview",
                "/api/source-smarts-catalog",
                "/api/source-smarts-roster-preview",
                "/api/source-smarts-roster-collect",
                "/api/source-ceqanet-listing-preview",
                "/api/source-ceqanet-listing",
                "/api/source-ceqanet-csv-preview",
                "/api/source-ceqanet-csv",
                "/api/source-ceqanet-series-execution-preview",
                "/api/source-ceqanet-series-execution",
                "/api/source-ceqanet-series-append-preview",
                "/api/source-ceqanet-series-append",
                "/api/source-ceqanet-recurring-attempt-preview",
                "/api/source-ceqanet-recurring-attempt",
                "/api/source-ceqanet-retained-apply",
                "/api/source-review-docket-stage",
                "/api/source-registry-reviewed-apply",
                "/api/parcel-source-row-preview",
                "/api/parcel-arcgis-proof-persist",
                "/api/investigation-watch",
                "/api/source-commercial-preview",
                "/api/source-reconciliation-queue",
                "/api/source-reconciliation-scope-queue",
                "/api/source-parcel-reconciliation-queue",
                "/api/source-ceqanet-export",
                "/api/smarts-contacts-bulk",
                "/api/data-folder",
                "/api/restore-preview",
                "/api/offline-map-install",
                "/api/restore-apply",
            ) or path.startswith(
                (
                    "/api/facts/",
                    "/api/site-review/",
                    "/api/contacts/",
                    "/api/smarts-contacts/",
                    "/api/photo/",
                    "/api/control/",
                    "/api/activity/",
                    "/api/bids/",
                )
            )
            is_watch = path.startswith("/api/watchlist/")
            is_outreach = path.startswith("/api/outreach/")
            if not directory or not (
                is_local or is_watch or is_outreach or path.startswith("/api/feedback/")
            ):
                self.send_error(501)
                return
            host = self.headers.get("Host", "")
            port = cast(ThreadingHTTPServer, self.server).server_port
            if (
                host not in (f"127.0.0.1:{port}", f"localhost:{port}")
                or self.headers.get("Origin") != f"http://{host}"
            ):
                self.send_error(403)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if path == "/api/offline-map-install":
                    if not 0 < length <= 500_000_000:
                        raise ValueError("Invalid local map size")
                    with tempfile.TemporaryDirectory(
                        prefix="cs-map-install-", dir=directory
                    ) as temporary:
                        archive_path = Path(temporary) / "basemap.pmtiles"
                        with archive_path.open("wb") as out:
                            remaining = length
                            while remaining:
                                chunk = self.rfile.read(min(1_048_576, remaining))
                                if not chunk:
                                    raise ValueError("Incomplete map upload")
                                out.write(chunk)
                                remaining -= len(chunk)
                        expected = self.headers.get("X-Archive-SHA256")
                        actual = data_folder.digest(archive_path)
                        if expected != actual:
                            raise ValueError("Local map SHA-256 mismatch")
                        info = offline_map.metadata(archive_path)
                        if (
                            (
                                info.get("source_url") != offline_map.SOURCE
                                and not (
                                    snapshot.get("demo")
                                    and info.get("source_url") == "Demo fixture"
                                )
                            )
                            or info.get("attribution") != offline_map.ATTRIBUTION
                            or info.get("format") != "png"
                        ):
                            raise ValueError("Choose a locally built ConstructionSight OSM archive")
                        archive_path.chmod(0o600)
                        archive_path.replace(directory / "basemap.pmtiles")
                        body = json.dumps({"installed": True, "archive_sha256": actual}).encode()
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.send_header("Content-Length", str(len(body)))
                        self.end_headers()
                        self.wfile.write(body)
                        return
                if path == "/api/restore-preview":
                    if not 0 < length <= 5_000_000_000:
                        raise ValueError("Invalid backup upload size")
                    with maintenance:
                        for temp, _ in restore_previews.values():
                            temp.cleanup()
                        restore_previews.clear()
                        staged = tempfile.TemporaryDirectory(
                            prefix="cs-restore-", dir=directory.parent
                        )
                        try:
                            with tempfile.TemporaryDirectory(prefix="cs-upload-") as upload:
                                archive_path = Path(upload) / "backup.zip"
                                with archive_path.open("wb") as out:
                                    remaining = length
                                    while remaining:
                                        chunk = self.rfile.read(min(1_048_576, remaining))
                                        if not chunk:
                                            raise ValueError("Incomplete backup upload")
                                        out.write(chunk)
                                        remaining -= len(chunk)
                                report = data_folder.preview_restore(
                                    archive_path, Path(staged.name) / "data"
                                )
                            token = report["archive_sha256"]
                            restore_previews[token] = (staged, report)
                            body = json.dumps(
                                {k: v for k, v in report.items() if k != "files"}
                            ).encode()
                            self.send_response(200)
                            self.send_header("Content-Type", "application/json")
                            self.send_header("Content-Length", str(len(body)))
                            self.end_headers()
                            self.wfile.write(body)
                            return
                        except Exception:
                            staged.cleanup()
                            raise
                if not 0 < length <= (1_400_000 if path.startswith("/api/photo/") else 65536):
                    raise ValueError("Invalid feedback size")
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict):
                    raise ValueError("Feedback must be an object")
                if is_local:
                    if path in ("/api/data-folder", "/api/restore-apply"):
                        with maintenance, capture_mutex:
                            if capture_status["running"]:
                                raise ValueError(
                                    "Wait for collection to finish before changing folders"
                                )
                            with capture_lock(directory):
                                if path == "/api/data-folder":
                                    if set(payload) != {"directory"} or not isinstance(
                                        payload["directory"], str
                                    ):
                                        raise ValueError("Provide a destination folder")
                                    result = data_folder.relocate(
                                        directory, Path(payload["directory"])
                                    )
                                else:
                                    if (
                                        set(payload) != {"token"}
                                        or payload["token"] not in restore_previews
                                    ):
                                        raise ValueError("Preview this backup before applying it")
                                    staged, report = restore_previews.pop(payload["token"])
                                    try:
                                        result = data_folder.apply_restore(
                                            Path(staged.name) / "data",
                                            report,
                                            data_folder.new_restore_path(directory),
                                        )
                                    finally:
                                        staged.cleanup()
                                assert startup_directory is not None
                                target = Path(result["directory"])
                                data_folder.point_startup(startup_directory, target)
                                directory = target
                    elif path == "/api/investigation-lead-review-transition":
                        if (
                            urlsplit(self.path).query
                            or urlsplit(self.path).fragment
                            or self.headers.get_all("Host", []) != [host]
                            or self.headers.get_all("Origin", []) != [f"http://{host}"]
                            or self.headers.get("Sec-Fetch-Site") == "cross-site"
                        ):
                            raise ValueError("exact same-origin canonical workflow review required")
                        result = transition_retained_canonical_review(
                            directory, payload, original_database=operator_database,
                        )
                    elif path == "/api/investigation-lead-result-review":
                        if (
                            urlsplit(self.path).query
                            or urlsplit(self.path).fragment
                            or self.headers.get_all("Host", []) != [host]
                            or self.headers.get_all("Origin", []) != [f"http://{host}"]
                            or self.headers.get("Sec-Fetch-Site") == "cross-site"
                        ):
                            raise ValueError("exact same-origin canonical result review required")
                        result = apply_retained_canonical_result_review(
                            directory, payload, original_database=operator_database,
                        )
                    elif path == "/api/investigation-lead-handoff":
                        if (
                            urlsplit(self.path).query
                            or urlsplit(self.path).fragment
                            or self.headers.get_all("Host", []) != [host]
                            or self.headers.get_all("Origin", []) != [f"http://{host}"]
                            or self.headers.get("Sec-Fetch-Site") == "cross-site"
                        ):
                            raise ValueError("exact same-origin lead review handoff required")
                        result = retain_reviewed_canonical_candidate(
                            directory, payload, original_database=operator_database,
                        )
                    elif path == "/api/parcel-arcgis-proof-persist":
                        if (
                            urlsplit(self.path).query or urlsplit(self.path).fragment
                            or self.headers.get_all("Host", []) != [host]
                            or self.headers.get_all("Origin", []) != [f"http://{host}"]
                            or self.headers.get("Sec-Fetch-Site") == "cross-site"
                        ):
                            raise ValueError("exact same-origin offline proof approval required")
                        result = persist_reviewed_arcgis_proof(
                            directory, operator_arcgis_proof_bundle, payload,
                            original_database=operator_database,
                        )
                    elif path == "/api/parcel-source-row-preview":
                        if (
                            urlsplit(self.path).query
                            or urlsplit(self.path).fragment
                            or self.headers.get_all("Host", []) != [host]
                            or self.headers.get_all("Origin", []) != [f"http://{host}"]
                            or self.headers.get("Sec-Fetch-Site") == "cross-site"
                        ):
                            raise ValueError("exact same-origin parcel row review required")
                        result = preview_retained_parcel_sample(payload)
                    elif path == "/api/investigation-watch":
                        if (
                            urlsplit(self.path).query
                            or urlsplit(self.path).fragment
                            or set(payload) != {"action", "investigation_id", "expected_digest"}
                            or self.headers.get_all("Host", []) != [host]
                            or self.headers.get_all("Origin", []) != [f"http://{host}"]
                            or self.headers.get("Sec-Fetch-Site") == "cross-site"
                        ):
                            raise ValueError("exact same-origin canonical watch request required")
                        result = investigation_watch.action(directory, payload)
                    elif path in (
                        "/api/source-smarts-roster-preview",
                        "/api/source-smarts-roster-collect",
                    ):
                        if (
                            urlsplit(self.path).query
                            or urlsplit(self.path).fragment
                            or self.headers.get_all("Host", []) != [host]
                            or self.headers.get_all("Origin") != [f"http://{host}"]
                            or self.headers.get("Sec-Fetch-Site") == "cross-site"
                        ):
                            raise ValueError("exact same-origin SMARTS roster approval required")
                        original_roster_operation = (
                            preview_original_smarts_roster_collection
                            if path.endswith("-preview")
                            else execute_reviewed_original_smarts_roster_collection
                        )
                        result = original_roster_operation(
                            operator_smarts_collection_roster,
                            operator_smarts_journal,
                            operator_smarts_collection_checkpoint,
                            payload,
                        )
                    elif path in (
                        "/api/source-smarts-catalog-preview",
                        "/api/source-smarts-catalog",
                    ):
                        if (
                            urlsplit(self.path).query
                            or urlsplit(self.path).fragment
                            or self.headers.get_all("Host", []) != [host]
                            or self.headers.get_all("Origin", []) != [f"http://{host}"]
                            or self.headers.get("Sec-Fetch-Site") == "cross-site"
                        ):
                            raise ValueError("exact same-origin SMARTS catalog review required")
                        result = (
                            preview_original_smarts_catalog(payload)
                            if path.endswith("-preview")
                            else execute_reviewed_original_smarts_catalog(payload)
                        )
                    elif path in (
                        "/api/source-ceqanet-listing-preview",
                        "/api/source-ceqanet-listing",
                        "/api/source-ceqanet-csv-preview",
                        "/api/source-ceqanet-csv",
                        "/api/source-ceqanet-series-execution-preview",
                        "/api/source-ceqanet-series-execution",
                    ):
                        if (
                            urlsplit(self.path).query
                            or urlsplit(self.path).fragment
                            or self.headers.get_all("Host", []) != [host]
                            or self.headers.get_all("Origin", []) != [f"http://{host}"]
                            or self.headers.get("Sec-Fetch-Site") == "cross-site"
                        ):
                            raise ValueError("exact same-origin CEQAnet acquisition required")
                        operations = {
                            "/api/source-ceqanet-listing-preview": preview_original_ceqanet_listing,
                            "/api/source-ceqanet-listing": (
                                execute_reviewed_original_ceqanet_listing
                            ),
                            "/api/source-ceqanet-csv-preview": preview_original_ceqanet_csv,
                            "/api/source-ceqanet-csv": execute_reviewed_original_ceqanet_csv,
                        }
                        if path.startswith("/api/source-ceqanet-series-execution"):
                            operation = (
                                preview_original_ceqanet_series_request
                                if path.endswith("-preview")
                                else execute_reviewed_original_ceqanet_series_request
                            )
                            result = operation(
                                operator_database,
                                operator_ceqanet_csv_evidence,
                                operator_ceqanet_csv_access_policy,
                                operator_ceqanet_csv_series_manifest,
                                payload,
                            )
                        else:
                            result = operations[path](payload)
                    elif path in (
                        "/api/source-ceqanet-recurring-attempt-preview",
                        "/api/source-ceqanet-recurring-attempt",
                    ):
                        if (
                            urlsplit(self.path).query
                            or urlsplit(self.path).fragment
                            or self.headers.get_all("Host", []) != [host]
                            or self.headers.get_all("Origin") != [f"http://{host}"]
                            or self.headers.get("Sec-Fetch-Site") == "cross-site"
                        ):
                            raise ValueError(
                                "exact same-origin recurring-run review required"
                            )
                        recurring_operation = (
                            preview_original_ceqanet_recurring_attempt
                            if path.endswith("-preview")
                            else execute_reviewed_original_ceqanet_recurring_attempt
                        )
                        result = recurring_operation(
                            operator_database,
                            operator_ceqanet_recurring_checklist,
                            operator_ceqanet_recurring_definition,
                            operator_ceqanet_recurring_manifest,
                            payload,
                        )
                    elif path in (
                        "/api/source-ceqanet-series-append-preview",
                        "/api/source-ceqanet-series-append",
                    ):
                        if (
                            urlsplit(self.path).query
                            or urlsplit(self.path).fragment
                            or self.headers.get_all("Host", []) != [host]
                            or self.headers.get_all("Origin") != [f"http://{host}"]
                            or self.headers.get("Sec-Fetch-Site") == "cross-site"
                        ):
                            raise ValueError("exact same-origin CEQAnet ledger approval required")
                        append_operation = (
                            preview_original_ceqanet_series_append
                            if path.endswith("-preview")
                            else apply_reviewed_original_ceqanet_series_append
                        )
                        result = append_operation(
                            operator_database,
                            operator_ceqanet_csv_evidence,
                            operator_ceqanet_csv_access_policy,
                            operator_ceqanet_csv_series_manifest,
                            payload,
                        )
                        if path == "/api/source-ceqanet-series-append":
                            # Native reads now use the newly verified immutable
                            # manifest; the response also supplies restart option.
                            operator_ceqanet_csv_series_manifest = Path(
                                result["series_manifest_path"]
                            )
                    elif path in (
                        "/api/source-ceqanet-detail-preview",
                        "/api/source-ceqanet-detail",
                    ):
                        if (
                            urlsplit(self.path).query
                            or urlsplit(self.path).fragment
                            or self.headers.get_all("Host", []) != [host]
                            or self.headers.get_all("Origin", []) != [f"http://{host}"]
                            or self.headers.get("Sec-Fetch-Site") == "cross-site"
                        ):
                            raise ValueError("exact same-origin CEQAnet detail review required")
                        result = (
                            preview_original_ceqanet_detail(payload)
                            if path == "/api/source-ceqanet-detail-preview"
                            else execute_reviewed_original_ceqanet_detail(payload)
                        )
                    elif path == "/api/source-ceqanet-discovery":
                        if (
                            urlsplit(self.path).query
                            or urlsplit(self.path).fragment
                            or self.headers.get_all("Host", []) != [host]
                            or self.headers.get_all("Origin", []) != [f"http://{host}"]
                            or self.headers.get("Sec-Fetch-Site") == "cross-site"
                        ):
                            raise ValueError("exact same-origin CEQAnet discovery consent required")
                        result = execute_reviewed_original_ceqanet_discovery(payload)
                    elif path == "/api/source-checklist-review":
                        if (
                            urlsplit(self.path).query
                            or urlsplit(self.path).fragment
                            or self.headers.get_all("Host", []) != [host]
                            or self.headers.get_all("Origin", []) != [f"http://{host}"]
                            or self.headers.get("Sec-Fetch-Site") == "cross-site"
                        ):
                            raise ValueError("exact same-origin manual source checklist required")
                        result = review_original_manual_checklist(
                            operator_database, payload,
                        )
                    elif path == "/api/source-review-docket-stage":
                        if (
                            urlsplit(self.path).query
                            or urlsplit(self.path).fragment
                            or self.headers.get_all("Host", []) != [host]
                            or self.headers.get_all("Origin", []) != [f"http://{host}"]
                            or self.headers.get("Sec-Fetch-Site") == "cross-site"
                        ):
                            raise ValueError("exact same-origin original docket staging required")
                        result = stage_reviewed_original_source_docket(
                            operator_database, payload,
                        )
                    elif path == "/api/source-ceqanet-retained-apply":
                        if (
                            urlsplit(self.path).query
                            or urlsplit(self.path).fragment
                            or self.headers.get_all("Host", []) != [host]
                            or self.headers.get_all("Origin", []) != [f"http://{host}"]
                            or self.headers.get("Sec-Fetch-Site") == "cross-site"
                        ):
                            raise ValueError("exact same-origin retained CSV approval required")
                        result = apply_reviewed_retained_ceqanet_import(
                            operator_database,
                            operator_ceqanet_csv_evidence,
                            operator_ceqanet_listing,
                            operator_ceqanet_review_queue,
                            payload,
                        )
                    elif path == "/api/source-registry-reviewed-apply":
                        if (
                            urlsplit(self.path).query
                            or urlsplit(self.path).fragment
                            or self.headers.get_all("Host", []) != [host]
                            or self.headers.get_all("Origin", []) != [f"http://{host}"]
                            or self.headers.get("Sec-Fetch-Site") == "cross-site"
                        ):
                            raise ValueError("exact same-origin source registry approval required")
                        result = apply_reviewed_original_source_registry_update(
                            operator_database, payload,
                        )
                    elif path == "/api/source-http-check":
                        if (
                            urlsplit(self.path).query
                            or urlsplit(self.path).fragment
                            or self.headers.get_all("Host", []) != [host]
                            or self.headers.get_all("Origin", []) != [f"http://{host}"]
                            or self.headers.get("Sec-Fetch-Site") == "cross-site"
                        ):
                            raise ValueError("exact same-origin manual source HTTP check required")
                        result = check_reviewed_original_source_readiness(
                            operator_database, payload,
                        )
                    elif path == "/api/source-watchlist-action":
                        if (
                            urlsplit(self.path).query
                            or urlsplit(self.path).fragment
                            or set(payload) != {"action", "kind", "record_id"}
                            or not all(isinstance(v, str) for v in payload.values())
                            or self.headers.get_all("Host", []) != [host]
                            or self.headers.get_all("Origin", []) != [f"http://{host}"]
                            or self.headers.get("Sec-Fetch-Site") == "cross-site"
                        ):
                            raise ValueError("exact same-origin source watch request required")
                        result = source_watch_action(
                            operator_database, action=payload["action"],
                            kind=payload["kind"], record_id=payload["record_id"],
                        )
                    elif path == "/api/source-commercial-preview":
                        if (
                            urlsplit(self.path).query
                            or urlsplit(self.path).fragment
                            or set(payload) != {"operation", "data"}
                            or not isinstance(payload["operation"], str)
                            or not isinstance(payload["data"], dict)
                            or self.headers.get_all("Host", []) != [host]
                            or self.headers.get_all("Origin", []) != [f"http://{host}"]
                            or self.headers.get("Sec-Fetch-Site") == "cross-site"
                        ):
                            raise ValueError("exact same-origin original preview request required")
                        result = retained_commercial_preview(
                            operator_database, operation=payload["operation"],
                            data=payload["data"],
                        )
                    elif path == "/api/source-ceqanet-export":
                        if (
                            urlsplit(self.path).query
                            or urlsplit(self.path).fragment
                            or set(payload) != {"expected_report_sha256", "caller_confirmation"}
                            or not isinstance(payload["expected_report_sha256"], str)
                            or payload["caller_confirmation"] is not True
                            or self.headers.get_all("Host", []) != [host]
                            or self.headers.get_all("Origin", []) != [f"http://{host}"]
                            or self.headers.get("Sec-Fetch-Site") == "cross-site"
                        ):
                            raise ValueError("exact same-origin confirmed export required")
                        result = original_ceqanet_export(
                            directory, operator_ceqanet_chain_report,
                            expected_report_sha256=payload["expected_report_sha256"],
                            caller_confirmation=True,
                        )
                    elif path in (
                        "/api/source-reconciliation-queue",
                        "/api/source-reconciliation-scope-queue",
                        "/api/source-parcel-reconciliation-queue",
                    ):
                        if (
                            urlsplit(self.path).query
                            or urlsplit(self.path).fragment
                            or self.headers.get_all("Host", []) != [host]
                            or self.headers.get_all("Origin", []) != [f"http://{host}"]
                            or self.headers.get("Sec-Fetch-Site") == "cross-site"
                        ):
                            raise ValueError("exact same-origin source replay is required")
                        queue_source = (
                            enqueue_original_parcel_reconciliation
                            if path == "/api/source-parcel-reconciliation-queue"
                            else enqueue_legacy_reconciliation_batch
                            if path == "/api/source-reconciliation-scope-queue"
                            else enqueue_legacy_reconciliation
                        )
                        result = queue_source(directory, operator_database, payload)
                    elif path == "/api/investigation-review":
                        result = apply_investigation_review(directory, payload)
                    elif path == "/api/smarts-contacts-bulk":
                        if payload:
                            raise ValueError("Bulk contact import takes no options")
                        result = bulk_import(directory, current()["rows"])
                    elif path in (
                        "/api/schedule",
                        "/api/schedule-install",
                        "/api/schedule-disable",
                    ):
                        assert startup_directory is not None
                        if path == "/api/schedule":
                            collection_schedule.save(directory, payload)
                            result = collection_schedule.status(directory, startup_directory)
                        elif path == "/api/schedule-install":
                            result = collection_schedule.install(
                                directory, startup_directory, payload
                            )
                        else:
                            if payload:
                                raise ValueError("Disable takes no options")
                            result = collection_schedule.disable(directory, startup_directory)
                    elif path == "/api/weights-reviewed":
                        result = calibration.apply(directory, payload)
                    elif path == "/api/settings":
                        result = state.save_settings(directory, payload)
                    elif path == "/api/notifications/read":
                        result = state.mark_read(directory, payload)
                    elif path == "/api/capture":
                        if payload:
                            raise ValueError("Capture takes no options")
                        result = capture()
                    elif path == "/api/scope-template":
                        result = commercial_catalog.save_scope(directory, payload)
                    elif path == "/api/price-book":
                        result = commercial.save_price(directory, payload)
                    elif path == "/api/royalty-contract":
                        result = commercial.contract(directory, payload)
                    elif path == "/api/royalty-entry":
                        result = commercial.transaction(directory, payload)
                    else:
                        key = unquote(path.split("/", 3)[3])
                        lead = next((r for r in current()["rows"] if r["source_key"] == key), None)
                        if lead is None:
                            raise ValueError("Unknown lead")
                        family = path.split("/")[2]
                        if family == "facts":
                            result = state.save_facts(directory, key, payload)
                        elif family == "site-review":
                            result = state.review_site(directory, lead, payload)
                        elif family == "photo":
                            result = state.save_photo(directory, key, payload)
                        elif family == "smarts-contacts":
                            if payload:
                                raise ValueError("Contact import takes no options")
                            result = state.import_smarts_contacts(directory, lead)
                        elif family == "contacts":
                            result = state.save_contact(directory, key, payload)
                        elif family == "control":
                            result = state.control(directory, key, payload)
                        elif family == "bids":
                            result = commercial.save_bid(directory, lead, payload)
                        else:
                            if (
                                set(payload) != {"kind", "note"}
                                or payload["kind"]
                                not in ("called", "emailed", "replied", "voicemail", "note")
                                or not isinstance(payload["note"], str)
                                or len(payload["note"]) > 10000
                            ):
                                raise ValueError("Invalid activity")
                            state.event(directory, key, payload["kind"], {"note": payload["note"]})
                            result = {"saved": True}
                    body = json.dumps(result).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                prefix = (
                    "/api/watchlist/"
                    if is_watch
                    else "/api/outreach/"
                    if is_outreach
                    else "/api/feedback/"
                )
                key = unquote(path[len(prefix) :])
                lead = next((r for r in current()["rows"] if r["source_key"] == key), None)
                if lead is None and not is_watch:
                    raise ValueError("Unknown lead")
                if is_outreach:
                    if payload or lead is None:
                        raise ValueError("Invalid outreach queue request")
                    if lead.get("do_not_contact") or lead["feedback"]["status"] == "Not a fit":
                        raise ValueError("Do-Not-Contact or excluded lead")
                    result = state.queue(directory, lead)
                elif is_watch:
                    result = update_watch(directory, key, payload, lead)
                else:
                    assert lead is not None
                    result = save_feedback(directory, key, payload, lead)
                body = json.dumps(result).encode()
            except (ValueError, KeyError, OSError, sqlite3.Error, zipfile.BadZipFile) as exc:
                self.send_error(400, str(exc))
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt: str, *args: Any) -> None:
            pass

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path.home() / ".local/share/constructionsight/command-center",
    )
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--offline", action="store_true", help="Use the last complete real capture")
    parser.add_argument("--demo", action="store_true", help="Labeled fixture preview, no network")
    parser.add_argument("--mockup-parity", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument(
        "--operator-database",
        type=Path,
        help="Existing legacy operator SQLite database for read-only source inspection",
    )
    parser.add_argument(
        "--operator-source-attribution-aliases", type=Path,
        help="Existing validated original source-name attribution aliases, read-only",
    )
    parser.add_argument(
        "--operator-capture-queue", type=Path,
        help="Exact locally retained CEQA capture-queue artifact, read-only",
    )
    parser.add_argument(
        "--operator-ceqanet-listing", type=Path,
        help="Retained CEQAnet listing evidence for original ingestion inbox",
    )
    parser.add_argument(
        "--operator-ceqanet-review-queue", type=Path,
        help="Paired retained CEQAnet review evidence for original inbox",
    )
    parser.add_argument(
        "--operator-ceqanet-csv-evidence", type=Path,
        help="One exact retained CEQAnet CSV execution artifact for governed import review",
    )
    parser.add_argument(
        "--operator-ceqanet-csv-access-policy", type=Path,
        help="One existing CEQAnet CSV evidence policy JSON for read-only audit",
    )
    parser.add_argument(
        "--operator-ceqanet-csv-series-manifest", type=Path,
        help="Private retained CEQAnet series + execution refs, read-only audit",
    )
    parser.add_argument(
        "--operator-smarts-collection-checkpoint", type=Path,
        help="Explicit original SMARTS resumable checkpoint path; no startup writes",
    )
    parser.add_argument(
        "--operator-smarts-collection-roster", type=Path,
        help="Existing original 1–25 exact SMARTS facility roster for offline audit",
    )
    parser.add_argument(
        "--operator-ceqanet-recurring-checklist", type=Path,
        help="Exact original manual CEQAnet source checklist, offline recurring audit",
    )
    parser.add_argument(
        "--operator-ceqanet-recurring-definition", type=Path,
        help="Immutable original CEQAnet recurring-run definition, read-only",
    )
    parser.add_argument(
        "--operator-ceqanet-recurring-manifest", type=Path,
        help="Immutable original CEQAnet exact-window run manifest, read-only",
    )
    parser.add_argument(
        "--operator-arcgis-proof-bundle", type=Path,
        help="One retained, verified ArcGIS proof JSON; offline review only",
    )
    parser.add_argument(
        "--operator-ceqanet-chain-report", type=Path,
        help="Existing exact CEQAnet chain report for locally verified operator ZIP exports",
    )
    parser.add_argument(
        "--operator-smarts-journal", type=Path,
        help="Existing private SMARTS evidence journal for read-only original inspection",
    )
    parser.add_argument(
        "--operator-smarts-history", type=Path,
        help="Existing private SMARTS CSV snapshot history for original change/parcel review",
    )
    parser.add_argument(
        "--operator-smarts-review-manifest", type=Path,
        help="Private retained SMARTS facility/inspection/compliance CSV manifest, offline",
    )
    parser.add_argument(
        "--capture-only", action="store_true", help="Scheduled capture without a server"
    )
    parser.add_argument(
        "--fontana-source-key",
        help="Explicit bounded historical address research for one current SMARTS lead",
    )
    args = parser.parse_args(argv)
    startup_directory = args.data_dir
    try:
        args.data_dir = data_folder.resolve_folder(args.data_dir)
        if args.mockup_parity:
            if not args.demo or args.capture_only or args.fontana_source_key:
                raise ValueError("Mockup parity is an isolated visual test; requires --demo")
            snapshot = json.loads(
                (Path(__file__).parents[2] / "tests/visual/parity.json").read_text()
            )
        elif args.demo:
            snapshot = json.loads((ASSETS / "demo.json").read_text())
        elif args.offline:
            snapshot = json.loads((args.data_dir / "active.json").read_text())
        else:
            print("Fetching official SMARTS Active facilities for both counties…", flush=True)
            with capture_lock(args.data_dir):
                run_id = begin_run(args.data_dir)
                try:
                    with httpx.Client(timeout=60, headers={"User-Agent": USER_AGENT}) as client:
                        snapshot = collect_active(client, args.data_dir)
                    finish_run(args.data_dir, run_id, snapshot)
                    print(
                        f"Live capture: {snapshot['totals']}; {snapshot['requests']} requests; "
                        f"new records: {snapshot['new_count']}",
                        flush=True,
                    )
                except (ValueError, OSError, httpx.HTTPError) as exc:
                    finish_run(args.data_dir, run_id, None, f"{type(exc).__name__}: {exc}")
                    if args.capture_only or not (args.data_dir / "active.json").exists():
                        raise
                    snapshot = json.loads((args.data_dir / "active.json").read_text())
                    print(
                        "Capture failed; opening the last good capture with a warning.", flush=True
                    )
        if args.fontana_source_key:
            lead = next(
                (r for r in snapshot["rows"] if r["source_key"] == args.fontana_source_key), None
            )
            if lead is None:
                raise ValueError("Unknown SMARTS source key")
            with httpx.Client(timeout=30, headers={"User-Agent": USER_AGENT}) as client:
                candidates = fetch_candidates(client, lead)
            retain_candidates(args.data_dir, candidates)
            print(
                f"Fontana: {candidates['returned_records']} returned, "
                f"{len(candidates['candidates'])} exact historical address candidates; "
                "current project match unverified; no dossier facts filled."
            )
        if args.capture_only:
            return 0
        server = make_server(
            snapshot,
            args.port,
            None if args.demo else args.data_dir,
            parity=args.mockup_parity,
            startup_directory=startup_directory,
            operator_database=args.operator_database,
            operator_source_attribution_aliases=args.operator_source_attribution_aliases,
            operator_capture_queue=args.operator_capture_queue,
            operator_ceqanet_listing=args.operator_ceqanet_listing,
            operator_ceqanet_review_queue=args.operator_ceqanet_review_queue,
            operator_ceqanet_csv_evidence=args.operator_ceqanet_csv_evidence,
            operator_ceqanet_csv_access_policy=args.operator_ceqanet_csv_access_policy,
            operator_ceqanet_csv_series_manifest=args.operator_ceqanet_csv_series_manifest,
            operator_ceqanet_recurring_checklist=args.operator_ceqanet_recurring_checklist,
            operator_ceqanet_recurring_definition=args.operator_ceqanet_recurring_definition,
            operator_ceqanet_recurring_manifest=args.operator_ceqanet_recurring_manifest,
            operator_smarts_journal=args.operator_smarts_journal,
            operator_smarts_collection_roster=args.operator_smarts_collection_roster,
            operator_smarts_collection_checkpoint=args.operator_smarts_collection_checkpoint,
            operator_smarts_history=args.operator_smarts_history,
            operator_smarts_review_manifest=args.operator_smarts_review_manifest,
            operator_ceqanet_chain_report=args.operator_ceqanet_chain_report,
            operator_arcgis_proof_bundle=args.operator_arcgis_proof_bundle,
        )
    except (ValueError, OSError, httpx.HTTPError) as exc:
        print(f"Command Center unavailable: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    url = f"http://127.0.0.1:{server.server_port}"
    print(f"Command Center: {url}", flush=True)
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
