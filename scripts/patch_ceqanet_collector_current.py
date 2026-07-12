"""Patch the temporary CEQAnet collector for the current public detail-page vocabulary."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "scripts/collect_ceqanet_source_evidence.py"


def replace_once(old: str, new: str) -> None:
    text = PATH.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one collector patch anchor, found {count}: {old!r}")
    PATH.write_text(text.replace(old, new, 1), encoding="utf-8")


def main() -> None:
    replace_once(
        'DETAIL_MARKERS = ("project title", "lead agency", "document type", "sch")\n',
        'DETAIL_MARKER_GROUPS = {\n'
        '    "sch_number": ("sch number",),\n'
        '    "project_info": ("project info",),\n'
        '    "title": ("title",),\n'
        '    "description": ("description",),\n'
        '    "documents_in_project": ("documents in project",),\n'
        '    "lead_public_agency": ("lead/public agency", "lead agency"),\n'
        '}\n',
    )
    replace_once(
        '        observed_detail_markers = [\n'
        '            marker for marker in DETAIL_MARKERS if marker in detail.text.lower()\n'
        '        ]\n'
        '        if len(observed_detail_markers) < 2:\n'
        '            raise RuntimeError("CEQAnet detail page lacks expected public-record field markers")\n',
        '        detail_text = detail.text.lower()\n'
        '        observed_detail_markers = [\n'
        '            label\n'
        '            for label, variants in DETAIL_MARKER_GROUPS.items()\n'
        '            if any(variant in detail_text for variant in variants)\n'
        '        ]\n'
        '        required_detail_markers = {"sch_number", "project_info", "title", "description"}\n'
        '        if (\n'
        '            not required_detail_markers.issubset(observed_detail_markers)\n'
        '            or len(observed_detail_markers) < 5\n'
        '        ):\n'
        '            raise RuntimeError(\n'
        '                "CEQAnet detail page lacks the current structured public-record marker set: "\n'
        '                f"{observed_detail_markers}"\n'
        '            )\n',
    )


if __name__ == "__main__":
    main()
