"""Command-line interface for ConstructionSight."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.table import Table

from constructionsight.adapters import (
    audit_adapter_contracts,
    audit_source_adapter_coverage,
    default_adapter_family_specs,
    default_adapter_registry,
)
from constructionsight.adapters.base import AdapterRunContext
from constructionsight.adapters.runner import AdapterRunner
from constructionsight.ceqanet_discovery_service import discover_ceqanet_public_search
from constructionsight.intelligence.artifact_identity import (
    IdentityFingerprint,
    IdentityResolutionCandidate,
)
from constructionsight.intelligence.artifact_resolution_service import ArtifactResolutionService
from constructionsight.intelligence.graph_neighborhood_service import (
    GraphNeighborhood,
    GraphNeighborhoodService,
)
from constructionsight.intelligence.relationship_query_service import RelationshipQueryService
from constructionsight.models import PublicSource
from constructionsight.storage.database import (
    DEFAULT_DATABASE_PATH,
    create_database_engine,
    initialize_database,
    managed_session,
    session_factory,
)
from constructionsight.storage.intelligence_store import IntelligenceStore
from constructionsight.storage.runtime_artifacts import read_runtime_text, write_runtime_text
from constructionsight.storage.source_registry import SourceRegistryStore
from constructionsight.storage.verification_store import VerificationStore
from constructionsight.verification.source_verifier import SourceVerifier

app = typer.Typer(help="ConstructionSight lawful public-record intelligence tools.")
console = Console()


def _load_sources_from_json(registry_path: Path) -> list[PublicSource]:
    """Load and validate source records from a JSON registry file."""

    data = json.loads(read_runtime_text(registry_path))
    if not isinstance(data, list):
        raise typer.BadParameter("Source registry JSON must be a list of source records.")
    return [PublicSource.model_validate(item) for item in data]


def _find_source_by_name(sources: list[PublicSource], source_name: str) -> PublicSource:
    """Return one loaded source by source name."""

    for source in sources:
        if source.source_name == source_name:
            return source
    raise typer.BadParameter(f"Source registry does not contain source_name={source_name!r}.")


def _safe_json_object(raw_json: str) -> Any:
    """Decode a JSON string while preserving malformed payloads for auditability."""

    try:
        return json.loads(raw_json)
    except json.JSONDecodeError:
        return {"unparsed_raw_json": raw_json}


def _read_json_object_file(input_path: Path) -> dict[str, Any]:
    """Read a JSON object from disk for export verification."""

    try:
        payload = json.loads(read_runtime_text(input_path))
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"Invalid JSON export: {exc}") from exc
    if not isinstance(payload, dict):
        raise typer.BadParameter("Verification export JSON must be an object.")
    return payload


def _verification_record_to_dict(record: Any) -> dict[str, Any]:
    """Convert a persisted verification ORM record into a JSON-safe dictionary."""

    return {
        "id": record.id,
        "source_id": record.source_id,
        "source_name": record.source_name,
        "public_url": record.public_url,
        "checked_at": record.checked_at.isoformat(),
        "url_reachable": record.url_reachable,
        "portal_type_detected": record.portal_type_detected,
        "public_search_available": record.public_search_available,
        "login_required": record.login_required,
        "permit_details_visible": record.permit_details_visible,
        "agenda_packets_visible": record.agenda_packets_visible,
        "pdfs_downloadable": record.pdfs_downloadable,
        "contractor_owner_applicant_fields_visible": (
            record.contractor_owner_applicant_fields_visible
        ),
        "evidence_snapshot_text": record.evidence_snapshot_text,
        "confidence_score": record.confidence_score,
        "notes": record.notes,
        "raw_observations": _safe_json_object(record.raw_observations_json),
    }


def _canonical_json_bytes(payload: dict[str, Any]) -> bytes:
    """Serialize JSON deterministically for checksum generation."""

    return json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def _verification_export_payload_scope(payload: dict[str, Any]) -> dict[str, Any]:
    """Return the integrity-protected verification export payload scope."""

    return {
        "metadata": payload["metadata"],
        "record_count": payload["record_count"],
        "records": payload["records"],
    }


def _verification_export_integrity(payload_without_integrity: dict[str, Any]) -> dict[str, str]:
    """Build a checksum block for the verification export payload."""

    digest = hashlib.sha256(
        _canonical_json_bytes(_verification_export_payload_scope(payload_without_integrity))
    ).hexdigest()
    return {
        "algorithm": "sha256",
        "canonicalization": "json.dumps(sort_keys=True,separators=(',',':'),default=str)",
        "payload_scope": "metadata,record_count,records",
        "payload_sha256": digest,
    }


def _verification_export_validation(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate the integrity block of a verification export payload."""

    integrity = payload.get("integrity")
    if not isinstance(integrity, dict):
        return {
            "valid": False,
            "reason": "missing integrity object",
            "expected_sha256": None,
            "actual_sha256": None,
        }

    if integrity.get("algorithm") != "sha256":
        return {
            "valid": False,
            "reason": "unsupported or missing integrity algorithm",
            "expected_sha256": None,
            "actual_sha256": integrity.get("payload_sha256"),
        }
    if integrity.get("payload_scope") != "metadata,record_count,records":
        return {
            "valid": False,
            "reason": "unsupported or missing integrity payload scope",
            "expected_sha256": None,
            "actual_sha256": integrity.get("payload_sha256"),
        }

    try:
        expected = hashlib.sha256(
            _canonical_json_bytes(_verification_export_payload_scope(payload))
        ).hexdigest()
    except KeyError as exc:
        return {
            "valid": False,
            "reason": f"missing protected payload field: {exc.args[0]}",
            "expected_sha256": None,
            "actual_sha256": integrity.get("payload_sha256"),
        }

    actual = integrity.get("payload_sha256")
    if actual != expected:
        return {
            "valid": False,
            "reason": "payload checksum mismatch",
            "expected_sha256": expected,
            "actual_sha256": actual,
        }
    return {
        "valid": True,
        "reason": "ok",
        "expected_sha256": expected,
        "actual_sha256": expected,
    }


