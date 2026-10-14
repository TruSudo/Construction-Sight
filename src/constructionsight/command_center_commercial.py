"""Local, user-entered bid versions and royalty transactions. Never sends proposals."""

from __future__ import annotations

import io
import json
import sqlite3
import uuid
from decimal import ROUND_HALF_EVEN, Decimal, InvalidOperation
from pathlib import Path
from threading import Lock
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from constructionsight.bid_pricing_models import BidPriceLine
from constructionsight.command_center_state import fingerprint
from constructionsight.lead_workflow import REASONS, connect, now
from constructionsight.result_ledger_service import (
    calculate_share_minor_units,
    money_minor_units,
    share_rate_ppm_units,
)

CATEGORIES = ("equipment", "labor", "materials", "permits")
SCOPES = {
    "CCTV": "Camera locations, recording retention, network and commissioning per reviewed scope.",
    "Access control": "Door hardware, controllers, credentials and life-safety interfaces.",
    "Intrusion": "Detection zones, signaling, communications and commissioning per reviewed scope.",
    "Structured cabling": "Cable routes, endpoints, termination, labeling and certification.",
}
FONT_LOCK = Lock()


def initialize(directory: Path) -> None:
    with connect(directory) as db:
        db.executescript("""
          CREATE TABLE IF NOT EXISTS cc_bids(
            id TEXT,version INTEGER,key TEXT,at TEXT,data TEXT,digest TEXT,PRIMARY KEY(id,version));
          CREATE TABLE IF NOT EXISTS cc_prices(id TEXT PRIMARY KEY,data TEXT);
          CREATE TABLE IF NOT EXISTS cc_contracts(id TEXT PRIMARY KEY,bid TEXT UNIQUE,data TEXT);
          CREATE TABLE IF NOT EXISTS cc_ledger(
            id TEXT PRIMARY KEY,contract TEXT,at TEXT,kind TEXT,amount INTEGER,reference TEXT,
            reverses TEXT UNIQUE);
          CREATE TRIGGER IF NOT EXISTS cc_bids_no_update BEFORE UPDATE ON cc_bids
            BEGIN SELECT RAISE(ABORT,'Bid versions are immutable'); END;
          CREATE TRIGGER IF NOT EXISTS cc_bids_no_delete BEFORE DELETE ON cc_bids
            BEGIN SELECT RAISE(ABORT,'Bid versions are immutable'); END;
          CREATE TRIGGER IF NOT EXISTS cc_ledger_no_update BEFORE UPDATE ON cc_ledger
            BEGIN SELECT RAISE(ABORT,'Ledger entries are immutable'); END;
          CREATE TRIGGER IF NOT EXISTS cc_ledger_no_delete BEFORE DELETE ON cc_ledger
            BEGIN SELECT RAISE(ABORT,'Ledger entries are immutable'); END;
        """)


def decimal(value: Any, *, maximum: int = 100_000_000_000) -> Decimal:
    try:
        if isinstance(value, bool) or len(str(value)) > 100:
            raise ValueError("Invalid decimal")
        result = Decimal(str(value))
        if not result.is_finite() or result < 0 or result > maximum:
            raise ValueError("Amount outside bounds")
        return result
    except (InvalidOperation, TypeError) as exc:
        raise ValueError("Invalid decimal") from exc


def money(value: Any) -> int:
    return money_minor_units(decimal(value))


def required(value: Any, *, limit: int = 2000) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError("Required text is missing or too long")
    return value.strip()


