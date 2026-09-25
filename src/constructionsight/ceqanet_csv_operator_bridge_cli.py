"""Governed one-request CEQAnet capture, offline review and explicitly approved import.

Only capture-preview can make one separately authorized GET. Preview and apply
remain offline, and no command automatically approves or writes a source capture.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

import typer
from sqlalchemy.orm import Session

from constructionsight.authorization_decision import AuthorizationDeniedError
from constructionsight.ceqanet_capture_queue import build_reviewed_ceqanet_capture_queue
from constructionsight.ceqanet_csv_live_models import CeqanetCsvLiveExecution
from constructionsight.ceqanet_csv_models import canonical_digest
from constructionsight.ceqanet_csv_operator_bridge import (
    ReviewedCeqanetCsvBridge,
    build_reviewed_ceqanet_csv_bridge,
)
from constructionsight.ceqanet_csv_service import build_ceqanet_csv_export_request
from constructionsight.legal import SourceAccessProfile
from constructionsight.operator_services.ceqanet_csv_service import (
    execute_authorized_ceqanet_csv,
)
from constructionsight.operator_services.ceqanet_persistence_service import (
    execute_authorized_ceqanet_write_plan,
)
from constructionsight.storage.database import database_url_from_path
from constructionsight.storage.domain_store import CeqaStore
from constructionsight.storage.operator_read_store import create_operator_read_engine
from constructionsight.storage.runtime_artifacts import (
    read_runtime_artifact,
    read_runtime_text,
    write_runtime_text,
)

app = typer.Typer(help="Governed current CEQAnet capture, reviewed preview and separate import.")


@app.callback()
def main() -> None:
    """Run a reviewed, bounded CSV-to-operator database workflow."""


def _load_evidence(path: Path) -> ReviewedCeqanetCsvBridge:
    try:
        payload: Any = json.loads(read_runtime_text(path))
        if not isinstance(payload, dict):
            raise ValueError("source execution artifact must contain a JSON object")
        # Historical evidence-series envelopes retain the live execution nested.
        content = payload.get("live_execution", payload)
        if not isinstance(content, dict):
            raise ValueError("live execution must contain a JSON object")
        execution = CeqanetCsvLiveExecution.model_validate(content)
        return build_reviewed_ceqanet_csv_bridge(execution)
    except (OSError, ValueError, TypeError) as exc:
        raise typer.BadParameter(
            f"retained CEQAnet source evidence could not be independently replayed: {exc}"
        ) from exc


def _plan_digest(bridge: ReviewedCeqanetCsvBridge) -> str:
    return canonical_digest(bridge.write_plan.to_dict())


def _load_bound_capture_candidate(
    *, listing_evidence: Path, queue_evidence: Path, sch_number: str,
) -> dict[str, object]:
    """Re-derive a saved queue from its exact listing bytes and bind one SCH candidate."""

    if listing_evidence.absolute() == queue_evidence.absolute():
        raise typer.BadParameter("listing evidence and queue evidence must be distinct artifacts")
    try:
        listing_raw = read_runtime_artifact(listing_evidence, max_bytes=16 * 1024 * 1024)
        queue_raw = read_runtime_artifact(queue_evidence, max_bytes=16 * 1024 * 1024)
        listing_payload: Any = json.loads(listing_raw.decode("utf-8"))
        queue_payload: Any = json.loads(queue_raw.decode("utf-8"))
        if not isinstance(listing_payload, dict) or not isinstance(queue_payload, dict):
            raise ValueError("listing and queue evidence must each contain a JSON object")
        regenerated = build_reviewed_ceqanet_capture_queue(
            listing_payload, original_bytes=listing_raw,
        )
        if queue_payload != regenerated:
            raise ValueError(\n                "saved queue does not exactly match a fresh derivation from listing evidence"\n            )
        candidates = regenerated.get("candidates")
        if not isinstance(candidates, list):
            raise ValueError("saved queue candidates are malformed")
        matches = [
            item for item in candidates
            if isinstance(item, dict) and item.get("sch_number") == sch_number
        ]
        if len(matches) != 1:
            raise ValueError("exact SCH is not uniquely present in the reviewed capture queue")
        candidate = matches[0]
        if (
            candidate.get("candidate_only") is not True
            or candidate.get("review_state") != "unverified_source_claim"
            or candidate.get("network_executed_for_candidate") is not False
            or candidate.get("persistence_mutated") is not False
            or not isinstance(candidate.get("source_claimed_county"), str)
            or not isinstance(candidate.get("official_detail_url"), str)
        ):
            raise ValueError("reviewed queue candidate has an invalid or promoted state")
    except (OSError, ValueError, UnicodeDecodeError, TypeError) as exc:
        raise typer.BadParameter(
            f"capture queue could not be independently rebound to listing evidence: {exc}"
        ) from exc

    return {
        "schema_version": "ceqanet_listing_capture_binding.v1",
        "sch_number": sch_number,
        "listing_artifact_sha256": hashlib.sha256(listing_raw).hexdigest(),
        "queue_artifact_sha256": hashlib.sha256(queue_raw).hexdigest(),
        "listing_plan_id": regenerated.get("listing_plan_id"),
        "source_claimed_county": candidate["source_claimed_county"],
        "source_claimed_title": candidate.get("source_claimed_title"),
        "official_detail_url": candidate["official_detail_url"],
        "observation_pages": candidate.get("observation_pages"),
        "source_observation_count": candidate.get("source_observation_count"),
        "claim_state": "unverified_source_claim",
    }


def _summary(bridge: ReviewedCeqanetCsvBridge) -> dict[str, object]:
    return {
        "source_sha256": bridge.source_sha256,
        "source_execution_digest": bridge.source_execution_digest,
        "source_inspection_digest": bridge.source_inspection_digest,
        "approved_plan_digest_required": _plan_digest(bridge),
        "source_records": list(bridge.source_record_keys),
        "source_record_count": len(bridge.source_record_keys),
        "planned_write_count": bridge.write_plan.operation_count,
        "network_executed": False,
        "persistence_mutated": False,
        "qualified_leads_created": False,
        "read_only_operator_compatibility": "same existing SQLite domain store",
    }


@app.command("discover-preview")
def discover_preview(
    listing_evidence: Annotated[
        Path,
        typer.Option("--listing-evidence", exists=True, dir_okay=False, readable=True,
                     help="Retained complete governed CEQAnet listing-execution JSON."),
    ],
    output: Annotated[
        Path, typer.Option("--output", help="New path for the offline exact-SCH review queue."),
    ],
) -> None:
    """Derive exact-SCH manual capture candidates from existing listing evidence only."""

    if output.exists() or listing_evidence.absolute() == output.absolute():
        raise typer.BadParameter("review queue output must be new and distinct from listing evidence")
    try:
        raw = read_runtime_artifact(listing_evidence, max_bytes=16 * 1024 * 1024)
        payload: Any = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("listing evidence must be a JSON object")
        queue = build_reviewed_ceqanet_capture_queue(payload, original_bytes=raw)
        write_runtime_text(
            output, json.dumps(queue, sort_keys=True, indent=2) + "\n", overwrite=False,
        )
    except (OSError, ValueError, UnicodeDecodeError, TypeError) as exc:
        typer.echo(f"Stored listing cannot be queued for exact project capture: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    # The queue is not an authorization decision. No project GET was performed.
    typer.echo(
        json.dumps(
            {
                "queue_output_path": str(output),
                "listing_artifact_sha256": queue["listing_artifact_sha256"],
                "listing_pages_reviewed": queue["listing_pages_reviewed"],
                "listing_records_parsed": queue["listing_records_parsed"],
                "candidate_count": queue["candidate_count"],
                "excluded_observations": queue["excluded_observations"],
                "candidates": queue["candidates"],
                "network_executed": False,
                "persistence_mutated": False,
                "commercial_leads_created": False,
                "next_step": (
                    "Review each candidate's exact official SCH and current public access; "
                    "execute capture-preview separately for an authorized new SCH; "
                    "independently approve any subsequent two-digest SQLite import."
                ),
            },
            sort_keys=True,
            indent=2,
        )
    )


@app.command("capture-preview")
def capture_preview(
    sch_number: Annotated[
        str, typer.Option("--sch-number", help="Exact 10-digit public CEQAnet SCH ID."),
    ],
    output: Annotated[
        Path, typer.Option("--output", help="New path for full retained live-execution evidence."),
    ],
    authorization_reason: Annotated[
        str, typer.Option("--authorization-reason", help="Reason for this exact single public GET."),
    ],
    execute_live: Annotated[
        bool, typer.Option("--execute-live", help="Explicit approval to request this one SCH export."),
    ] = False,
    plan_output: Annotated[
        Path | None, typer.Option("--plan-output", help="Optional new reviewed plan path."),
    ] = None,
    operator_id: Annotated[
        str | None, typer.Option("--operator-id", help="Optional audit label, not authentication."),
    ] = None,
    listing_evidence: Annotated[
        Path | None,
        typer.Option(
            "--listing-evidence",
            help="Optional retained listing evidence used to independently re-derive the queue.",
        ),
    ] = None,
    queue_evidence: Annotated[
        Path | None,
        typer.Option(
            "--queue-evidence",
            help="Optional exact-SCH review queue; requires --listing-evidence.",
        ),
    ] = None,
    requires_login: Annotated[bool, typer.Option("--requires-login")] = False,
    has_captcha: Annotated[bool, typer.Option("--has-captcha")] = False,
    robots_disallows_collection: Annotated[
        bool, typer.Option("--robots-disallows-collection"),
    ] = False,
    terms_disallow_collection: Annotated[
        bool, typer.Option("--terms-disallow-collection"),
    ] = False,
    paywalled: Annotated[bool, typer.Option("--paywalled")] = False,
) -> None:
    """Authorize one exact project CSV GET, retain full evidence, preview only; never import."""

    if not execute_live:
        raise typer.BadParameter("explicit --execute-live is required for network access")
    if not authorization_reason.strip():
        raise typer.BadParameter("authorization reason cannot be blank")
    if output.exists():
        raise typer.BadParameter("capture output already exists; use a new evidence path")
    if plan_output is not None and (
        plan_output.absolute() == output.absolute() or plan_output.exists()
    ):
        raise typer.BadParameter("plan output must be new and distinct from source evidence")
    if (listing_evidence is None) != (queue_evidence is None):
        raise typer.BadParameter(
            "--listing-evidence and --queue-evidence must be supplied together"
        )
    discovery_binding: dict[str, object] | None = None
    if listing_evidence is not None and queue_evidence is not None:
        protected_paths = {listing_evidence.absolute(), queue_evidence.absolute()}
        if output.absolute() in protected_paths or (
            plan_output is not None and plan_output.absolute() in protected_paths
        ):
            raise typer.BadParameter(
                "capture and plan outputs must be distinct from listing and queue evidence"
            )
        discovery_binding = _load_bound_capture_candidate(
            listing_evidence=listing_evidence,
            queue_evidence=queue_evidence,
            sch_number=sch_number,
        )
    requested_at = datetime.now(UTC)
    try:
        request = build_ceqanet_csv_export_request(sch_number=sch_number)
        profile = SourceAccessProfile(
            public_url=request.source_url,
            requires_login=requires_login,
            has_captcha=has_captcha,
            robots_disallows_collection=robots_disallows_collection,
            terms_disallow_collection=terms_disallow_collection,
            paywalled=paywalled,
        )
        authorized = execute_authorized_ceqanet_csv(
            request=request,
            access_profile=profile,
            authorization_reason=authorization_reason,
            caller_confirmation=True,
            timeout_seconds=20.0,
            max_body_bytes=10_000_000,
            max_retained_rows=100,
            operator_id=operator_id,
        )
    except (AuthorizationDeniedError, ValueError) as exc:
        typer.echo(f"Exact public-source acquisition blocked: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    # Preserve the complete original response, including an unsuccessful execution,
    # before attempting offline decoding or target-county normalization. Never
    # replace older evidence even when a source returns an unexpected format.
    try:
        execution_payload = authorized.execution.model_dump(mode="json")
        retained_payload: dict[str, object]
        if discovery_binding is None:
            retained_payload = execution_payload
        else:
            retained_payload = {
                "schema_version": "ceqanet_bound_project_capture.v1",
                "discovery_binding": discovery_binding,
                "live_execution": execution_payload,
            }
        write_runtime_text(
            output,
            json.dumps(retained_payload, indent=2, sort_keys=True) + "\n",
            overwrite=False,
        )
    except (OSError, ValueError) as exc:
        typer.echo(f"Acquisition completed but retained evidence could not be published: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    if (
        authorized.execution.request != request
        or authorized.execution.request_url != request.source_url
    ):
        typer.echo(
            f"Source evidence preserved at {output}, but execution identity does "
            "not match the exact approved SCH request; no import plan was prepared.",
            err=True,
        )
        raise typer.Exit(code=1)
    if not authorized.verification.passed:
        typer.echo(
            f"Retained source verification failed; inspect preserved evidence at {output}",
            err=True,
        )
        raise typer.Exit(code=1)

    # The effect-consumption service can replay a previously authorized exact GET.
    # Retain that evidence for audit, but do not relabel its old body as a NEW
    # capture or prepare an import under this current-capture command.
    if not requested_at <= authorized.execution.executed_at <= datetime.now(UTC):
        typer.echo(
            f"Source evidence preserved at {output}, but execution timestamp is not "
            "within this capture invocation; an exact prior-result replay is not "
            "a new public-source acquisition. No import plan was prepared.",
            err=True,
        )
        raise typer.Exit(code=1)

    # Reopen the actual saved bytes through the existing independently replayable
    # bridge. A non-project export, incomplete body, unrecognized/other county,
    # conflicting schema or >100 rows cannot be silently omitted or imported.
    try:
        bridge = _load_evidence(output)
        if discovery_binding is not None:
            claimed_county = discovery_binding["source_claimed_county"]
            captured_counties = {record.county for record in bridge.preview.ceqa_records}
            if captured_counties != {claimed_county}:
                raise ValueError(
                    "captured project county does not match the exact queued source claim"
                )
        if plan_output is not None:
            write_runtime_text(
                plan_output,
                json.dumps(bridge.write_plan.to_dict(), indent=2, sort_keys=True) + "\n",
                overwrite=False,
            )
    except (OSError, ValueError, typer.BadParameter) as exc:
        typer.echo(
            f"Source evidence preserved at {output}, but reviewed import preview is blocked: {exc}",
            err=True,
        )
        raise typer.Exit(code=1) from exc
    typer.echo(
        json.dumps(
            {
                **_summary(bridge),
                "network_executed": True,
                "executed_at": authorized.execution.executed_at.isoformat(),
                "source_evidence_path": str(output),
                "plan_output_path": str(plan_output) if plan_output is not None else None,
                "source_verification_passed": True,
                "execution_timestamp_within_invocation": True,
                "discovery_binding": discovery_binding,
                "source_claims_verified": False,
                "persistence_mutated": False,
                "next_step": (
                    "Independently inspect both approved digests and use the separate "
                    "reviewed-import apply command with --execute-write."
                ),
            },
            indent=2,
            sort_keys=True,
        )
    )


@app.command("preview")
def preview(
    evidence_path: Annotated[
        Path,
        typer.Option(
            "--evidence", exists=True, dir_okay=False, readable=True,
            help="Existing complete, digest-bound CEQAnet CSV live execution JSON.",
        ),
    ],
    plan_output: Annotated[
        Path | None,
        typer.Option(
            "--plan-output", help="Optional path for exact reviewed write-plan JSON.",
        ),
    ] = None,
) -> None:
    """Independently replay public CSV evidence and preview all proposed writes."""

    bridge = _load_evidence(evidence_path)
    if plan_output is not None:
        write_runtime_text(
            plan_output,
            json.dumps(bridge.write_plan.to_dict(), indent=2, sort_keys=True) + "\n",
        )
    typer.echo(json.dumps(_summary(bridge), indent=2, sort_keys=True))


@app.command("apply")
def apply(
    evidence_path: Annotated[
        Path,
        typer.Option(
            "--evidence", exists=True, dir_okay=False, readable=True,
            help="Exact retained CSV execution JSON reviewed through preview.",
        ),
    ],
    database_path: Annotated[
        Path,
        typer.Option(
            "--database", exists=True, dir_okay=False, writable=True,
            help="An existing, operator-compatible SQLite database.",
        ),
    ],
    approved_source_sha256: Annotated[
        str,
        typer.Option("--approved-source-sha256", help="Exact source digest from preview."),
    ],
    approved_plan_digest: Annotated[
        str,
        typer.Option("--approved-plan-digest", help="Exact write-plan digest from preview."),
    ],
    authorization_reason: Annotated[
        str,
        typer.Option("--authorization-reason", help="Reason for importing this exact source."),
    ],
    execute_write: Annotated[
        bool,
        typer.Option("--execute-write", help="Explicit permission for one atomic persistence."),
    ] = False,
    operator_id: Annotated[
        str | None,
        typer.Option("--operator-id", help="Optional local audit identity, not authentication."),
    ] = None,
) -> None:
    """Apply only the reviewed exact plan through existing governed persistence."""

    if not execute_write:
        raise typer.BadParameter("explicit --execute-write is required")
    bridge = _load_evidence(evidence_path)
    if (
        approved_source_sha256 != bridge.source_sha256
        or approved_plan_digest != _plan_digest(bridge)
    ):
        raise typer.BadParameter("the retained source or write plan differs from reviewed hashes")
    if not authorization_reason.strip():
        raise typer.BadParameter("authorization reason cannot be blank")
    try:
        # Refuse a destination that the existing GUI cannot read; never migrate it
        # silently just to complete an import.
        engine = create_operator_read_engine(database_path)
        engine.dispose()
        result = execute_authorized_ceqanet_write_plan(
            write_plan_payload=bridge.write_plan.to_dict(),
            database_url=database_url_from_path(database_path),
            caller_confirmation=True,
            authorization_reason=authorization_reason,
            operator_id=operator_id,
        )
        if result.execution.applied_count != bridge.write_plan.operation_count:
            raise ValueError("persisted operations differ from the exact reviewed plan")
        # Read the same database using the GUI's actual read-only connection.
        engine = create_operator_read_engine(database_path)
        try:
            with Session(engine, autoflush=False) as session:
                store = CeqaStore(session)
                for expected in bridge.preview.ceqa_records:
                    actual = store.get(expected.ceqa_key)
                    if actual is None or actual.title != expected.title or (
                        actual.provenance[0].raw_reference
                        != expected.provenance[0].raw_reference
                    ):
                        raise ValueError("operator could not retrieve the exact imported source")
        finally:
            engine.dispose()
    except (AuthorizationDeniedError, OSError, RuntimeError, ValueError) as exc:
        typer.echo(f"Reviewed CEQAnet import blocked or not fully verified: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(
        json.dumps(
            {
                **_summary(bridge),
                "persistence_mutated": True,
                "applied_operations": result.execution.applied_count,
                "operator_readback_verified": True,
                "source_review_state": "unassessed",
                "commercial_leads_created": False,
                "operator_command": (
                    f"constructionsight-operator --database {database_path} --open-browser"
                ),
            },
            indent=2,
            sort_keys=True,
        )
    )
