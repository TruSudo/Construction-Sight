"""Apply the exact mutable-Action scanner correction from the retained regression."""

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
        "src/constructionsight/dependency_certification.py",
        "    action_pattern = re.compile(\n"
        "        r\"^(?P<indent>\\s*)uses:\\s*(?P<action>[^@\\s]+)@\"\n"
        "        r\"(?P<ref>[^\\s#]+)(?P<comment>.*)$\"\n"
        "    )\n",
        "    action_pattern = re.compile(\n"
        "        r\"^(?P<indent>\\s*)(?:-\\s*)?uses:\\s*(?P<action>[^@\\s]+)@\"\n"
        "        r\"(?P<ref>[^\\s#]+)(?P<comment>.*)$\"\n"
        "    )\n",
    )

    for relative in (
        "governance/diagnostics/static_ruff.txt",
        "governance/diagnostics/static_regressions.txt",
    ):
        diagnostic = ROOT / relative
        if diagnostic.exists():
            diagnostic.unlink()


if __name__ == "__main__":
    main()