def _verification_export_payload(records: list[Any], *, limit: int) -> dict[str, Any]:
    """Build a self-describing verification export payload."""

    record_payloads = [_verification_record_to_dict(record) for record in records]
    payload: dict[str, Any] = {
        "metadata": {
            "schema_version": "verification_export.v1",
            "export_type": "source_verification_records",
            "application": "ConstructionSight",
            "generated_at": datetime.now(UTC).isoformat(),
            "limit": limit,
        },
        "record_count": len(record_payloads),
        "records": record_payloads,
    }
    payload["integrity"] = _verification_export_integrity(payload)
    return payload


def _write_json_file(output_path: Path, payload: dict[str, Any]) -> None:
    """Write deterministic UTF-8 JSON to disk."""

    write_runtime_text(
        output_path, json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
    )


def _render_source_table(sources: list[PublicSource], title: str) -> None:
    """Render a concise source-registry table."""

    table = Table(title=title)
    table.add_column("Source")
    table.add_column("Jurisdiction")
    table.add_column("Platform")
    table.add_column("Status")
    table.add_column("Confidence")

    for source in sources:
        table.add_row(
            source.source_name,
            source.jurisdiction.name,
            source.platform_family.value,
            source.verification_status.value,
            str(source.confidence_score),
        )

    console.print(table)


def _render_verification_table(records: list[Any], title: str) -> None:
    """Render persisted verification records in compact table form."""

    table = Table(title=title)
    table.add_column("Checked")
    table.add_column("Source")
    table.add_column("Reachable")
    table.add_column("Platform")
    table.add_column("Search")
    table.add_column("Login")
    table.add_column("Confidence")
    table.add_column("Notes")

    for record in records:
        table.add_row(
            record.checked_at.isoformat(),
            record.source_name,
            str(record.url_reachable),
            record.portal_type_detected,
            str(record.public_search_available),
            str(record.login_required),
            str(record.confidence_score),
            record.notes or "",
        )
    console.print(table)


def _render_relationships_table(records: list[Any], title: str) -> None:
    """Render relationship assertions."""

    table = Table(title=title)
    table.add_column("Relationship")
    table.add_column("Subject")
    table.add_column("Predicate")
    table.add_column("Object")
    table.add_column("Status")
    table.add_column("Confidence")

    for record in records:
        table.add_row(
            record.relationship_id,
            record.subject_entity_id,
            record.predicate,
            record.object_entity_id,
            record.relationship_status.value,
            str(record.confidence_score),
        )
    console.print(table)


def _render_project_clusters_table(records: list[Any], title: str) -> None:
    """Render project clusters."""

    table = Table(title=title)
    table.add_column("Project")
    table.add_column("Name")
    table.add_column("Jurisdiction")
    table.add_column("Phase")
    table.add_column("Status")
    table.add_column("Confidence")

    for record in records:
        table.add_row(
            record.project_cluster_id,
            record.project_name or "",
            record.jurisdiction or "",
            record.lifecycle_phase.value,
            record.cluster_status.value,
            str(record.cluster_confidence),
        )
    console.print(table)


