"""Apply exact static-analysis and certification-mechanism corrections.

This script is intentionally one-shot and assertion-bound. It is removed after the
resulting commit is verified.
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
        "    \"\"\"Return one metadata value without relying on an untyped get method.\"\"\"\n\n"
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
        "def _run_case(root: Path, case: MutationCase, timeout: int) -> MutationResult:\n"
        "    with tempfile.TemporaryDirectory(prefix=\"constructionsight-mutant-\") as directory:\n"
        "        temporary_root = Path(directory)\n"
        "        overlay_src = temporary_root / \"src\"\n"
        "        shutil.copytree(root / \"src/constructionsight\", overlay_src / \"constructionsight\")\n"
        "        target = temporary_root / case.path\n",
        "def _copy_tracked_tree(root: Path, temporary_root: Path) -> None:\n"
        "    completed = subprocess.run(\n"
        "        [\"git\", \"-C\", str(root), \"ls-files\", \"-z\"],\n"
        "        check=False,\n"
        "        capture_output=True,\n"
        "    )\n"
        "    if completed.returncode != 0:\n"
        "        detail = completed.stderr.decode(\"utf-8\", errors=\"replace\")\n"
        "        raise MutationContractError(f\"cannot enumerate tracked tree: {detail}\")\n"
        "    for raw_relative in completed.stdout.split(b\"\\0\"):\n"
        "        if not raw_relative:\n"
        "            continue\n"
        "        relative = Path(raw_relative.decode(\"utf-8\"))\n"
        "        if relative.is_absolute() or \"..\" in relative.parts:\n"
        "            raise MutationContractError(f\"unsafe tracked path: {relative}\")\n"
        "        source = root / relative\n"
        "        if not source.is_file():\n"
        "            raise MutationContractError(f\"tracked file is missing: {relative}\")\n"
        "        destination = temporary_root / relative\n"
        "        destination.parent.mkdir(parents=True, exist_ok=True)\n"
        "        shutil.copy2(source, destination)\n\n\n"
        "def _timeout_output(value: bytes | str | None) -> str:\n"
        "    if value is None:\n"
        "        return \"\"\n"
        "    if isinstance(value, bytes):\n"
        "        return value.decode(\"utf-8\", errors=\"replace\")\n"
        "    return value\n\n\n"
        "def _run_case(root: Path, case: MutationCase, timeout: int) -> MutationResult:\n"
        "    with tempfile.TemporaryDirectory(prefix=\"constructionsight-mutant-\") as directory:\n"
        "        temporary_root = Path(directory)\n"
        "        _copy_tracked_tree(root, temporary_root)\n"
        "        target = temporary_root / case.path\n",
    )
    replace_once(
        "src/constructionsight/mutation_certification.py",
        "        values = [str(overlay_src), str(root / \"src\")]\n",
        "        values = [str(temporary_root / \"src\")]\n",
    )
    replace_once(
        "src/constructionsight/mutation_certification.py",
        "                cwd=root,\n",
        "                cwd=temporary_root,\n",
    )
    replace_once(
        "src/constructionsight/mutation_certification.py",
        '            output = (exc.stdout or "") + (exc.stderr or "")\n',
        "            output = _timeout_output(exc.stdout) + _timeout_output(exc.stderr)\n",
    )

    replace_once(
        "src/constructionsight/ceqanet_csv_live_service.py",
        "    if execution.method != \"GET\":\n"
        "        findings.append(\"live CSV execution method is not GET\")\n"
        "    if execution.retry_count != 0:\n"
        "        findings.append(\"live CSV execution reports a retry\")\n"
        "    if not execution.network_executed:\n"
        "        findings.append(\"live CSV execution does not affirm network execution\")\n"
        "    if execution.documents_downloaded:\n"
        "        findings.append(\"live CSV execution reports CEQA document downloads\")\n"
        "    if execution.persistence_mutated:\n"
        "        findings.append(\"live CSV execution reports persistence mutation\")\n",
        "    runtime_payload = execution.model_dump(mode=\"python\")\n"
        "    if runtime_payload.get(\"method\") != \"GET\":\n"
        "        findings.append(\"live CSV execution method is not GET\")\n"
        "    if runtime_payload.get(\"retry_count\") != 0:\n"
        "        findings.append(\"live CSV execution reports a retry\")\n"
        "    if runtime_payload.get(\"network_executed\") is not True:\n"
        "        findings.append(\"live CSV execution does not affirm network execution\")\n"
        "    if runtime_payload.get(\"documents_downloaded\") is not False:\n"
        "        findings.append(\"live CSV execution reports CEQA document downloads\")\n"
        "    if runtime_payload.get(\"persistence_mutated\") is not False:\n"
        "        findings.append(\"live CSV execution reports persistence mutation\")\n",
    )

    replace_once(
        "tests/test_ceqanet_csv_evidence_series.py",
        '    assert \'"httpx[socks]>=0.27.0"\' in pyproject\n',
        '    assert \'"httpx[socks]==0.28.1"\' in pyproject\n',
    )


if __name__ == "__main__":
    main()