def normalize(payload: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "id",
        "expected_version",
        "title",
        "prepared_for",
        "scope",
        "basis",
        "lines",
        "markup",
        "tax",
        "tax_basis",
        "status",
        "contract_value",
        "loss_reason",
    }
    if set(payload) - allowed:
        raise ValueError("Unknown bid fields")
    lines = payload.get("lines")
    if not isinstance(lines, list) or not 1 <= len(lines) <= 100:
        raise ValueError("Enter between 1 and 100 bid lines")
    normalized = []
    for i, line in enumerate(lines):
        if not isinstance(line, dict) or set(line) != {
            "description",
            "category",
            "quantity",
            "unit_price",
            "taxable",
        }:
            raise ValueError("Invalid bid line")
        quantity = decimal(line["quantity"], maximum=1_000_000)
        if quantity == 0 or quantity != quantity.quantize(Decimal("0.000001")):
            raise ValueError("Quantity must be positive with up to six decimal places")
        unit_price = money(line["unit_price"])
        amount = int((quantity * unit_price).quantize(Decimal(1), rounding=ROUND_HALF_EVEN))
        basis = required(payload.get("basis"))
        validated = BidPriceLine(
            line_key=str(i + 1),
            description=required(line["description"]),
            pricing_basis=basis,
            amount_minor=amount,
        )
        if line["category"] not in CATEGORIES or type(line["taxable"]) is not bool:
            raise ValueError("Choose a category and taxable flag")
        normalized.append(
            {
                **line,
                "quantity": str(quantity),
                "unit_price_minor": unit_price,
                "amount_minor": validated.amount_minor,
            }
        )
    subtotal = sum(line["amount_minor"] for line in normalized)
    if subtotal > 100_000_000_000:
        raise ValueError("Bid subtotal exceeds supported bounds")
    markup, tax = (
        decimal(payload.get("markup"), maximum=100),
        decimal(payload.get("tax"), maximum=100),
    )
    markup_minor = int((subtotal * markup / 100).quantize(Decimal(1), rounding=ROUND_HALF_EVEN))
    tax_basis = payload.get("tax_basis")
    if tax_basis not in ("taxable_lines", "subtotal_and_markup"):
        raise ValueError("Choose a tax basis")
    taxable = (
        sum(line["amount_minor"] for line in normalized if line["taxable"])
        if tax_basis == "taxable_lines"
        else subtotal + markup_minor
    )
    tax_minor = int((taxable * tax / 100).quantize(Decimal(1), rounding=ROUND_HALF_EVEN))
    status = payload.get("status")
    if status not in ("draft", "sent", "won", "lost"):
        raise ValueError("Invalid bid status")
    if status == "lost" and payload.get("loss_reason") not in REASONS:
        raise ValueError("Choose the loss reason")
    contract = money(payload.get("contract_value")) if status == "won" else None
    if status == "won" and not contract:
        raise ValueError("Won bids require the actual contract value")
    return {
        "title": required(payload.get("title"), limit=500),
        "prepared_for": required(payload.get("prepared_for"), limit=500),
        "scope": required(payload.get("scope"), limit=10000),
        "basis": required(payload.get("basis")),
        "lines": normalized,
        "subtotal_minor": subtotal,
        "markup": str(markup),
        "tax": str(tax),
        "markup_minor": markup_minor,
        "tax_minor": tax_minor,
        "tax_basis": tax_basis,
        "total_minor": subtotal + markup_minor + tax_minor,
        "status": status,
        "contract_minor": contract,
        "loss_reason": payload.get("loss_reason"),
        "source": "Entered by user",
        "currency": "USD",
    }


