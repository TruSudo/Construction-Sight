"""Structural regressions for the standalone read-only operator presentation."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path


ASSETS = Path(__file__).resolve().parents[1] / "src" / "constructionsight"


class _Structure(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.parents: dict[str, tuple[str, ...]] = {}
        self.stack: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        identifier = attributes.get("id")
        if identifier:
            self.ids.append(identifier)
            self.parents[identifier] = tuple(self.stack)
        if tag not in {"meta", "link", "br", "input", "img", "hr"}:
            self.stack.append(identifier or tag)

    def handle_endtag(self, tag: str) -> None:
        if self.stack:
            self.stack.pop()


def test_map_has_an_independent_workspace_and_collapsible_legend() -> None:
    html = (ASSETS / "operator_ui.html").read_text(encoding="utf-8")
    script = (ASSETS / "operator_ui.js").read_text(encoding="utf-8")
    stylesheet = (ASSETS / "operator_ui.css").read_text(encoding="utf-8")
    structure = _Structure()
    structure.feed(html)
    assert len(structure.ids) == len(set(structure.ids)), "Duplicate HTML element identity"
    for identifier in (
        "records-tab", "map-tab", "workflow-tab", "records-view", "map-view",
        "map-layout", "map-legend-panel", "legend-open", "legend-close",
        "nav-toggle", "map", "map-selection", "detail",
    ):
        assert identifier in structure.parents
    assert "map-view" in structure.parents["map"]
    assert "records-view" not in structure.parents["map"]
    assert "map-view" in structure.parents["map-legend-panel"]
    assert "records-view" in structure.parents["detail"]
    assert "function setNavigationCollapsed(" in script
    assert "function setLegendCollapsed(" in script
    assert "function renderMapSelection(" in script
    assert 'mode === "workflow" ? "workflow" : "records"' in script
    assert "map-layout.legend-collapsed" in stylesheet
    assert "prefers-reduced-motion:reduce" in stylesheet
    assert "No street or county boundary layer" in html


def test_static_element_references_are_present() -> None:
    html = (ASSETS / "operator_ui.html").read_text(encoding="utf-8")
    script = (ASSETS / "operator_ui.js").read_text(encoding="utf-8")
    ids = set(re.findall(r'\bid="([^"]+)"', html))
    dynamic_ids = {
        "inspect-parcels", "preview-candidate", "parcel-candidates",
        "fit-parcel-candidates", "candidate-preview", "entity-related",
        "fit-related", "map-selection-close", "view-map-record",
    }
    references = set(re.findall(r'\$\("([^"]+)"\)', script))
    assert references <= ids | dynamic_ids
