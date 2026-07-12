"""Patch the current CEQAnet CSV runtime for strict Windows-1252 replay support."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERVICE_PATH = ROOT / "src/constructionsight/ceqanet_csv_service.py"
CLI_PATH = ROOT / "src/constructionsight/ceqanet_csv_cli.py"


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one runtime anchor in {path}, found {count}: {old!r}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def patch_service() -> None:
    replace_once(
        SERVICE_PATH,
        "from typing import Any\n",
        "from typing import Any, Literal\n",
    )
    replace_once(
        SERVICE_PATH,
        "    try:\n"
        "        text = content.decode(\"utf-8-sig\")\n"
        "    except UnicodeDecodeError as exc:\n"
        "        raise ValueError(\"CEQAnet CSV body must use UTF-8 or UTF-8 with BOM\") from exc\n",
        "    text, encoding = _decode_csv_body(content)\n",
    )
    replace_once(
        SERVICE_PATH,
        "\n    payload = {\n",
        "\n    if encoding == \"windows-1252\":\n"
        "        warnings.append(\n"
        "            \"source body decoded as Windows-1252 after strict UTF-8 failure\"\n"
        "        )\n\n"
        "    payload = {\n",
    )
    replace_once(
        SERVICE_PATH,
        "        \"content_type\": normalized_content_type,\n"
        "        \"byte_length\": len(content),\n",
        "        \"content_type\": normalized_content_type,\n"
        "        \"encoding\": encoding,\n"
        "        \"byte_length\": len(content),\n",
    )
    replace_once(
        SERVICE_PATH,
        "\ndef _validate_sch_number(value: str) -> None:\n",
        "\ndef _decode_csv_body(\n"
        "    content: bytes,\n"
        ") -> tuple[str, Literal[\"utf-8-sig\", \"windows-1252\"]]:\n"
        "    try:\n"
        "        return content.decode(\"utf-8-sig\"), \"utf-8-sig\"\n"
        "    except UnicodeDecodeError:\n"
        "        pass\n"
        "    try:\n"
        "        return content.decode(\"windows-1252\"), \"windows-1252\"\n"
        "    except UnicodeDecodeError as exc:\n"
        "        raise ValueError(\n"
        "            \"CEQAnet CSV body must use UTF-8, UTF-8 with BOM, or Windows-1252\"\n"
        "        ) from exc\n\n\n"
        "def _validate_sch_number(value: str) -> None:\n",
    )


def patch_cli() -> None:
    replace_once(
        CLI_PATH,
        "from constructionsight.ceqanet_csv_live_service import (\n"
        "    execute_ceqanet_csv_live_request,\n"
        "    verify_ceqanet_csv_live_execution,\n"
        ")\n"
        "from constructionsight.ceqanet_csv_service import (\n",
        "from constructionsight.ceqanet_csv_live_service import (\n"
        "    execute_ceqanet_csv_live_request,\n"
        "    verify_ceqanet_csv_live_execution,\n"
        ")\n"
        "from constructionsight.ceqanet_csv_replay_models import CeqanetCsvEncodingReplay\n"
        "from constructionsight.ceqanet_csv_replay_service import (\n"
        "    build_ceqanet_csv_encoding_replay,\n"
        "    verify_ceqanet_csv_encoding_replay,\n"
        ")\n"
        "from constructionsight.ceqanet_csv_service import (\n",
    )
    marker = "\ndef _write_json_file(path: Path, payload: object, *, overwrite: bool) -> None:\n"
    commands = '''\n\n@app.command("replay-execution")\ndef replay_csv_execution(\n    execution_path: Annotated[\n        Path,\n        typer.Argument(help="Path to a retained live CSV execution artifact."),\n    ],\n    output: Annotated[\n        Path,\n        typer.Option("--output", help="Required derived replay JSON output path."),\n    ],\n    max_retained_rows: Annotated[\n        int,\n        typer.Option("--max-retained-rows", min=0),\n    ] = 1_000,\n    overwrite: Annotated[bool, typer.Option("--overwrite")] = False,\n) -> None:\n    """Replay retained response bytes offline using the current CSV parser."""\n\n    try:\n        payload: Any = json.loads(execution_path.read_text(encoding="utf-8"))\n        execution = CeqanetCsvLiveExecution.model_validate(payload)\n        replay = build_ceqanet_csv_encoding_replay(\n            execution,\n            max_retained_rows=max_retained_rows,\n        )\n    except (OSError, ValueError, json.JSONDecodeError) as exc:\n        raise typer.BadParameter(str(exc)) from exc\n    _write_json_file(output, replay.model_dump(mode="json"), overwrite=overwrite)\n    console.print(f"Wrote CEQAnet CSV encoding replay to {output}")\n\n\n@app.command("verify-replay")\ndef verify_csv_replay(\n    execution_path: Annotated[\n        Path,\n        typer.Argument(help="Path to the source live CSV execution artifact."),\n    ],\n    replay_path: Annotated[\n        Path,\n        typer.Argument(help="Path to the derived encoding replay artifact."),\n    ],\n    output: Annotated[\n        Path | None,\n        typer.Option("--output", help="Optional replay verification JSON output path."),\n    ] = None,\n) -> None:\n    """Verify a derived replay against the original retained live response."""\n\n    try:\n        execution_payload: Any = json.loads(\n            execution_path.read_text(encoding="utf-8")\n        )\n        replay_payload: Any = json.loads(replay_path.read_text(encoding="utf-8"))\n        execution = CeqanetCsvLiveExecution.model_validate(execution_payload)\n        replay = CeqanetCsvEncodingReplay.model_validate(replay_payload)\n        verification = verify_ceqanet_csv_encoding_replay(execution, replay)\n    except (OSError, ValueError, json.JSONDecodeError) as exc:\n        raise typer.BadParameter(str(exc)) from exc\n    _emit_json(verification.model_dump(mode="json"), output)\n    if not verification.passed:\n        raise typer.Exit(code=1)\n'''
    text = CLI_PATH.read_text(encoding="utf-8")
    if text.count(marker) != 1:
        raise RuntimeError("expected one CEQAnet CSV CLI replay insertion marker")
    CLI_PATH.write_text(text.replace(marker, commands + marker, 1), encoding="utf-8")


def main() -> None:
    patch_service()
    patch_cli()


if __name__ == "__main__":
    main()