def save_bid(directory: Path, row: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    data = normalize(payload)
    initialize(directory)
    bid_id = payload.get("id") or str(uuid.uuid4())
    if not isinstance(bid_id, str) or len(bid_id) > 100:
        raise ValueError("Invalid bid ID")
    expected = payload.get("expected_version", 0)
    if type(expected) is not int or expected < 0:
        raise ValueError("Invalid expected version")
    with connect(directory) as db:
        db.execute("BEGIN IMMEDIATE")
        prior = db.execute(
            "SELECT * FROM cc_bids WHERE id=? ORDER BY version DESC LIMIT 1", (bid_id,)
        ).fetchone()
        if (prior and prior["key"] != row["source_key"]) or expected != (
            prior["version"] if prior else 0
        ):
            raise ValueError("Bid changed; reload before saving")
        data.update(id=bid_id, version=expected + 1, source_key=row["source_key"], at=now())
        db.execute(
            "INSERT INTO cc_bids VALUES (?,?,?,?,?,?)",
            (
                bid_id,
                data["version"],
                row["source_key"],
                data["at"],
                json.dumps(data),
                fingerprint(data),
            ),
        )
        if data["status"] != "draft":
            status = {"sent": "Quoted", "won": "Won", "lost": "Lost"}[data["status"]]
            f = row.get("feedback", {})
            db.execute(
                "INSERT INTO feedback VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(source_key) "
                "DO UPDATE SET status=excluded.status,reason_code=excluded.reason_code,"
                "updated_at=excluded.updated_at,score_at_update=excluded.score_at_update,"
                "project_type_at_update=excluded.project_type_at_update",
                (
                    row["source_key"],
                    status,
                    f.get("notes") or "",
                    f.get("last_contacted"),
                    data["loss_reason"] if status == "Lost" else None,
                    f.get("reason_text") or "",
                    now(),
                    f.get("score_at_update") if f.get("status") == status else row["security_fit"],
                    f.get("project_type_at_update")
                    if f.get("status") == status
                    else row["project_type"],
                ),
            )
            db.execute(
                "INSERT INTO feedback_events(source_key,changed_at,status,score,project_type) "
                "VALUES (?,?,?,?,?)",
                (row["source_key"], now(), status, row["security_fit"], row["project_type"]),
            )
            if status in ("Won", "Lost"):
                db.execute("DELETE FROM outreach_queue WHERE source_key=?", (row["source_key"],))
    return data


def bids(directory: Path, bid_id: str | None = None) -> list[dict[str, Any]]:
    initialize(directory)
    with connect(directory) as db:
        records = db.execute("SELECT * FROM cc_bids ORDER BY at DESC").fetchall()
    result, seen = [], set()
    for row in records:
        data = json.loads(row["data"])
        if fingerprint(data) != row["digest"]:
            raise ValueError("Bid content hash mismatch")
        if bid_id is not None:
            if row["id"] == bid_id:
                result.append(data)
        elif row["id"] not in seen:
            seen.add(row["id"])
            result.append(data)
    return result


def prices(directory: Path) -> list[dict[str, Any]]:
    initialize(directory)
    with connect(directory) as db:
        return [json.loads(row["data"]) for row in db.execute("SELECT * FROM cc_prices")]


def save_price(directory: Path, payload: dict[str, Any]) -> dict[str, Any]:
    if set(payload) - {"id", "description", "category", "unit", "unit_price", "basis"}:
        raise ValueError("Unknown price-book field")
    data = {
        "id": payload.get("id") or str(uuid.uuid4()),
        "description": required(payload.get("description")),
        "unit": required(payload.get("unit")),
        "basis": required(payload.get("basis")),
        "unit_price_minor": money(payload.get("unit_price")),
        "category": payload.get("category"),
        "source": "Entered by user",
        "at": now(),
    }
    if data["category"] not in CATEGORIES or not isinstance(data["id"], str):
        raise ValueError("Invalid price-book entry")
    initialize(directory)
    with connect(directory) as db:
        db.execute("INSERT OR REPLACE INTO cc_prices VALUES (?,?)", (data["id"], json.dumps(data)))
    return data


def contract(directory: Path, payload: dict[str, Any]) -> dict[str, Any]:
    if set(payload) != {"bid_id", "partner", "percent", "terms"}:
        raise ValueError("Contract requires bid, partner, share percent and terms")
    initialize(directory)
    rate = share_rate_ppm_units(decimal(payload["percent"], maximum=100) / 100)
    partner, terms = required(payload["partner"]), required(payload["terms"], limit=10000)
    with connect(directory) as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute(
            "SELECT data,digest FROM cc_bids WHERE id=? ORDER BY version DESC LIMIT 1",
            (required(payload["bid_id"]),),
        ).fetchone()
        if row is None:
            raise ValueError("Unknown bid")
        bid = json.loads(row["data"])
        if fingerprint(bid) != row["digest"] or bid["status"] != "won":
            raise ValueError("Royalty terms require a verified won bid")
        data = {
            "id": str(uuid.uuid4()),
            "bid_id": bid["id"],
            "bid_version": bid["version"],
            "source_key": bid["source_key"],
            "contract_minor": bid["contract_minor"],
            "rate_ppm": rate,
            "partner": partner,
            "terms": terms,
            "at": now(),
            "calculated_minor": calculate_share_minor_units(bid["contract_minor"], rate),
            "source": "Entered by user",
        }
        try:
            db.execute(
                "INSERT INTO cc_contracts VALUES (?,?,?)", (data["id"], bid["id"], json.dumps(data))
            )
        except sqlite3.IntegrityError as exc:
            raise ValueError("Royalty terms already recorded for this bid") from exc
    return data


def ledger(directory: Path) -> list[dict[str, Any]]:
    initialize(directory)
    with connect(directory) as db:
        contracts = [json.loads(r["data"]) for r in db.execute("SELECT * FROM cc_contracts")]
        entries = [dict(r) for r in db.execute("SELECT * FROM cc_ledger ORDER BY at")]
    for item in contracts:
        item["entries"] = [r for r in entries if r["contract"] == item["id"]]
        invoice = received = 0
        by_id = {r["id"]: r for r in item["entries"]}
        for entry in item["entries"]:
            kind = by_id[entry["reverses"]]["kind"] if entry["reverses"] else entry["kind"]
            if kind == "invoiced":
                invoice += entry["amount"]
            elif kind == "received":
                received += entry["amount"]
        item.update(
            invoiced_minor=invoice,
            received_minor=received,
            receivable_minor=max(0, invoice - received),
            credit_minor=max(0, received - invoice),
        )
    return contracts


def transaction(directory: Path, payload: dict[str, Any]) -> dict[str, Any]:
    if set(payload) - {"contract_id", "kind", "amount", "reference", "reverses"}:
        raise ValueError("Unknown royalty entry fields")
    initialize(directory)
    key, kind = required(payload.get("contract_id")), payload.get("kind")
    if kind not in ("invoiced", "received", "reversal"):
        raise ValueError("Invalid royalty entry kind")
    ref = required(payload.get("reference"))
    with connect(directory) as db:
        db.execute("BEGIN IMMEDIATE")
        if not db.execute("SELECT 1 FROM cc_contracts WHERE id=?", (key,)).fetchone():
            raise ValueError("Unknown contract")
        reverses = payload.get("reverses") if kind == "reversal" else None
        if kind == "reversal":
            original = db.execute(
                "SELECT * FROM cc_ledger WHERE id=? AND contract=?", (required(reverses), key)
            ).fetchone()
            if (
                not original
                or original["reverses"]
                or db.execute("SELECT 1 FROM cc_ledger WHERE reverses=?", (reverses,)).fetchone()
            ):
                raise ValueError("Entry is missing or already reversed")
            amount = -original["amount"]
        else:
            amount = money(payload.get("amount"))
            if not amount:
                raise ValueError("Amount must be positive")
        data = {
            "id": str(uuid.uuid4()),
            "contract": key,
            "at": now(),
            "kind": kind,
            "amount": amount,
            "reference": ref,
            "reverses": reverses,
        }
        db.execute("INSERT INTO cc_ledger VALUES (?,?,?,?,?,?,?)", tuple(data.values()))
    return data


def proposal_pdf(bid: dict[str, Any], company: str) -> bytes:
    """A printable document from the persisted version, with no invented customer facts."""
    out = io.BytesIO()
    with FONT_LOCK:
        if "CSRoboto" not in pdfmetrics.getRegisteredFontNames():
            fonts = Path(__file__).parent / "command_center/fonts"
            pdfmetrics.registerFont(TTFont("CSRoboto", str(fonts / "roboto-400.ttf")))
            pdfmetrics.registerFont(TTFont("CSRobotoBold", str(fonts / "roboto-700.ttf")))
    styles = getSampleStyleSheet()
    for name in ("Normal", "BodyText", "Title", "Heading1", "Heading2"):
        style = styles[name]
        style.fontName = "CSRobotoBold" if style.fontName == "Helvetica-Bold" else "CSRoboto"
    normal = styles["BodyText"]
    story: list[Any] = [
        Paragraph(escape(company or "Proposal"), styles["Title"]),
        Paragraph(escape(bid["title"]), styles["Heading1"]),
        Paragraph(f"Prepared for: {escape(bid['prepared_for'])}", normal),
        Paragraph(f"Version {bid['version']} | Status: {bid['status']} | USD", normal),
        Spacer(1, 16),
        Paragraph("Scope", styles["Heading2"]),
        Paragraph(escape(bid["scope"]).replace("\n", "<br/>"), normal),
        Spacer(1, 16),
    ]
    cells: list[list[Any]] = [["Description", "Qty", "Unit price", "Amount"]]
    for line in bid["lines"]:
        cells.append(
            [
                Paragraph(escape(line["description"]), normal),
                line["quantity"],
                f"${line['unit_price_minor'] / 100:,.2f}",
                f"${line['amount_minor'] / 100:,.2f}",
            ]
        )
    for label, key in (
        ("Subtotal", "subtotal_minor"),
        ("Markup", "markup_minor"),
        ("Tax", "tax_minor"),
        ("Total", "total_minor"),
    ):
        cells.append([label, "", "", f"${bid[key] / 100:,.2f}"])
    table = Table(cells, colWidths=[275, 45, 100, 100], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eee4d1")),
                ("FONTNAME", (0, 0), (-1, -1), "CSRoboto"),
                ("FONTNAME", (0, 0), (-1, 0), "CSRobotoBold"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.grey),
            ]
        )
    )
    story += [
        table,
        Spacer(1, 16),
        Paragraph("Pricing basis", styles["Heading2"]),
        Paragraph(escape(bid["basis"]), normal),
        Paragraph(f"Tax basis: {escape(bid['tax_basis'])}", normal),
    ]
    SimpleDocTemplate(
        out, pagesize=letter, leftMargin=46, rightMargin=46, topMargin=42, bottomMargin=42
    ).build(story)
    return out.getvalue()
