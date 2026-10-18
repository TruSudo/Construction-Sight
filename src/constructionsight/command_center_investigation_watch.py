"""Native canonical-investigation watch state, using existing private operator settings.

A watch observes committed evidence/association changes; it does not create a
second investigation, independently verify a site, or authorize commercial work.
The separate investigation database is always read-only from this module.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from constructionsight import command_center_state as state
from constructionsight.command_center_investigations import investigation_view
from constructionsight.lead_workflow import connect

_DIGEST = re.compile(r"[0-9a-f]{64}")


def observation(directory: Path, investigation_id: str) -> dict[str, Any]:
    """Fingerprint only this investigation's committed material state.

    Unrelated worker events must not trip watches. Reject truncated dossiers
    instead of silently presenting a partial source-watch baseline as complete.
    """
    if not isinstance(investigation_id, str) or not 1 <= len(investigation_id) <= 255:
        raise ValueError("exact canonical investigation ID required")
    dossier = investigation_view(directory, investigation_id=investigation_id)
    if any(dossier.get(key) for key in (
        "sources_truncated", "relationships_truncated", "evidence_truncated",
        "parties_truncated", "candidate_links_truncated",
    )):
        raise ValueError("investigation exceeds bounded watch evidence; review the full history")
    project = dossier["investigation"]
    canonical = project["project_cluster_id"]
    members = dossier.get("source_membership", [])
    relationships = dossier.get("relationships", [])
    material = {
        "canonical_investigation_id": canonical,
        "project_name": project["project_name"],
        "cluster_status": project.get("cluster_status"),
        "lifecycle_phase": project.get("lifecycle_phase"),
        "members": [
            {
                "source_id": m["source_id"],
                "evidence_id": m["current_evidence_id"],
                "membership_basis": m["membership_basis"],
                "relationships": sorted(m["membership_relationship_ids"]),
            }
            for m in members
        ],
        "relationships": [
            {
                "id": link["relationship_id"],
                "predicate": link["predicate"],
                "status": link["relationship_status"],
                "supports": link["supporting_evidence_ids"],
                "contradicts": link["contradictory_evidence_ids"],
            }
            for link in relationships
        ],
    }
    raw = json.dumps(material, sort_keys=True, separators=(",", ":")).encode("utf-8")
    county_set = sorted({
        str(x.get("county"))
        for x in dossier.get("source_observations", [])
        if x.get("county")
    })
    return {
        "investigation_id": canonical,
        "requested_investigation_id": investigation_id,
        "current_digest": hashlib.sha256(raw).hexdigest(),
        "county": county_set[0] if len(county_set) == 1 else None,
        "source_claim_only": True,
        "identity_independently_verified": False,
        "commercial_authority_granted": False,
    }


def _rows(directory: Path) -> list[dict[str, Any]]:
    state.initialize(directory)
    with connect(directory) as db:
        return [dict(x) for x in db.execute(
            "SELECT investigation_id, acknowledged_digest FROM cc_investigation_watches "
            "ORDER BY investigation_id LIMIT 101"
        )]


def inspect(directory: Path, investigation_id: str) -> dict[str, Any]:
    current = observation(directory, investigation_id)
    records = _rows(directory)
    if len(records) > 100:
        raise ValueError("canonical watch limit exceeded")
    saved = next(
        (x for x in records if x["investigation_id"] == investigation_id), None
    )
    return {
        **current,
        "watched": saved is not None,
        "changed": saved is not None
        and saved["acknowledged_digest"] != current["current_digest"],
        "acknowledged_digest": saved["acknowledged_digest"] if saved else None,
    }


def action(directory: Path, payload: dict[str, Any]) -> dict[str, Any]:
    if (
        set(payload) != {"action", "investigation_id", "expected_digest"}
        or payload["action"] not in {"watch", "acknowledge", "remove"}
        or not isinstance(payload["expected_digest"], str)
        or _DIGEST.fullmatch(payload["expected_digest"]) is None
    ):
        raise ValueError("exact canonical watch action and evidence digest required")
    identity = payload["investigation_id"]
    current = observation(directory, identity)
    if current["investigation_id"] != identity:
        raise ValueError("investigation identity was reassigned; open its current dossier")
    if current["current_digest"] != payload["expected_digest"]:
        raise ValueError("investigation changed; reload its current evidence before acting")
    state.initialize(directory)
    with connect(directory) as db:
        db.execute("BEGIN IMMEDIATE")
        exists = db.execute(
            "SELECT acknowledged_digest FROM cc_investigation_watches WHERE investigation_id=?",
            (identity,),
        ).fetchone()
        if payload["action"] == "watch":
            if exists is not None:
                raise ValueError("investigation is already watched")
            if db.execute("SELECT COUNT(*) FROM cc_investigation_watches").fetchone()[0] >= 100:
                raise ValueError("canonical investigation watch limit reached")
            db.execute(
                "INSERT INTO cc_investigation_watches(investigation_id,acknowledged_digest) "
                "VALUES (?,?)", (identity, current["current_digest"]),
            )
        elif payload["action"] == "acknowledge":
            if exists is None:
                raise ValueError("canonical investigation is not watched")
            db.execute(
                "UPDATE cc_investigation_watches SET acknowledged_digest=? "
                "WHERE investigation_id=?",
                (current["current_digest"], identity),
            )
        else:
            if exists is None:
                raise ValueError("canonical investigation is not watched")
            db.execute(
                "DELETE FROM cc_investigation_watches WHERE investigation_id=?", (identity,)
            )
    return inspect(directory, identity)


def notifications(directory: Path) -> list[dict[str, Any]]:
    """Use committed investigation revisions, never independent watch polling."""
    records = _rows(directory)
    if len(records) > 100:
        raise ValueError("canonical investigation watch limit exceeded")
    notices: list[dict[str, Any]] = []
    for saved in records:
        try:
            current = observation(directory, saved["investigation_id"])
        except (ValueError, OSError, RuntimeError) as exc:
            notices.append({
                "id": "investigation-watch:unavailable:" + saved["investigation_id"],
                "message": "Watched shared investigation unavailable: "
                + saved["investigation_id"] + " (" + str(exc)[:120] + ")",
                "county": None, "city": None,
            })
            continue
        if current["current_digest"] == saved["acknowledged_digest"]:
            continue
        identity = saved["investigation_id"]
        notice = hashlib.sha256(
            json.dumps([identity, current["current_digest"]], separators=(",", ":")).encode()
        ).hexdigest()
        notices.append({
            "id": "investigation-watch:" + notice,
            "investigation_id": current["investigation_id"],
            "watched_investigation_id": identity,
            "message": "Watched shared investigation changed; review current evidence",
            "county": current["county"],
            "city": None,
            "source_claim_only": True,
        })
    return notices
