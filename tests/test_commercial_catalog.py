import json
from pathlib import Path

import pytest

from constructionsight import command_center_commercial as commercial
from constructionsight import commercial_catalog as catalog
from constructionsight.lead_workflow import connect


def test_scope_revision_conflict_and_retained_text(tmp_path: Path) -> None:
    scopes = catalog.current(tmp_path, "scope")
    assert {s["service"] for s in scopes} == set(commercial.SCOPES)
    original = next(s for s in scopes if s["name"] == "CCTV")
    payload = {
        "id": original["id"],
        "expected_version": 1,
        "name": "CCTV",
        "service": "CCTV",
        "body": "Operator-reviewed camera commissioning scope",
    }
    saved = catalog.save_scope(tmp_path, payload)
    assert saved["version"] == 2
    assert catalog.scopes(tmp_path)["CCTV"] == payload["body"]
    assert catalog.history(tmp_path, "scope", original["id"])[1]["body"] == original["body"]
    with pytest.raises(ValueError, match="changed since edit"):
        catalog.save_scope(tmp_path, payload)
    with pytest.raises(ValueError, match="already uses"):
        catalog.save_scope(tmp_path, {**payload, "id": "other", "expected_version": 0})


def test_price_migration_exact_money_edit_and_history(tmp_path: Path) -> None:
    commercial.initialize(tmp_path)
    original = {
        "id": "legacy",
        "description": "Operator price",
        "unit": "each",
        "basis": "Operator supplied quote",
        "unit_price_minor": 1234,
        "category": "equipment",
        "source": "Entered by user",
        "at": "2026-01-01",
    }
    with connect(tmp_path) as db:
        db.execute("INSERT INTO cc_prices VALUES (?,?)", ("legacy", json.dumps(original)))
    migrated = commercial.prices(tmp_path)[0]
    assert migrated["version"] == 1 and migrated["service"] is None
    payload = {
        "id": "legacy",
        "expected_version": 1,
        "description": "Operator revised price",
        "unit": "each",
        "basis": "New operator quote",
        "unit_price": "12.35",
        "category": "equipment",
        "service": "Access control",
    }
    saved = commercial.save_price(tmp_path, payload)
    assert saved["version"] == 2 and saved["unit_price_minor"] == 1235
    assert catalog.history(tmp_path, "price", "legacy")[1]["description"] == original["description"]
    with pytest.raises(ValueError, match="changed since edit"):
        commercial.save_price(tmp_path, payload)
    assert commercial.prices(tmp_path)[0] == saved
