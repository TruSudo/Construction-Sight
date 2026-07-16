"""Apply the exact formatter-resistant Ruff corrections from the retained report."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(relative: str, old: str, new: str) -> None:
    path = ROOT / relative
    content = path.read_text(encoding="utf-8")
    count = content.count(old)
    if count != 1:
        raise RuntimeError(f"{relative}: expected one replacement target, found {count}")
    path.write_text(content.replace(old, new, 1), encoding="utf-8")


def main() -> None:
    replace_once(
        "src/constructionsight/governance_certification_core.py",
        "            if isinstance(mode, ast.Constant) and isinstance(mode.value, str):\n"
        "                if any(flag in mode.value for flag in \"wax+\"):\n"
        "                    lines.add(node.lineno)\n",
        "            if (\n"
        "                isinstance(mode, ast.Constant)\n"
        "                and isinstance(mode.value, str)\n"
        "                and any(flag in mode.value for flag in \"wax+\")\n"
        "            ):\n"
        "                lines.add(node.lineno)\n",
    )

    replace_once(
        "src/constructionsight/operator_services/ceqanet_persistence_service.py",
        "    exact_scope = tuple(\n",
        "    operation_ids_digest = authorization_digest(\n"
        "        \"ceqanet-operation-ids\",\n"
        "        {\"ids\": operation_ids},\n"
        "    )\n"
        "    exact_scope = tuple(\n",
    )
    replace_once(
        "src/constructionsight/operator_services/ceqanet_persistence_service.py",
        "                f\"operation-id-digest:{authorization_digest('ceqanet-operation-ids', {'ids': operation_ids})}\",\n",
        "                f\"operation-id-digest:{operation_ids_digest}\",\n",
    )

    replace_once(
        "src/constructionsight/operator_services/ceqanet_recurring_run_service.py",
        '                    "attempt uniqueness is local-process only until a durable attempt ledger exists",\n',
        '                    "attempt uniqueness is local-process only until a durable "\n'
        '                    "attempt ledger exists",\n',
    )
    replace_once(
        "src/constructionsight/operator_services/source_promotion_service.py",
        '            "perform one bounded verification GET per source and build a report-only promotion plan",\n',
        '            "perform one bounded verification GET per source and build a "\n'
        '            "report-only promotion plan",\n',
    )
    replace_once(
        "src/constructionsight/source_verification_checklist_service.py",
        '                    "HTTP evidence does not complete manual query, list, detail, barrier, or terms review",\n',
        '                    "HTTP evidence does not complete manual query, list, detail, "\n'
        '                    "barrier, or terms review",\n',
    )

    diagnostic = ROOT / "governance/diagnostics/static_ruff.txt"
    if diagnostic.exists():
        diagnostic.unlink()


if __name__ == "__main__":
    main()
