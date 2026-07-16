"""Prepare the assertion-bound alignment correction for local execution.

This helper applies the two command-boundary changes whose source fragments occur more
than once, then removes their duplicate calls from the main correction script. It is
intentionally temporary and should not be included in the durable product commit.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str) -> None:
    content = path.read_text(encoding="utf-8")
    count = content.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one target, found {count}")
    path.write_text(content.replace(old, new, 1), encoding="utf-8")


def remove_block(content: str, start: str, end: str) -> str:
    start_index = content.index(start)
    end_index = content.index(end, start_index)
    return content[:start_index] + content[end_index:]


def main() -> None:
    recurring = ROOT / "src/constructionsight/ceqanet_recurring_run_cli.py"
    replace_once(
        recurring,
        '    """Authorize and execute one exact foreground recurring-run attempt."""\n\n'
        "    definition = _load_model(definition_path, CeqanetRecurringRunDefinition)\n",
        '    """Authorize and execute one exact foreground recurring-run attempt."""\n\n'
        "    if not execute_live:\n"
        "        typer.echo(\n"
        '            "CEQAnet recurring-run execution blocked: caller confirmation is "\n'
        '            "required in addition to scope-bound authority",\n'
        "            err=True,\n"
        "        )\n"
        "        raise typer.Exit(code=1)\n"
        "    definition = _load_model(definition_path, CeqanetRecurringRunDefinition)\n",
    )

    parcel = ROOT / "src/constructionsight/parcel_source_cli.py"
    replace_once(
        parcel,
        '    """Authorize persistence of one exact verified bundle; never authorize bulk."""\n\n'
        "    try:\n"
        "        bundle = load_arcgis_bounded_proof_bundle(input_path)\n",
        '    """Authorize persistence of one exact verified bundle; never authorize bulk."""\n\n'
        "    if not authorize_persistence:\n"
        "        typer.echo(\n"
        '            "ArcGIS bounded-proof persistence blocked: acquisition-persist-bundle "\n'
        '            "requires --authorize-persistence in addition to scope-bound authority",\n'
        "            err=True,\n"
        "        )\n"
        "        raise typer.Exit(code=1)\n"
        "    try:\n"
        "        bundle = load_arcgis_bounded_proof_bundle(input_path)\n",
    )

    script_path = ROOT / "scripts/apply_alignment_baseline_fixes.py"
    script = script_path.read_text(encoding="utf-8")
    script = remove_block(
        script,
        '    replace_once(\n'
        '        "src/constructionsight/ceqanet_recurring_run_cli.py",\n',
        '    replace_once(\n'
        '        "src/constructionsight/operator_services/ceqanet_recurring_run_service.py",\n',
    )
    script = remove_block(
        script,
        '    replace_once(\n'
        '        "src/constructionsight/parcel_source_cli.py",\n',
        "\n\n    # Stale lawful-access assertions",
    )
    script_path.write_text(script, encoding="utf-8")


if __name__ == "__main__":
    main()
