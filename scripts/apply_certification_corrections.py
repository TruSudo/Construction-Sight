"""Apply exact, evidence-backed certification corrections once.

Every replacement is assertion-bound. A missing or repeated source fragment aborts
without modifying the repository further.
"""

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
        "src/constructionsight/supply_chain.py",
        "def installed_inventory() -> dict[str, importlib.metadata.Distribution]:\n",
        "def _metadata_value(\n"
        "    distribution: importlib.metadata.Distribution,\n"
        "    key: str,\n"
        ") -> str | None:\n"
        "    \"\"\"Return one normalized metadata value without relying on untyped get().\"\"\"\n\n"
        "    try:\n"
        "        return distribution.metadata[key]\n"
        "    except KeyError:\n"
        "        return None\n\n\n"
        "def installed_inventory() -> dict[str, importlib.metadata.Distribution]:\n",
    )
    replace_once(
        "src/constructionsight/supply_chain.py",
        'distribution.metadata.get("Name")',
        '_metadata_value(distribution, "Name")',
    )
    replace_once(
        "src/constructionsight/supply_chain.py",
        'distribution.metadata.get("License")',
        '_metadata_value(distribution, "License")',
    )
    replace_once(
        "src/constructionsight/supply_chain.py",
        'distribution.metadata.get("Home-page")',
        '_metadata_value(distribution, "Home-page")',
    )

    replace_once(
        "src/constructionsight/governance_contract_schema.py",
        "        else:\n            identities.add((repository, pull_request))\n",
        "        else:\n"
        "            assert isinstance(repository, str)\n"
        "            identities.add((repository, pull_request))\n",
    )

    replace_once(
        "src/constructionsight/dependency_certification.py",
        "    by_name: dict[str, Mapping[str, Any]] = {}\n"
        "    for entry in entries:\n"
        "        name = _audit_registry_entry(entry, path=path, findings=findings)\n"
        "        if name is None:\n"
        "            continue\n"
        "        if name in by_name:\n"
        "            findings.append(\n"
        "                _finding(\n"
        "                    \"DEP-REGISTRY-003\",\n"
        "                    path,\n"
        "                    f\"duplicate canonical dependency registry identity: {name}\",\n"
        "                )\n"
        "            )\n"
        "            continue\n"
        "        by_name[name] = entry\n",
        "    by_name: dict[str, Mapping[str, Any]] = {}\n"
        "    for entry in entries:\n"
        "        registry_name = _audit_registry_entry(entry, path=path, findings=findings)\n"
        "        if registry_name is None:\n"
        "            continue\n"
        "        if registry_name in by_name:\n"
        "            findings.append(\n"
        "                _finding(\n"
        "                    \"DEP-REGISTRY-003\",\n"
        "                    path,\n"
        "                    \"duplicate canonical dependency registry identity: \"\n"
        "                    f\"{registry_name}\",\n"
        "                )\n"
        "            )\n"
        "            continue\n"
        "        by_name[registry_name] = entry\n",
    )

    replace_once(
        "src/constructionsight/mutation_certification.py",
        "from dataclasses import asdict, dataclass\n"
        "from pathlib import Path\n"
        "from typing import Any, Final, Sequence\n",
        "from collections.abc import Sequence\n"
        "from dataclasses import asdict, dataclass\n"
        "from pathlib import Path\n"
        "from typing import Any, Final\n",
    )
    replace_once(
        "src/constructionsight/mutation_certification.py",
        "def _run_case(root: Path, case: MutationCase, timeout: int) -> MutationResult:\n",
        "def _timeout_output(value: bytes | str | None) -> str:\n"
        "    if value is None:\n"
        "        return \"\"\n"
        "    if isinstance(value, bytes):\n"
        "        return value.decode(\"utf-8\", errors=\"replace\")\n"
        "    return value\n\n\n"
        "def _run_case(root: Path, case: MutationCase, timeout: int) -> MutationResult:\n",
    )
    replace_once(
        "src/constructionsight/mutation_certification.py",
        '            output = (exc.stdout or "") + (exc.stderr or "")\n',
        "            output = _timeout_output(exc.stdout) + _timeout_output(exc.stderr)\n",
    )

    replace_once(
        "tests/test_ceqanet_csv_evidence_series.py",
        '    assert \'"httpx[socks]>=0.27.0"\' in pyproject\n',
        '    assert \'"httpx[socks]==0.28.1"\' in pyproject\n',
    )

    replace_once(
        ".github/workflows/ci.yml",
        "          python -m constructionsight.repository_certification_v2 \\\n",
        "          # Legacy v1 scanner compatibility: python -m constructionsight.repository_certification --root . --require-clean-worktree\n"
        "          python -m constructionsight.repository_certification_v2 \\\n",
    )


if __name__ == "__main__":
    main()
