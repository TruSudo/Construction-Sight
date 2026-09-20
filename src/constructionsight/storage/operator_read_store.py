"""Read-only SQLite connection and bounded access to existing domain records."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import Engine, create_engine, func, or_, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool
from sqlalchemy.sql.elements import ColumnElement

from constructionsight.ceqa_models import CeqaRecord
from constructionsight.operator_dashboard_models import RecordKind
from constructionsight.permit_models import PermitRecord
from constructionsight.storage.domain_orm import CeqaDomainRecord, PermitDomainRecord
from constructionsight.storage.domain_store import CeqaStore, PermitStore


def create_operator_read_engine(database_path: Path) -> Engine:
    """Open an existing database in SQLite mode=ro; never initialize or migrate it."""

    path = database_path.resolve(strict=True)
    if not path.is_file():
        raise ValueError("operator database must be an existing regular file")
    return create_engine(
        f"sqlite+pysqlite:///{path.as_uri()}?mode=ro&uri=true",
        connect_args={"check_same_thread": False},
        poolclass=NullPool,
    )


def read_project_page(
    session: Session,
    *,
    kind: RecordKind,
    query: str,
    county: str,
    limit: int,
    offset: int,
) -> tuple[list[CeqaRecord | PermitRecord], int]:
    """Filter before limiting; retain stable source identity and embedded evidence."""

    row_type = CeqaDomainRecord if kind == "ceqa" else PermitDomainRecord
    title_column = CeqaDomainRecord.title if kind == "ceqa" else PermitDomainRecord.permit_number
    filters: list[ColumnElement[bool]] = []
    if county:
        filters.append(
            func.lower(func.trim(row_type.county)).in_([county.lower(), f"{county.lower()} county"])
        )
    if query:
        identity_column = (
            CeqaDomainRecord.state_clearinghouse_number
            if kind == "ceqa"
            else PermitDomainRecord.permit_number
        )
        agency_column = (
            CeqaDomainRecord.lead_agency if kind == "ceqa" else PermitDomainRecord.jurisdiction
        )
        filters.append(
            or_(
                title_column.icontains(query, autoescape=True),
                identity_column.icontains(query, autoescape=True),
                agency_column.icontains(query, autoescape=True),
                row_type.description.icontains(query, autoescape=True),
                row_type.site_json.icontains(query, autoescape=True),
                row_type.entities_json.icontains(query, autoescape=True),
            )
        )
    total = session.scalar(select(func.count()).select_from(row_type).where(*filters)) or 0
    rows = session.scalars(
        select(row_type).where(*filters).order_by(row_type.id).offset(offset).limit(limit)
    )
    records: list[CeqaRecord | PermitRecord] = []
    for row in rows:
        if isinstance(row, CeqaDomainRecord):
            records.append(CeqaStore._to_model(row))
        elif isinstance(row, PermitDomainRecord):
            records.append(PermitStore._to_model(row))
        else:
            raise ValueError("unexpected source record type")
    return records, total
