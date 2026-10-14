from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest

from constructionsight import command_center_commercial as commercial
from constructionsight.live_command_center import projection
from tests.test_command_center_state import snapshot


def payload(**patch: Any) -> dict[str, Any]:
    return {
        "title": "Actual requested scope",
        "prepared_for": "Actual customer",
        "scope": "Reviewed camera scope",
        "basis": "Entered by user: supplier quote",
        "lines": [
            {
                "description": "Cameras",
                "category": "equipment",
                "quantity": "3",
                "unit_price": "0.33",
                "taxable": True,
            }
        ],
        "markup": "10",
        "tax": "9.25",
        "tax_basis": "taxable_lines",
        "status": "draft",
        **patch,
    }


def test_exact_cents_version_binding_and_pdf(tmp_path: Path) -> None:
    lead = projection(snapshot(), tmp_path)["rows"][0]
    bid = commercial.save_bid(tmp_path, lead, payload())
    assert (bid["subtotal_minor"], bid["markup_minor"], bid["tax_minor"], bid["total_minor"]) == (
        99,
        10,
        9,
        118,
    )
    pdf = commercial.proposal_pdf(bid, "Actual company")
    assert pdf.startswith(b"%PDF") and b"%%EOF" in pdf[-20:]
    commercial.save_bid(tmp_path, lead, payload(id=bid["id"], expected_version=1, status="sent"))
    assert len(commercial.bids(tmp_path, bid["id"])) == 2
    assert projection(snapshot(), tmp_path)["rows"][0]["feedback"]["status"] == "Quoted"
    with pytest.raises(ValueError, match="reload"):
        commercial.save_bid(tmp_path, lead, payload(id=bid["id"], expected_version=1))
    with pytest.raises(ValueError, match="reload"):
        commercial.save_bid(
            tmp_path, {**lead, "source_key": "other"}, payload(id=bid["id"], expected_version=2)
        )
    with (
        commercial.connect(tmp_path) as db,
        pytest.raises(sqlite3.IntegrityError, match="immutable"),
    ):
        db.execute("UPDATE cc_bids SET digest='changed'")


def test_calculated_is_not_receivable_and_reversals(tmp_path: Path) -> None:
    lead = projection(snapshot(), tmp_path)["rows"][0]
    bid = commercial.save_bid(tmp_path, lead, payload(status="won", contract_value="1000.00"))
    contract = commercial.contract(
        tmp_path,
        {
            "bid_id": bid["id"],
            "partner": "Actual partner",
            "percent": "5",
            "terms": "Actual agreement",
        },
    )
    assert (
        commercial.ledger(tmp_path)[0]["calculated_minor"],
        commercial.ledger(tmp_path)[0]["receivable_minor"],
    ) == (5000, 0)
    invoice = commercial.transaction(
        tmp_path,
        {"contract_id": contract["id"], "kind": "invoiced", "amount": "25", "reference": "INV-1"},
    )
    receipt = commercial.transaction(
        tmp_path,
        {
            "contract_id": contract["id"],
            "kind": "received",
            "amount": "10",
            "reference": "Receipt-1",
        },
    )
    assert commercial.ledger(tmp_path)[0]["receivable_minor"] == 1500
    commercial.transaction(
        tmp_path,
        {
            "contract_id": contract["id"],
            "kind": "reversal",
            "reverses": receipt["id"],
            "reference": "Returned payment",
        },
    )
    assert commercial.ledger(tmp_path)[0]["received_minor"] == 0
    commercial.transaction(
        tmp_path,
        {
            "contract_id": contract["id"],
            "kind": "reversal",
            "reverses": invoice["id"],
            "reference": "Credit note",
        },
    )
    assert commercial.ledger(tmp_path)[0]["receivable_minor"] == 0
    with pytest.raises(ValueError, match="already reversed"):
        commercial.transaction(
            tmp_path,
            {
                "contract_id": contract["id"],
                "kind": "reversal",
                "reverses": receipt["id"],
                "reference": "Again",
            },
        )
    with pytest.raises(ValueError, match="already recorded"):
        commercial.contract(
            tmp_path,
            {"bid_id": bid["id"], "partner": "Another", "percent": "5", "terms": "Duplicate"},
        )
    assert projection(snapshot(), tmp_path)["rows"][0]["feedback"]["status"] == "Won"


@pytest.mark.parametrize(
    "patch",
    [
        {"markup": "NaN"},
        {"tax": "-1"},
        {"status": "won"},
        {"status": "lost"},
        {"tax_basis": "invented"},
    ],
)
def test_invalid_bid_does_not_persist(tmp_path: Path, patch: dict[str, Any]) -> None:
    lead = projection(snapshot(), tmp_path)["rows"][0]
    with pytest.raises(ValueError):
        commercial.save_bid(tmp_path, lead, payload(**patch))
    assert commercial.bids(tmp_path) == []


def test_price_book_is_real_user_entered_pricing(tmp_path: Path) -> None:
    price = commercial.save_price(
        tmp_path,
        {
            "description": "Camera",
            "category": "equipment",
            "unit": "each",
            "unit_price": "12.34",
            "basis": "Supplier quote",
        },
    )
    assert commercial.prices(tmp_path)[0]["unit_price_minor"] == 1234
    assert price["source"] == "Entered by user"