def _render_opportunities_table(records: list[Any], title: str) -> None:
    """Render opportunity signals."""

    table = Table(title=title)
    table.add_column("Opportunity")
    table.add_column("Category")
    table.add_column("Project")
    table.add_column("Status")
    table.add_column("Confidence")
    table.add_column("Summary")

    for record in records:
        table.add_row(
            record.opportunity_id,
            record.category.value,
            record.project_cluster_id or "",
            record.opportunity_status.value,
            str(record.confidence_score),
            record.evidence_summary,
        )
    console.print(table)


def _graph_neighborhood_to_dict(neighborhood: GraphNeighborhood) -> dict[str, Any]:
    """Convert a graph neighborhood into a machine-readable dictionary."""

    return {
        "center_node_id": neighborhood.center_node_id,
        "center_node_kind": neighborhood.center_node_kind,
        "node_count": neighborhood.node_count,
        "edge_count": neighborhood.edge_count,
        "connected_entities": [
            entity.model_dump(mode="json") for entity in neighborhood.connected_entities
        ],
        "connected_projects": [
            project.model_dump(mode="json") for project in neighborhood.connected_projects
        ],
        "relationships": [
            relationship.model_dump(mode="json") for relationship in neighborhood.relationships
        ],
        "opportunities": [
            opportunity.model_dump(mode="json") for opportunity in neighborhood.opportunities
        ],
    }


