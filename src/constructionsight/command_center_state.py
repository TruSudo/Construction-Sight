"""Persistent operator facts and actions, separate from captured public records."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import re
import sqlite3
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError

from constructionsight.lead_watchlist import watchlist
from constructionsight.lead_workflow import connect, now, run_history, save_feedback
from constructionsight.security_fit import WEIGHTS
from constructionsight.smarts_active import PUBLIC_FIELDS
from constructionsight.smarts_evidence_ledger import verify_smarts_journal

FACTS = {
    "SITE_NAME",
    "SITE_CITY",
    "SITE_COUNTY",
    "OWNER_NAME",
    "DEVELOPER_NAME",
    "project_id",
    "project_type",
    "stage",
    "permit_type",
    "size_sf",
    "value",
    "architect",
    "contractor",
    "permit_date",
    "SITE_LATITUDE",
    "SITE_LONGITUDE",
    "site_verified",
}
DEFAULTS: dict[str, Any] = {
    "profile": {"name": "", "role": "", "company": "", "default_region": ""},
    "weights": WEIGHTS,
    "map": {"url_template": None, "attribution": None},
    "map_view": None,
    "saved_views": {},
    "source_enabled": True,
    "templates": {
        "email": (
            "Hello {{contact}},\nI’m contacting you about {{project}} in {{city}}.\n{{company}}"
        ),
        "call": "Hello {{contact}}, I’m calling about {{project}} in {{city}}.",
        "voicemail": "Hello {{contact}}, please return my call about {{project}}. {{company}}",
    },
}


def initialize(directory: Path) -> None:
    with connect(directory) as db:
        db.executescript("""
          CREATE TABLE IF NOT EXISTS cc_settings(id INTEGER PRIMARY KEY CHECK(id=1),data TEXT);
          CREATE TABLE IF NOT EXISTS cc_facts(key TEXT PRIMARY KEY,data TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS cc_contacts(
            id INTEGER PRIMARY KEY,key TEXT NOT NULL,data TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS cc_controls(
            key TEXT PRIMARY KEY,dnc INTEGER NOT NULL DEFAULT 0,hidden INTEGER NOT NULL DEFAULT 0);
          CREATE TABLE IF NOT EXISTS cc_events(
            id INTEGER PRIMARY KEY,key TEXT NOT NULL,at TEXT NOT NULL,kind TEXT NOT NULL,data TEXT);
          CREATE TABLE IF NOT EXISTS cc_reads(id TEXT PRIMARY KEY);
          CREATE TABLE IF NOT EXISTS cc_photos(
            key TEXT PRIMARY KEY,data BLOB,mime TEXT,source TEXT,at TEXT);
          CREATE TABLE IF NOT EXISTS outreach_queue(source_key TEXT PRIMARY KEY,added_at TEXT);
        """)


def settings(directory: Path) -> dict[str, Any]:
    initialize(directory)
    with connect(directory) as db:
        row = db.execute("SELECT data FROM cc_settings WHERE id=1").fetchone()
    result: dict[str, Any] = json.loads(json.dumps(DEFAULTS))
    if row:
        result.update(json.loads(row["data"]))
    else:
        for filename, key in (("weights.json", "weights"), ("map.json", "map")):
            path = directory / filename
            if path.exists():
                result[key] = json.loads(path.read_text())
    result["data_folder"] = str(directory.resolve())
    return result


def save_settings(directory: Path, payload: dict[str, Any]) -> dict[str, Any]:
    if set(payload) - (set(DEFAULTS)):
        raise ValueError("Unknown setting")
    for key, value in payload.items():
        if key == "profile":
            if not isinstance(value, dict) or set(value) != set(DEFAULTS[key]):
                raise ValueError("Profile requires name, role, company and default_region")
            if any(not isinstance(v, str) or len(v) > 500 for v in value.values()):
                raise ValueError("Profile values must be text up to 500 characters")
        elif key == "weights":
            if not isinstance(value, dict) or set(value) != set(WEIGHTS):
                raise ValueError("Unknown scoring weights")
            if any(type(v) is not int or not 0 <= v <= 100 for v in value.values()):
                raise ValueError("Weights must be integers from 0 to 100")
        elif key == "source_enabled":
            if type(value) is not bool:
                raise ValueError("Source enabled must be boolean")
        elif key == "map":
            if not isinstance(value, dict) or set(value) != {"url_template", "attribution"}:
                raise ValueError("Map requires URL and attribution")
            url, attribution = value["url_template"], value["attribution"]
            if url and (
                not isinstance(url, str)
                or not url.startswith("https://")
                or any("{" + k + "}" not in url for k in ("z", "x", "y"))
            ):
                raise ValueError("Map URL must be HTTPS with {z}, {x}, {y}")
            if url and (not isinstance(attribution, str) or not attribution.strip()):
                raise ValueError("Map attribution is required")
        elif key == "map_view":
            if (
                not isinstance(value, dict)
                or set(value) != {"center", "zoom"}
                or not isinstance(value["center"], list)
                or len(value["center"]) != 2
                or any(type(v) not in (int, float) for v in value["center"])
                or not -90 <= value["center"][0] <= 90
                or not -180 <= value["center"][1] <= 180
                or type(value["zoom"]) is not int
                or not 3 <= value["zoom"] <= 18
            ):
                raise ValueError("Invalid map view")
        elif key in ("saved_views", "templates"):
            if not isinstance(value, dict) or len(json.dumps(value)) > 20000:
                raise ValueError("Invalid saved configuration")
            if key == "templates" and (
                set(value) != set(DEFAULTS[key])
                or any(not isinstance(v, str) for v in value.values())
            ):
                raise ValueError("Email, call and voicemail templates are required")
    initialize(directory)
    with connect(directory) as db:
        db.execute("BEGIN IMMEDIATE")
        prior = db.execute("SELECT data FROM cc_settings WHERE id=1").fetchone()
        data = json.loads(prior["data"]) if prior else settings(directory)
        data.pop("data_folder", None)
        data.update(payload)
        db.execute("INSERT OR REPLACE INTO cc_settings VALUES (1,?)", (json.dumps(data),))
    return settings(directory)


def event(directory: Path, key: str, kind: str, data: dict[str, Any]) -> None:
    with connect(directory) as db:
        db.execute(
            "INSERT INTO cc_events(key,at,kind,data) VALUES (?,?,?,?)",
            (key, now(), kind, json.dumps(data)),
        )


def attach(directory: Path, rows: list[dict[str, Any]]) -> None:
    initialize(directory)
    with connect(directory) as db:
        facts = {r["key"]: json.loads(r["data"]) for r in db.execute("SELECT * FROM cc_facts")}
        controls = {r["key"]: dict(r) for r in db.execute("SELECT * FROM cc_controls")}
        contacts: dict[str, list[dict[str, Any]]] = {}
        for item in db.execute("SELECT * FROM cc_contacts"):
            contacts.setdefault(item["key"], []).append(
                {**json.loads(item["data"]), "id": item["id"]}
            )
        queued = {r["source_key"] for r in db.execute("SELECT * FROM outreach_queue")}
        photos = {r["key"] for r in db.execute("SELECT key FROM cc_photos")}
    for row in rows:
        key = row["source_key"]
        row["source_fields"] = {k: row.get(k) for k in {*PUBLIC_FIELDS, *FACTS}}
        row["field_sources"] = dict(row.get("field_sources", {}))
        for field, fact in facts.get(key, {}).items():
            row[field] = fact["value"]
            row["field_sources"][field] = {k: v for k, v in fact.items() if k != "value"}
        from constructionsight.contact_call_list import contact_view

        row["sourced_contacts"] = [contact_view(c) for c in contacts.get(key, [])]
        row["do_not_contact"] = bool(controls.get(key, {}).get("dnc"))
        row["hidden"] = bool(controls.get(key, {}).get("hidden"))
        row["outreach_queued"] = key in queued
        row["photo"] = key in photos
        if row.get("site_verified"):
            row["site_verification"] = {"verified": True, "source": "Entered by user"}


def save_facts(directory: Path, key: str, payload: dict[str, Any]) -> dict[str, Any]:
    if set(payload) - FACTS:
        raise ValueError("Unknown dossier field")
    normalized: dict[str, Any] = {}
    for field, value in payload.items():
        if field == "site_verified":
            if type(value) is not bool:
                raise ValueError("Site verification must be boolean")
        elif value is not None and value != "":
            if field in ("value", "size_sf", "SITE_LATITUDE", "SITE_LONGITUDE"):
                try:
                    number = Decimal(str(value))
                    lower, upper = {"SITE_LATITUDE": (-90, 90), "SITE_LONGITUDE": (-180, 180)}.get(
                        field, (0, 1_000_000_000_000)
                    )
                    if not number.is_finite() or not lower <= number <= upper:
                        raise ValueError("Numeric field outside bounds")
                    if field == "size_sf" and number != number.to_integral_value():
                        raise ValueError("Size must be whole square feet")
                    if field == "value" and number != number.quantize(Decimal("0.01")):
                        raise ValueError("Value requires exact cents")
                    value = str(number) if field == "value" else float(number)
                except InvalidOperation as exc:
                    raise ValueError("Invalid numeric value") from exc
            elif field == "permit_date":
                date.fromisoformat(str(value))
            elif not isinstance(value, str) or len(value) > 2000:
                raise ValueError("Facts must be text up to 2,000 characters")
            if field == "project_type" and value not in (
                "industrial",
                "commercial",
                "residential",
                "infrastructure",
                "unknown",
            ):
                raise ValueError("Invalid project type")
        normalized[field] = value
    initialize(directory)
    with connect(directory) as db:
        db.execute("BEGIN IMMEDIATE")
        prior = db.execute("SELECT data FROM cc_facts WHERE key=?", (key,)).fetchone()
        facts = json.loads(prior["data"]) if prior else {}
        for field, value in normalized.items():
            if value is None or value == "":
                facts.pop(field, None)
            else:
                facts[field] = {"value": value, "source": "Entered by user", "at": now()}
        db.execute("INSERT OR REPLACE INTO cc_facts VALUES (?,?)", (key, json.dumps(facts)))
    event(directory, key, "facts", normalized)
    return facts


def save_contact(directory: Path, key: str, payload: dict[str, Any]) -> dict[str, Any]:
    if set(payload) - {"name", "role", "company", "email", "phone", "source"}:
        raise ValueError("Unknown contact field")
    if any(not isinstance(v, str) or len(v) > 2000 for v in payload.values()):
        raise ValueError("Contact fields must be text")
    email, phone = payload.get("email", "").strip(), payload.get("phone", "").strip()
    if not payload.get("source", "").strip() or not (email or phone):
        raise ValueError("Contact needs a source and email or phone")
    if email and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise ValueError("Invalid email")
    if phone and not 7 <= len(re.sub(r"\D", "", phone)) <= 15:
        raise ValueError("Invalid phone")
    initialize(directory)
    data = {**payload, "email": email, "phone": phone, "at": now()}
    with connect(directory) as db:
        db.execute("BEGIN IMMEDIATE")
        for prior in db.execute("SELECT id,data FROM cc_contacts WHERE key=?", (key,)):
            contact = json.loads(prior["data"])
            if (email and contact.get("email", "").casefold() == email.casefold()) or (
                phone and re.sub(r"\D", "", contact.get("phone", "")) == re.sub(r"\D", "", phone)
            ):
                return {**contact, "id": prior["id"]}
        cursor = db.execute(
            "INSERT INTO cc_contacts(key,data) VALUES (?,?)", (key, json.dumps(data))
        )
        data["id"] = cursor.lastrowid
    event(directory, key, "contact", {"contact_id": data["id"], "source": payload["source"]})
    return data


def control(directory: Path, key: str, payload: dict[str, Any]) -> dict[str, Any]:
    if (
        not payload
        or set(payload) - {"dnc", "hidden"}
        or any(type(v) is not bool for v in payload.values())
    ):
        raise ValueError("DNC and hidden must be boolean")
    initialize(directory)
    with connect(directory) as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute("INSERT OR IGNORE INTO cc_controls(key) VALUES (?)", (key,))
        for field, value in payload.items():
            db.execute(f"UPDATE cc_controls SET {field}=? WHERE key=?", (int(value), key))
        if payload.get("dnc"):
            db.execute("DELETE FROM outreach_queue WHERE source_key=?", (key,))
    event(directory, key, "control", payload)
    return payload


def queue(directory: Path, row: dict[str, Any]) -> dict[str, Any]:
    initialize(directory)
    key = row["source_key"]
    with connect(directory) as db:
        db.execute("BEGIN IMMEDIATE")
        dnc = db.execute("SELECT dnc FROM cc_controls WHERE key=?", (key,)).fetchone()
        if (
            row.get("do_not_contact")
            or (dnc and dnc["dnc"])
            or row["feedback"]["status"] == "Not a fit"
        ):
            raise ValueError("Do-Not-Contact or excluded lead")
        inserted = db.execute("INSERT OR IGNORE INTO outreach_queue VALUES (?,?)", (key, now()))
        fresh = bool(inserted.rowcount)
    if fresh:
        fields = {
            k: row["feedback"].get(k)
            for k in ("notes", "last_contacted", "reason_code", "reason_text")
        }
        fields["notes"] = fields["notes"] or ""
        fields["reason_text"] = fields["reason_text"] or ""
        save_feedback(directory, key, {**fields, "status": "Outreach queued"}, row)
        event(directory, key, "outreach_queued", {})
    return {"source_key": key, "queued": True}


def activity(directory: Path, key: str) -> list[dict[str, Any]]:
    initialize(directory)
    with connect(directory) as db:
        result = [
            {**dict(r), "data": json.loads(r["data"])}
            for r in db.execute("SELECT * FROM cc_events WHERE key=? ORDER BY id DESC", (key,))
        ]
        result += [
            {"at": r["changed_at"], "kind": "status", "data": {"status": r["status"]}}
            for r in db.execute("SELECT * FROM feedback_events WHERE source_key=?", (key,))
        ]
    return sorted(result, key=lambda r: r["at"], reverse=True)


def notifications(directory: Path, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    initialize(directory)
    with connect(directory) as db:
        read = {r["id"] for r in db.execute("SELECT * FROM cc_reads")}
    result = [
        {
            "id": "new:" + r["source_key"],
            "source_key": r["source_key"],
            "message": "New source lead: " + str(r.get("SITE_NAME") or "—"),
            "county": r.get("SITE_COUNTY"),
            "city": r.get("SITE_CITY"),
        }
        for r in rows
        if r.get("is_new")
    ]
    for w in watchlist(directory, rows):
        for kind, flagged in (("due", w["due"]), ("change", w["changed"])):
            if flagged:
                result.append(
                    {
                        "id": f"{kind}:{w['source_key']}:{w['updated_at']}",
                        "source_key": w["source_key"],
                        "message": ("Reminder due: " if kind == "due" else "Source review: ")
                        + str(w["row"].get("SITE_NAME") or "—"),
                        "county": w["row"].get("SITE_COUNTY"),
                        "city": w["row"].get("SITE_CITY"),
                    }
                )
    result += [
        {"id": f"run:{r['id']}", "message": "Capture failed: " + str(r["error"])}
        for r in run_history(directory)
        if r["outcome"] == "error"
    ]
    return [{**item, "read": item["id"] in read} for item in result]


def mark_read(directory: Path, payload: dict[str, Any]) -> dict[str, Any]:
    ids = payload.get("ids")
    if (
        set(payload) != {"ids"}
        or not isinstance(ids, list)
        or len(ids) > 5000
        or any(not isinstance(i, str) or len(i) > 1000 for i in ids)
    ):
        raise ValueError("Invalid notification IDs")
    with connect(directory) as db:
        db.executemany("INSERT OR IGNORE INTO cc_reads VALUES (?)", [(i,) for i in ids])
    return {"read": len(ids)}


def evidence(directory: Path, row: dict[str, Any], *, verify: bool = False) -> dict[str, Any]:
    path = directory / "evidence.sqlite3"
    result: dict[str, Any] = {
        "source": "California SMARTS",
        "source_key": row["source_key"],
        "row_sha256": row.get("row_sha256"),
        "response_sha256": row.get("response_sha256"),
        "field_sources": row.get("field_sources", {}),
        "activity": activity(directory, row["source_key"]),
        "verified": None,
        "available": path.is_file(),
    }
    if verify:
        try:
            if not path.is_file():
                raise ValueError("Original response journal is unavailable")
            result["journal"] = verify_smarts_journal(path, read_only=True)
            with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as db:
                result["verified"] = bool(
                    db.execute(
                        "SELECT 1 FROM smarts_observations "
                        "WHERE source_key=? AND row_sha256=? AND response_sha256=? LIMIT 1",
                        (row["source_key"], row.get("row_sha256"), row.get("response_sha256")),
                    ).fetchone()
                )
            if not result["verified"]:
                result["error"] = "This lead does not match a verified source observation"
        except (ValueError, sqlite3.Error, OSError) as exc:
            result.update(verified=False, error=str(exc))
    return result


def backup(directory: Path) -> bytes:
    from constructionsight.data_folder import make_backup

    return make_backup(directory)


def fingerprint(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False
        ).encode()
    ).hexdigest()


def save_photo(directory: Path, key: str, payload: dict[str, Any]) -> dict[str, Any]:
    if set(payload) != {"data", "source"} or not isinstance(payload["data"], str):
        raise ValueError("Photo requires image bytes and a source")
    source = payload["source"]
    if not isinstance(source, str) or not source.strip() or len(source) > 2000:
        raise ValueError("Enter the photograph source / ownership")
    try:
        data = base64.b64decode(payload["data"], validate=True)
        if not 0 < len(data) <= 1_000_000:
            raise ValueError("Photo must be at most 1 MB")
        with Image.open(io.BytesIO(data)) as im:
            if im.format not in ("PNG", "JPEG") or im.width * im.height > 16_000_000:
                raise ValueError("Use a PNG or JPEG up to 16 megapixels")
            mime = "image/png" if im.format == "PNG" else "image/jpeg"
            im.verify()
    except (ValueError, UnidentifiedImageError, OSError) as exc:
        raise ValueError("Invalid photograph") from exc
    initialize(directory)
    with connect(directory) as db:
        db.execute(
            "INSERT OR REPLACE INTO cc_photos VALUES (?,?,?,?,?)", (key, data, mime, source, now())
        )
    event(directory, key, "photo", {"source": source, "sha256": hashlib.sha256(data).hexdigest()})
    return {"saved": True, "source": source}


def import_smarts_contacts(directory: Path, row: dict[str, Any]) -> dict[str, Any]:
    """Import actual source-reported contact fields only from hash-verified retained bytes."""
    checked = evidence(directory, row, verify=True)
    if not checked["verified"]:
        raise ValueError(checked.get("error", "Original evidence verification failed"))
    path = directory / "evidence.sqlite3"
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True) as db:
        raw = db.execute(
            "SELECT raw_response,request_url FROM smarts_observations WHERE source_key=? "
            "AND row_sha256=? AND response_sha256=? ORDER BY id DESC LIMIT 1",
            (row["source_key"], row["row_sha256"], row["response_sha256"]),
        ).fetchone()
    return _import_verified_contact_body(directory, row, raw[0], source_url=raw[1])


def _import_verified_contact_body(
    directory: Path, row: dict[str, Any], raw: bytes, *, source_url: str = ""
) -> dict[str, Any]:
    if hashlib.sha256(raw).hexdigest() != row["response_sha256"]:
        raise ValueError("Original response hash mismatch")
    records = json.loads(raw)["result"]["records"]
    record = next(
        r
        for r in records
        if fingerprint({k: v for k, v in r.items() if k != "_id"}) == row["row_sha256"]
    )
    saved = []
    reported_kinds = []

    def text(field: str) -> str:
        value = str(record.get(field) or "").strip()
        return "" if value.upper() in {"NA", "N/A", "UNKNOWN", "NULL", "NONE", "0", "-"} else value

    for prefix, label in (("DEVELOPER", "developer"), ("SITE", "site")):
        email, phone = text(prefix + "_EMAIL"), text(prefix + "_PHONE")
        if not email and not phone:
            continue
        if email and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
            email = ""
        if phone and not 7 <= len(re.sub(r"\D", "", phone)) <= 15:
            phone = ""
        if not email and not phone:
            continue
        reported_kinds.append(label)
        saved.append(
            save_contact(
                directory,
                row["source_key"],
                {
                    "name": " ".join(
                        filter(
                            None,
                            (
                                text(prefix + "_CONTACT_FIRST_NAME"),
                                text(prefix + "_CONTACT_LAST_NAME"),
                            ),
                        )
                    ),
                    "role": text("DEVELOPER_TITLE") if prefix == "DEVELOPER" else "Site contact",
                    "company": text("DEVELOPER_NAME") if prefix == "DEVELOPER" else "",
                    "email": email,
                    "phone": phone,
                    "source": (
                        f"SMARTS source-reported {label} contact; "
                        f"response SHA-256 {row['response_sha256']}; source {source_url}"
                    ),
                },
            )
        )
    for contact, kind in zip(saved, reported_kinds, strict=True):
        with connect(directory) as db:
            item = db.execute(
                "SELECT data FROM cc_contacts WHERE id=?", (contact["id"],)
            ).fetchone()
            stored = json.loads(item["data"])
            stored["source_kinds"] = sorted(set(stored.get("source_kinds", [])) | {kind})
            if (
                source_url
                and row["response_sha256"] in stored.get("source", "")
                and source_url not in stored["source"]
            ):
                stored["source"] += "; source " + source_url
            contact["source"] = stored["source"]
            db.execute(
                "UPDATE cc_contacts SET data=? WHERE id=?", (json.dumps(stored), contact["id"])
            )
            contact["source_kinds"] = stored["source_kinds"]
    return {
        "contacts": saved,
        "reported_contact_kinds": reported_kinds,
        "message": "Source-reported regulatory contact; purchasing authority is unverified",
    }


def deltas(directory: Path, rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Compare real snapshots under the same current scoring and region rules."""
    from constructionsight.security_fit import rank_leads

    current_time = datetime.now(UTC)
    regions = {
        "all",
        *(str(r["SITE_COUNTY"]) for r in rows if r.get("SITE_COUNTY")),
        *("city:" + str(r["SITE_CITY"]) for r in rows if r.get("SITE_CITY")),
    }
    result: dict[str, Any] = {region: {"total": None, "new": None} for region in regions}

    def scoped(items: list[dict[str, Any]], region: str) -> list[dict[str, Any]]:
        return [
            r
            for r in items
            if not r.get("hidden")
            and r["project_type"] != "infrastructure"
            and (
                region == "all"
                or (
                    r.get("SITE_CITY") == region[5:]
                    if region.startswith("city:")
                    else r.get("SITE_COUNTY") == region
                )
            )
        ]

    for key, days in (("total", 30), ("new", 7)):
        cutoff = (current_time - timedelta(days=days)).isoformat()
        with connect(directory) as db:
            old = db.execute(
                "SELECT snapshot FROM runs WHERE outcome='success' AND finished_at<=? "
                "AND snapshot IS NOT NULL ORDER BY finished_at DESC LIMIT 1",
                (cutoff,),
            ).fetchone()
        if not old:
            continue
        snapshot = json.loads(old["snapshot"])
        historical = rank_leads(snapshot["rows"], weights=settings(directory)["weights"])
        attach(directory, historical)
        historical = rank_leads(historical, weights=settings(directory)["weights"])
        past_time = datetime.fromisoformat(snapshot["captured_at"])
        for region in regions:
            present, past = scoped(rows, region), scoped(historical, region)
            if key == "new":
                present = [
                    r
                    for r in present
                    if r.get("first_seen")
                    and r["first_seen"] >= (current_time - timedelta(days=7)).isoformat()
                ]
                past = [
                    r
                    for r in past
                    if r.get("first_seen")
                    and r["first_seen"] >= (past_time - timedelta(days=7)).isoformat()
                ]
            if past:
                result[region][key] = round((len(present) - len(past)) / len(past) * 100, 1)
    return result
