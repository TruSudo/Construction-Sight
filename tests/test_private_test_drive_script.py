"""Structural coverage for the isolated private test-drive launcher."""

from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "test-drive.sh"


def test_private_test_drive_loads_registry_without_live_source_verification() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    init = '"$cs_runtime/constructionsight" init-db --database-url "sqlite:///$cs_database"'
    load = (
        '"$cs_runtime/constructionsight" load-sources data/source_registry.seed.json \\\n'
        '    --database-url "sqlite:///$cs_database"'
    )
    apply = '"$cs_runtime/constructionsight-ceqanet-persistence-apply" execute \\\n'

    assert init in script
    assert load in script
    assert apply in script
    assert script.index(init) < script.index(load) < script.index(apply)
    assert "verify-sources" not in script
    assert "Fresh collection" not in script
