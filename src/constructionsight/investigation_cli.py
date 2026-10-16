"""Bounded offline replay into the shared investigation services; no network access."""

from __future__ import annotations

import argparse
import json
import os
import stat
from pathlib import Path

from constructionsight.ceqa_models import CeqaRecord
from constructionsight.intelligence.investigation_query_service import InvestigationQueryService
from constructionsight.intelligence.investigation_review_service import InvestigationReviewService
from constructionsight.intelligence.investigation_service import InvestigationService
from constructionsight.intelligence.investigation_sources import (
    from_domain,
    from_parcel,
    from_smarts,
)
from constructionsight.parcel_core_models import ParcelCoreRecord
from constructionsight.permit_models import PermitRecord
from constructionsight.smarts_evidence_ledger import read_smarts_observations
from constructionsight.storage.database import (
    create_database_engine,
    initialize_database,
    managed_session,
    session_factory,
)
from constructionsight.storage.intelligence_store import IntelligenceStore
from constructionsight.storage.operator_read_store import create_operator_read_engine


def _private_target(path: Path, *, create: bool = True) -> Path:
    path = path.absolute()
    if create:
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    info = path.parent.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or info.st_mode & 0o077:
        raise ValueError("investigation database requires an owner-only directory (0700)")
    if create:
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        except FileExistsError:
            pass
        else:
            os.close(fd)
    info = path.lstat()
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_uid != os.geteuid()
        or stat.S_IMODE(info.st_mode) != 0o600
        or info.st_nlink != 1
    ):
        raise ValueError("investigation database must be a private, owned regular file (0600)")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--show", metavar="INVESTIGATION_ID")
    parser.add_argument("--review", metavar="RELATIONSHIP_ID")
    parser.add_argument("--decision", choices=("associate", "reject"))
    parser.add_argument("--target")
    parser.add_argument("--expected")
    parser.add_argument("--reason")
    parser.add_argument("--operator")
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--kind", choices=("smarts-journal", "ceqa", "permit", "parcel"))
    parser.add_argument("--after-id", type=int, default=0)
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args(argv)
    if args.review:
        if args.source or args.kind or args.show or args.after_id:
            parser.error("review cannot be combined with source replay or dossier display")
        if args.decision is None:
            if any([args.target, args.expected, args.reason, args.operator, args.confirm]):
                parser.error("review preview takes no decision options; use --decision to apply")
            engine = create_operator_read_engine(args.database)
        else:
            if not args.expected or not args.reason:
                parser.error("a review decision requires --expected and --reason")
            target = _private_target(args.database, create=False)
            engine = create_database_engine(f"sqlite+pysqlite:///{target}")
        try:
            review_service = InvestigationReviewService(engine)
            result = (
                review_service.preview(args.review)
                if args.decision is None
                else review_service.review(
                    args.review,
                    decision=args.decision,
                    target_id=args.target,
                    expected_identity=args.expected,
                    reason=args.reason,
                    caller_confirmation=args.confirm,
                    operator_id=args.operator,
                )
            )
            print(json.dumps(result))
        finally:
            engine.dispose()
        return 0
    if any([args.decision, args.target, args.expected, args.reason, args.operator, args.confirm]):
        parser.error("review options require --review")
    if args.show:
        if args.source or args.kind or args.after_id:
            parser.error("show is a read-only operation and cannot be combined with source replay")
        engine = create_operator_read_engine(args.database)
        try:
            with managed_session(session_factory(engine)) as session:
                report = InvestigationQueryService(IntelligenceStore(session)).dossier(args.show)
                print(json.dumps(report))
        finally:
            engine.dispose()
        return 0
    if not args.source or not args.kind:
        parser.error("source replay requires both --source and --kind")
    if not 1 <= args.limit <= 500 or args.after_id < 0:
        parser.error("limit must be 1–500 and after-id nonnegative")
    if args.source.resolve() == args.database.resolve():
        parser.error("source and destination must be different files")
    if args.kind == "smarts-journal":
        retained = read_smarts_observations(args.source, after_id=args.after_id, limit=args.limit)
        observations = [from_smarts(item) for item in retained]
        next_cursor = retained[-1].observation_id if retained else args.after_id
    else:
        if args.after_id:
            parser.error("after-id applies only to a SMARTS journal")
        with args.source.open("rb") as stream:
            body = stream.read(16_000_001)
        if len(body) > 16_000_000:
            raise ValueError("source JSON exceeds bounded input size")
        payload = json.loads(body)
        rows = payload if isinstance(payload, list) else [payload]
        if len(rows) > args.limit:
            raise ValueError("source JSON exceeds limit; split the retained export into batches")
        if args.kind == "parcel":
            observations = [from_parcel(ParcelCoreRecord.model_validate(row)) for row in rows]
        else:
            model: type[CeqaRecord] | type[PermitRecord] = (
                CeqaRecord if args.kind == "ceqa" else PermitRecord
            )
            observations = [from_domain(model.model_validate(row)) for row in rows]
        next_cursor = None
    # Validate all retained input before opening the destination database.
    target = _private_target(args.database)
    engine = create_database_engine(f"sqlite+pysqlite:///{target}")
    try:
        initialize_database(engine)
        with managed_session(session_factory(engine)) as session:
            store = IntelligenceStore(session)
            service = InvestigationService(store)
            ids = [service.ingest(item).project_cluster_id for item in observations]
        print(
            json.dumps(
                {
                    "processed_observations": len(observations),
                    "investigation_ids": ids,
                    "next_observation_id": next_cursor,
                    "network_executed": False,
                    "identity_verified": False,
                    "commercial_authority_granted": False,
                    "limitations": [
                        "Processed observations do not establish a fully investigated site.",
                        "No automatic cross-source identity merge or commercial action.",
                    ],
                }
            )
        )
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
