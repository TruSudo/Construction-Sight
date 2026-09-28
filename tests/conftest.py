from __future__ import annotations

from pathlib import Path

import pytest

import constructionsight.effect_consumption as effect_consumption


@pytest.fixture(autouse=True)
def _isolate_effect_consumption_store(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Keep every test's durable reservations independent."""

    monkeypatch.setattr(
        effect_consumption,
        "_CONSUMPTION_DATABASE_PATH",
        tmp_path / "effect-consumption.sqlite3",
    )