def _read_artifact_resolution_preview_input(
    input_path: Path,
) -> tuple[IdentityFingerprint, IdentityFingerprint, str | None]:
    """Read artifact-resolution preview input from a JSON object file."""

    try:
        payload = json.loads(read_runtime_text(input_path))
    except json.JSONDecodeError as exc:
        raise typer.BadParameter(f"Invalid artifact resolution JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise typer.BadParameter("Artifact resolution input JSON must be an object.")
    if "left" not in payload:
        raise typer.BadParameter("Artifact resolution input JSON requires a left fingerprint.")
    if "right" not in payload:
        raise typer.BadParameter("Artifact resolution input JSON requires a right fingerprint.")

    candidate_id = payload.get("candidate_id")
    if candidate_id is not None and not isinstance(candidate_id, str):
        raise typer.BadParameter("candidate_id must be a string when provided.")

    try:
        left = IdentityFingerprint.model_validate(payload["left"])
        right = IdentityFingerprint.model_validate(payload["right"])
    except ValueError as exc:
        raise typer.BadParameter(f"Invalid artifact fingerprint payload: {exc}") from exc

    return left, right, candidate_id


def _artifact_resolution_candidate_to_dict(
    candidate: IdentityResolutionCandidate,
) -> dict[str, Any]:
    """Convert an artifact resolution candidate into JSON-safe preview output."""

    payload = candidate.model_dump(mode="json")
    payload["resolution_score"] = candidate.resolution_score
    payload["recommended_decision"] = candidate.recommended_decision.value
    payload["has_near_unique_support"] = candidate.has_near_unique_support
    payload["has_near_unique_conflict"] = candidate.has_near_unique_conflict
    payload["has_only_weak_support"] = candidate.has_only_weak_support
    return payload


def _render_artifact_resolution_candidate(candidate: IdentityResolutionCandidate) -> None:
    """Render an artifact-resolution preview as Rich tables."""

    summary = Table(title="Artifact Resolution Preview")
    summary.add_column("Field")
    summary.add_column("Value")
    summary.add_row("Candidate", candidate.candidate_id)
    summary.add_row("Left identity", candidate.left_identity_id)
    summary.add_row("Right identity", candidate.right_identity_id)
    summary.add_row("Target kind", candidate.target_kind.value)
    summary.add_row("Resolution score", str(candidate.resolution_score))
    summary.add_row("Recommended decision", candidate.recommended_decision.value)
    summary.add_row("Supporting matches", str(len(candidate.supporting_matches)))
    summary.add_row("Conflicts", str(len(candidate.conflicts)))
    summary.add_row("Review required", str(candidate.review_required))
    summary.add_row("Evidence summary", candidate.evidence_summary)
    console.print(summary)

    if candidate.supporting_matches:
        matches = Table(title="Supporting Artifact Matches")
        matches.add_column("Artifact")
        matches.add_column("Left observation")
        matches.add_column("Right observation")
        matches.add_column("Strength")
        matches.add_column("Contribution")
        matches.add_column("Sources")
        for match in candidate.supporting_matches:
            matches.add_row(
                match.artifact_type.value,
                match.left_observation_id,
                match.right_observation_id,
                str(match.match_strength),
                str(match.contribution),
                ", ".join(match.source_families),
            )
        console.print(matches)

    if candidate.conflicts:
        conflicts = Table(title="Artifact Conflicts")
        conflicts.add_column("Artifact")
        conflicts.add_column("Left value")
        conflicts.add_column("Right value")
        conflicts.add_column("Strength")
        conflicts.add_column("Penalty")
        for conflict in candidate.conflicts:
            conflicts.add_row(
                conflict.artifact_type.value,
                conflict.left_value,
                conflict.right_value,
                str(conflict.conflict_strength),
                str(conflict.penalty),
            )
        console.print(conflicts)


def _render_graph_neighborhood(neighborhood: GraphNeighborhood, title: str) -> None:
    """Render a graph neighborhood summary and component tables."""

    summary = Table(title=title)
    summary.add_column("Field")
    summary.add_column("Value")
    summary.add_row("Center node", neighborhood.center_node_id)
    summary.add_row("Center kind", neighborhood.center_node_kind)
    summary.add_row("Node count", str(neighborhood.node_count))
    summary.add_row("Edge count", str(neighborhood.edge_count))
    summary.add_row("Connected entities", str(len(neighborhood.connected_entities)))
    summary.add_row("Connected projects", str(len(neighborhood.connected_projects)))
    summary.add_row("Opportunities", str(len(neighborhood.opportunities)))
    console.print(summary)

    if neighborhood.connected_entities:
        entities_table = Table(title="Connected Entities")
        entities_table.add_column("Entity")
        entities_table.add_column("Type")
        entities_table.add_column("Name")
        entities_table.add_column("Status")
        entities_table.add_column("Confidence")
        for entity in neighborhood.connected_entities:
            entities_table.add_row(
                entity.entity_id,
                entity.entity_type.value,
                entity.canonical_name,
                entity.identity_status.value,
                str(entity.confidence_score),
            )
        console.print(entities_table)

    if neighborhood.connected_projects:
        _render_project_clusters_table(neighborhood.connected_projects, "Connected Projects")

    if neighborhood.relationships:
        _render_relationships_table(neighborhood.relationships, "Neighborhood Relationships")

    if neighborhood.opportunities:
        _render_opportunities_table(neighborhood.opportunities, "Neighborhood Opportunities")


def _relationship_query_service(database_url: str | None) -> tuple[Any, Any]:
    """Create a database session factory and engine for intelligence-query CLI commands."""

    engine = create_database_engine(database_url)
    initialize_database(engine)
    return engine, session_factory(engine)


def _render_verification_detail_lines(records: list[Any]) -> None:
    """Render full verification evidence details without Rich table truncation."""

    if not records:
        return

    console.print("Verification Evidence Details")
    for index, record in enumerate(records, start=1):
        console.print(f"verification_record={index}")
        console.print(f"checked={record.checked_at.isoformat()}")
        console.print(f"source={record.source_name}")
        console.print(f"reachable={record.url_reachable}")
        console.print(f"platform={record.portal_type_detected}")
        console.print(f"public_search={record.public_search_available}")
        console.print(f"login_required={record.login_required}")
        console.print(f"confidence={record.confidence_score}")
        console.print(f"notes={record.notes or ''}")


@app.command()
def version() -> None:
    """Print the installed ConstructionSight version."""

    from constructionsight import __version__

    console.print(__version__)


@app.command("validate-sources")
def validate_sources(
    registry_path: Annotated[
        Path,
        typer.Argument(help="Path to a JSON source registry file."),
    ],
) -> None:
    """Validate a JSON source registry against the phase-1 schema."""

    sources = _load_sources_from_json(registry_path)
    _render_source_table(sources, "ConstructionSight Source Registry")
    console.print(f"Validated {len(sources)} source records.")


@app.command("audit-adapters")
def audit_adapters() -> None:
    """Audit adapter registry/spec alignment."""

    result = audit_adapter_contracts(
        default_adapter_registry(),
        default_adapter_family_specs(),
    )

    table = Table(title="Adapter Contract Audit")
    table.add_column("Check")
    table.add_column("Result")
    table.add_row("Registry platforms", str(len(result.registry_platforms)))
    table.add_row("Spec platforms", str(len(result.spec_platforms)))
    table.add_row(
        "Missing specs",
        ", ".join(platform.value for platform in result.missing_specs) or "none",
    )
    table.add_row(
        "Missing registrations",
        ", ".join(platform.value for platform in result.missing_registrations) or "none",
    )
    table.add_row("Passed", str(result.passed))
    console.print(table)
    if not result.passed:
        raise typer.Exit(code=1)


@app.command("discover-ceqanet")
def discover_ceqanet(
    persist: Annotated[
        bool,
        typer.Option(help="Persist CEQAnet discovery through the verification store."),
    ] = False,
    registry_path: Annotated[
        Path,
        typer.Option(help="Source registry JSON used when --persist is enabled."),
    ] = Path("data/source_registry.seed.json"),
    database_url: Annotated[
        str | None,
        typer.Option(help="SQLAlchemy database URL used when --persist is enabled."),
    ] = None,
    source_name: Annotated[
        str,
        typer.Option(help="Source registry source_name to link CEQAnet discovery evidence to."),
    ] = "CEQAnet State Clearinghouse",
) -> None:
    """Discover the public CEQAnet advanced-search surface without collecting records."""

    result = discover_ceqanet_public_search()
    table = Table(title="CEQAnet Public Search Discovery")
    table.add_column("Check")
    table.add_column("Result")
    table.add_row("URL", result.url)
    table.add_row("Reachable", str(result.reachable))
    table.add_row("Status code", str(result.status_code))
    table.add_row("Advanced search", str(result.advanced_search_available))
    table.add_row("SCH number field", str(result.sch_number_field_detected))
    table.add_row("Document type field", str(result.document_type_field_detected))
    table.add_row("Date field", str(result.date_field_detected))
    table.add_row("Lead/public agency field", str(result.lead_agency_field_detected))
    table.add_row("Confidence", str(result.confidence_score))
    console.print(table)

    if persist:
        sources = _load_sources_from_json(registry_path)
        source = _find_source_by_name(sources, source_name)
        verification_result = result.to_source_verification_result(
            source_name=source.source_name,
            source_url=str(source.public_url),
        )
        engine = create_database_engine(database_url)
        initialize_database(engine)
        factory = session_factory(engine)
        with managed_session(factory) as session:
            source_store = SourceRegistryStore(session)
            source_store.upsert_many(sources)
            VerificationStore(session).add_result(verification_result)
        console.print(f"Persisted CEQAnet discovery verification for {source.source_name}.")

    if not result.reachable:
        raise typer.Exit(code=1)


@app.command("audit-source-coverage")
def audit_source_coverage(
    registry_path: Annotated[
        Path,
        typer.Argument(help="Path to a JSON source registry file."),
    ],
) -> None:
    """Audit whether source registry records have adapter/spec coverage."""

    sources = _load_sources_from_json(registry_path)
    result = audit_source_adapter_coverage(
        sources,
        default_adapter_registry(),
        default_adapter_family_specs(),
    )
    table = Table(title="Source Adapter Coverage Audit")
    table.add_column("Check")
    table.add_column("Result")
    table.add_row("Source records", str(result.source_count))
    table.add_row("Issues", str(len(result.issues)))
    table.add_row("Passed", str(result.passed))
    console.print(table)
    if result.issues:
        issue_table = Table(title="Coverage Issues")
        issue_table.add_column("Source")
        issue_table.add_column("Platform")
        issue_table.add_column("Issue")
        for issue in result.issues:
            issue_table.add_row(issue.source_name, issue.platform_family.value, issue.issue)
        console.print(issue_table)
        raise typer.Exit(code=1)


@app.command("dry-run-adapters")
def dry_run_adapters(
    registry_path: Annotated[
        Path,
        typer.Argument(help="Path to a JSON source registry file."),
    ],
    limit: Annotated[int | None, typer.Option(help="Maximum number of sources to dry-run.")] = None,
    max_records: Annotated[int | None, typer.Option(help="Maximum records per adapter.")] = 0,
) -> None:
    """Run registered adapters in dry-run mode against a source registry."""

    sources = _load_sources_from_json(registry_path)
    if limit is not None:
        sources = sources[:limit]
    runner = AdapterRunner(default_adapter_registry())
    context = AdapterRunContext(dry_run=True, max_records=max_records)
    table = Table(title="Adapter Dry Run")
    table.add_column("Source")
    table.add_column("Platform")
    table.add_column("Outcome")
    table.add_column("Records")
    table.add_column("Errors")
    for source in sources:
        result = runner.run_source(source, context)
        table.add_row(
            source.source_name,
            source.platform_family.value,
            result.outcome.value,
            str(len(result.records)),
            str(len(result.errors)),
        )
    console.print(table)
    console.print(f"Dry-ran {len(sources)} adapter sources.")


@app.command("init-db")
def init_db(
    database_url: Annotated[
        str | None,
        typer.Option(
            help=(
                "SQLAlchemy database URL. Defaults to local SQLite data/constructionsight.sqlite3."
            )
        ),
    ] = None,
) -> None:
    """Initialize the ConstructionSight database tables."""

    if database_url is None:
        DEFAULT_DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    engine = create_database_engine(database_url)
    initialize_database(engine)
    console.print("Database initialized.")


@app.command("load-sources")
def load_sources(
    registry_path: Annotated[
        Path,
        typer.Argument(help="Path to a JSON source registry file."),
    ],
    database_url: Annotated[
        str | None,
        typer.Option(
            help=(
                "SQLAlchemy database URL. Defaults to local SQLite data/constructionsight.sqlite3."
            )
        ),
    ] = None,
) -> None:
    """Load source registry records into the database."""

    sources = _load_sources_from_json(registry_path)
    engine = create_database_engine(database_url)
    initialize_database(engine)
    factory = session_factory(engine)
    with managed_session(factory) as session:
        count = SourceRegistryStore(session).upsert_many(sources)
    console.print(f"Loaded {count} source records.")


@app.command("list-sources")
def list_sources(
    database_url: Annotated[
        str | None,
        typer.Option(
            help=(
                "SQLAlchemy database URL. Defaults to local SQLite data/constructionsight.sqlite3."
            )
        ),
    ] = None,
) -> None:
    """List source registry records from the database."""

    engine = create_database_engine(database_url)
    initialize_database(engine)
    factory = session_factory(engine)
    with managed_session(factory) as session:
        sources = SourceRegistryStore(session).list_sources()
    _render_source_table(sources, "Persisted ConstructionSight Sources")
    console.print(f"Found {len(sources)} source records.")


@app.command("list-relationships")
def list_relationships(
    entity_id: Annotated[
        str,
        typer.Option(help="Entity ID whose direct relationships should be listed."),
    ],
    database_url: Annotated[
        str | None,
        typer.Option(
            help=(
                "SQLAlchemy database URL. Defaults to local SQLite data/constructionsight.sqlite3."
            )
        ),
    ] = None,
) -> None:
    """List persisted relationships connected to an entity."""

    _, factory = _relationship_query_service(database_url)
    with managed_session(factory) as session:
        query_service = RelationshipQueryService(IntelligenceStore(session))
        records = query_service.get_relationships_for_entity(entity_id)
    _render_relationships_table(records, f"Relationships for Entity {entity_id}")
    console.print(f"Found {len(records)} relationships.")


@app.command("list-projects-for-entity")
def list_projects_for_entity(
    entity_id: Annotated[
        str,
        typer.Option(help="Entity ID whose connected project clusters should be listed."),
    ],
    database_url: Annotated[
        str | None,
        typer.Option(
            help=(
                "SQLAlchemy database URL. Defaults to local SQLite data/constructionsight.sqlite3."
            )
        ),
    ] = None,
) -> None:
    """List project clusters connected to an entity."""

    _, factory = _relationship_query_service(database_url)
    with managed_session(factory) as session:
        query_service = RelationshipQueryService(IntelligenceStore(session))
        records = query_service.get_projects_for_entity(entity_id)
    _render_project_clusters_table(records, f"Projects for Entity {entity_id}")
    console.print(f"Found {len(records)} project clusters.")


@app.command("list-opportunities-for-project")
def list_opportunities_for_project(
    project_cluster_id: Annotated[
        str,
        typer.Option(help="Project cluster ID whose opportunities should be listed."),
    ],
    database_url: Annotated[
        str | None,
        typer.Option(
            help=(
                "SQLAlchemy database URL. Defaults to local SQLite data/constructionsight.sqlite3."
            )
        ),
    ] = None,
) -> None:
    """List opportunities tied to a project cluster."""

    _, factory = _relationship_query_service(database_url)
    with managed_session(factory) as session:
        query_service = RelationshipQueryService(IntelligenceStore(session))
        records = query_service.get_opportunities_for_project(project_cluster_id)
    _render_opportunities_table(records, f"Opportunities for Project {project_cluster_id}")
    console.print(f"Found {len(records)} opportunities.")


@app.command("list-opportunities-for-entity")
def list_opportunities_for_entity(
    entity_id: Annotated[
        str,
        typer.Option(
            help="Entity ID whose direct and project-derived opportunities should be listed."
        ),
    ],
    database_url: Annotated[
        str | None,
        typer.Option(
            help=(
                "SQLAlchemy database URL. Defaults to local SQLite data/constructionsight.sqlite3."
            )
        ),
    ] = None,
) -> None:
    """List opportunities tied directly or indirectly to an entity."""

    _, factory = _relationship_query_service(database_url)
    with managed_session(factory) as session:
        query_service = RelationshipQueryService(IntelligenceStore(session))
        records = query_service.get_opportunities_for_entity(entity_id)
    _render_opportunities_table(records, f"Opportunities for Entity {entity_id}")
    console.print(f"Found {len(records)} opportunities.")


@app.command("preview-artifact-resolution")
def preview_artifact_resolution(
    input_path: Annotated[
        Path,
        typer.Option(
            "--input",
            help="Path to artifact-resolution preview JSON containing left and right fingerprints.",
        ),
    ],
    json_output: Annotated[
        bool,
        typer.Option("--json-output", help="Emit machine-readable JSON instead of Rich tables."),
    ] = False,
    output_path: Annotated[
        Path | None,
        typer.Option(
            "--output",
            help="Write JSON output to this file path. Requires --json-output.",
        ),
    ] = None,
) -> None:
    """Preview deterministic artifact-based identity resolution from JSON fingerprints."""

    if output_path is not None and not json_output:
        typer.echo("--output requires --json-output.")
        raise typer.Exit(code=1)

    left, right, candidate_id = _read_artifact_resolution_preview_input(input_path)
    try:
        candidate = ArtifactResolutionService().resolve_fingerprints(
            left,
            right,
            candidate_id=candidate_id,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc

    if json_output:
        payload = _artifact_resolution_candidate_to_dict(candidate)
        if output_path is not None:
            _write_json_file(output_path, payload)
            typer.echo(f"Wrote artifact resolution JSON to {output_path}.")
            return
        console.print_json(json.dumps(payload))
        return

    _render_artifact_resolution_candidate(candidate)


@app.command("show-entity-neighborhood")
def show_entity_neighborhood(
    entity_id: Annotated[
        str,
        typer.Option(help="Entity ID whose immediate graph neighborhood should be displayed."),
    ],
    database_url: Annotated[
        str | None,
        typer.Option(
            help=(
                "SQLAlchemy database URL. Defaults to local SQLite data/constructionsight.sqlite3."
            )
        ),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json-output", help="Emit machine-readable JSON instead of Rich tables."),
    ] = False,
    output_path: Annotated[
        Path | None,
        typer.Option(
            "--output",
            help="Write JSON output to this file path. Requires --json-output.",
        ),
    ] = None,
) -> None:
    """Show immediate graph neighborhood around an entity."""

    _, factory = _relationship_query_service(database_url)
    with managed_session(factory) as session:
        neighborhood_service = GraphNeighborhoodService(IntelligenceStore(session))
        neighborhood = neighborhood_service.get_entity_neighborhood(entity_id)

    if output_path is not None and not json_output:
        raise typer.BadParameter("--output requires --json-output.")

    if json_output:
        payload = _graph_neighborhood_to_dict(neighborhood)
        if output_path is not None:
            _write_json_file(output_path, payload)
            typer.echo(f"Wrote graph neighborhood JSON to {output_path}.")
            return
        console.print_json(json.dumps(payload))
        return

    _render_graph_neighborhood(neighborhood, f"Entity Neighborhood {entity_id}")


@app.command("show-project-neighborhood")
def show_project_neighborhood(
    project_cluster_id: Annotated[
        str,
        typer.Option(
            help="Project cluster ID whose immediate graph neighborhood should be displayed."
        ),
    ],
    database_url: Annotated[
        str | None,
        typer.Option(
            help=(
                "SQLAlchemy database URL. Defaults to local SQLite data/constructionsight.sqlite3."
            )
        ),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json-output", help="Emit machine-readable JSON instead of Rich tables."),
    ] = False,
    output_path: Annotated[
        Path | None,
        typer.Option(
            "--output",
            help="Write JSON output to this file path. Requires --json-output.",
        ),
    ] = None,
) -> None:
    """Show immediate graph neighborhood around a project cluster."""

    _, factory = _relationship_query_service(database_url)
    with managed_session(factory) as session:
        neighborhood_service = GraphNeighborhoodService(IntelligenceStore(session))
        neighborhood = neighborhood_service.get_project_neighborhood(project_cluster_id)

    if output_path is not None and not json_output:
        raise typer.BadParameter("--output requires --json-output.")

    if json_output:
        payload = _graph_neighborhood_to_dict(neighborhood)
        if output_path is not None:
            _write_json_file(output_path, payload)
            typer.echo(f"Wrote graph neighborhood JSON to {output_path}.")
            return
        console.print_json(json.dumps(payload))
        return

    _render_graph_neighborhood(neighborhood, f"Project Neighborhood {project_cluster_id}")


@app.command("list-verifications")
def list_verifications(
    database_url: Annotated[
        str | None,
        typer.Option(
            help=(
                "SQLAlchemy database URL. Defaults to local SQLite data/constructionsight.sqlite3."
            )
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option(help="Maximum number of latest verification records to display."),
    ] = 20,
) -> None:
    """List latest persisted source-verification records from the database."""

    engine = create_database_engine(database_url)
    initialize_database(engine)
    factory = session_factory(engine)
    with managed_session(factory) as session:
        records = VerificationStore(session).list_latest(limit=limit)
    _render_verification_table(records, "Persisted Source Verification Records")
    _render_verification_detail_lines(records)
    console.print(f"Found {len(records)} verification records.")


@app.command("export-verifications")
def export_verifications(
    output_path: Annotated[
        Path,
        typer.Argument(help="Path to write exported verification JSON."),
    ],
    database_url: Annotated[
        str | None,
        typer.Option(
            help=(
                "SQLAlchemy database URL. Defaults to local SQLite data/constructionsight.sqlite3."
            )
        ),
    ] = None,
    limit: Annotated[
        int,
        typer.Option(help="Maximum number of latest verification records to export."),
    ] = 20,
) -> None:
    """Export latest persisted source-verification records to machine-readable JSON."""

    engine = create_database_engine(database_url)
    initialize_database(engine)
    factory = session_factory(engine)
    with managed_session(factory) as session:
        records = VerificationStore(session).list_latest(limit=limit)
    payload = _verification_export_payload(records, limit=limit)
    _write_json_file(output_path, payload)
    console.print(f"Exported {len(records)} verification records to {output_path}.")


@app.command("verify-verification-export")
def verify_verification_export(
    export_path: Annotated[
        Path,
        typer.Argument(help="Path to a verification export JSON file."),
    ],
) -> None:
    """Verify the SHA-256 integrity block in a verification export JSON file."""

    payload = _read_json_object_file(export_path)
    result = _verification_export_validation(payload)
    table = Table(title="Verification Export Integrity")
    table.add_column("Check")
    table.add_column("Result")
    table.add_row("Export path", str(export_path))
    table.add_row("Valid", str(result["valid"]))
    table.add_row("Reason", str(result["reason"]))
    table.add_row("Expected SHA-256", str(result["expected_sha256"]))
    table.add_row("Actual SHA-256", str(result["actual_sha256"]))
    console.print(table)
    if not result["valid"]:
        console.print(f"Verification export integrity invalid: {result['reason']}.")
        raise typer.Exit(code=1)
    console.print("Verification export integrity valid.")


@app.command("verify-sources")
def verify_sources(
    database_url: Annotated[
        str | None,
        typer.Option(
            help=(
                "SQLAlchemy database URL. Defaults to local SQLite data/constructionsight.sqlite3."
            )
        ),
    ] = None,
    limit: Annotated[int | None, typer.Option(help="Maximum number of sources to verify.")] = None,
) -> None:
    """Verify persisted public sources and store auditable verification results."""

    engine = create_database_engine(database_url)
    initialize_database(engine)
    factory = session_factory(engine)
    verifier = SourceVerifier()
    table = Table(title="Source Verification Results")
    table.add_column("Source")
    table.add_column("Reachable")
    table.add_column("Detected Platform")
    table.add_column("Search")
    table.add_column("Login")
    table.add_column("Confidence")
    with managed_session(factory) as session:
        sources = SourceRegistryStore(session).list_sources()
        if limit is not None:
            sources = sources[:limit]
        store = VerificationStore(session)
        for source in sources:
            result = verifier.verify(source)
            store.add_result(result)
            table.add_row(
                result.source_name,
                str(result.url_reachable),
                result.portal_type_detected.value,
                str(result.public_search_available),
                str(result.login_required),
                str(result.confidence_score),
            )
    console.print(table)
    console.print(f"Verified {len(sources)} source records.")
