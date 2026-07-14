"""Operator storage summary CLI."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table
from sqlalchemy import inspect, text

from constructionsight.storage.database import (
    create_database_engine,
    initialize_database,
    managed_session,
    session_factory,
)

app = typer.Typer(help="ConstructionSight storage summary tools.")
console = Console()

STORAGE_TABLES: tuple[tuple[str, str], ...] = (
    ("domain_sites", "domain site records"),
    ("domain_entities", "domain entity records"),
    ("domain_permits", "domain permit records"),
    ("domain_planning_cases", "domain planning-case records"),
    ("domain_ceqa_records", "domain CEQA records"),
    ("domain_agenda_items", "domain agenda item records"),
    ("domain_documents", "domain document records"),
    ("domain_relationships", "domain relationship records"),
    ("intelligence_evidence_records", "intelligence evidence records"),
    ("intelligence_entities", "intelligence entity records"),
    ("intelligence_relationships", "intelligence relationship records"),
    ("intelligence_project_clusters", "intelligence project clusters"),
    ("intelligence_opportunities", "intelligence opportunities"),
    ("intelligence_runtime_events", "intelligence runtime events"),
    ("intelligence_watchlist_items", "intelligence watchlist items"),
    ("parcel_core_records", "parcel core records"),
    ("parcel_assurance_reports", "parcel fact assurance reports"),
    ("site_resolution_results", "site-resolution result reports"),
    ("permit_snapshots", "permit snapshots"),
    ("permit_transitions", "permit transitions"),
    ("contractor_identities", "contractor identities"),
    ("decision_records", "decision records"),
    ("opportunity_enrichment_reports", "opportunity enrichment reports"),
    ("lead_review_packages", "lead review packages"),
    ("lead_fingerprints", "lead fingerprints"),
    ("lead_duplicate_results", "lead duplicate results"),
    ("lead_workflows", "lead workflow records"),
    ("lead_workflow_events", "lead workflow events"),
    ("result_ledgers", "result ledgers"),
    ("result_share_records", "result share records"),
)


@dataclass(frozen=True)
class StorageTableSummary:
    """Operator-facing storage table summary."""

    table_name: str
    layer: str
    exists: bool
    row_count: int | None


def build_storage_summary(database_url: str | None = None) -> list[StorageTableSummary]:
    """Initialize known metadata and return table existence/count summaries."""

    engine = create_database_engine(database_url)
    initialize_database(engine)
    table_names = set(inspect(engine).get_table_names())
    factory = session_factory(engine)
    with managed_session(factory) as session:
        summaries: list[StorageTableSummary] = []
        for table_name, layer in STORAGE_TABLES:
            exists = table_name in table_names
            row_count = None
            if exists:
                result = session.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
                row_count = int(result.scalar_one())
            summaries.append(
                StorageTableSummary(
                    table_name=table_name,
                    layer=layer,
                    exists=exists,
                    row_count=row_count,
                )
            )
        return summaries


@app.callback()
def storage_summary_root() -> None:
    """ConstructionSight storage summary commands."""


@app.command("summary")
def storage_summary(
    database_url: Annotated[
        str | None,
        typer.Option(help="SQLAlchemy database URL to inspect."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json-output", help="Print machine-readable JSON."),
    ] = False,
) -> None:
    """Print storage table existence and row counts."""

    summaries = build_storage_summary(database_url)
    if json_output:
        console.print_json(json.dumps([asdict(summary) for summary in summaries]))
        return

    table = Table(title="ConstructionSight Storage Summary")
    table.add_column("Table")
    table.add_column("Layer")
    table.add_column("Exists")
    table.add_column("Rows")
    for summary in summaries:
        table.add_row(
            summary.table_name,
            summary.layer,
            str(summary.exists),
            "" if summary.row_count is None else str(summary.row_count),
        )
    console.print(table)
