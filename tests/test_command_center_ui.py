"""Read-only Command Center layout and route regressions."""
from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path

from constructionsight.operator_web import _ASSETS

ASSETS = Path(__file__).resolve().parents[1] / "src" / "constructionsight"


class _Ids(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        identifier = dict(attrs).get("id")
        if identifier is not None:
            self.ids.append(identifier)


def test_command_center_is_default_with_legacy_workspace_preserved() -> None:
    assert _ASSETS["/"][0] == "operator_command_center.html"
    assert _ASSETS["/workspace"][0] == "operator_ui.html"
    assert _ASSETS["/operator_brand.webp"][1] == "image/webp"
    for path in (
        "operator_brand.webp",
        "operator_command_center.html",
        "operator_command_center.css",
        "operator_command_center.js",
        "operator_ui.html",
        "operator_ui.js",
    ):
        assert (ASSETS / path).is_file()


def test_approved_shell_and_all_sidebar_destinations_are_present() -> None:
    html = (ASSETS / "operator_command_center.html").read_text(encoding="utf-8")
    parser = _Ids()
    parser.feed(html)
    assert len(parser.ids) == len(set(parser.ids))
    for marker in (
        "Command Center",
        "Project Intelligence",
        "Site Map",
        "Entity Network",
        "Evidence Chains",
        "Lead Console",
        "Outreach",
        "Bid Studio",
        "Royalty Ledger",
        "Watchlist",
        "Sources &amp; Collection",
        'id="command-map"',
        'id="command-dossier"',
        'id="command-records"',
        'id="watchlist-summary"',
        'src="/operator_brand.webp"',
    ):
        assert marker in html
    for route in ("/workspace#records", "/workspace#map", "/workspace#workflow"):
        assert route in html
    assert "Synthetic chain fixture" not in html


def test_command_center_discloses_unassessed_records_and_missing_actions() -> None:
    html = (ASSETS / "operator_command_center.html").read_text(encoding="utf-8")
    script = (ASSETS / "operator_command_center.js").read_text(encoding="utf-8")
    for required in (
        "UNASSESSED", "Readiness not yet evaluated",
        "No monitoring or notifications", "Not deduplicated projects",
    ):
        assert required in html + script
    for endpoint in ("/api/snapshot?", "/api/footprint?", "/api/workflows?", "/api/health"):
        assert endpoint in script
    assert "source claims" in script.lower()
    assert "localStorage" in script
    assert not re.search(r'\b(247|104|86|57)\b', html)


def test_legacy_workspace_can_open_links_from_canonical_sidebar() -> None:
    old = (ASSETS / "operator_ui.js").read_text(encoding="utf-8")
    old_html = (ASSETS / "operator_ui.html").read_text(encoding="utf-8")
    assert '"hashchange"' in old
    assert '"records", "map", "workflow"' in old
    assert 'href="/"' in old_html


def test_command_center_exact_source_navigation_and_paging_contract() -> None:
    """All displayed read details come from bounded existing read-only routes."""
    html = (ASSETS / "operator_command_center.html").read_text(encoding="utf-8")
    script = (ASSETS / "operator_command_center.js").read_text(encoding="utf-8")
    parser = _Ids()
    parser.feed(html)
    assert len(parser.ids) == len(set(parser.ids))
    assert 'id="previous-records"' in html and 'id="next-records"' in html
    assert "Math.floor(p.ordinal/50)*50" in script
    assert "identity(r)===identity(p)" in script
    assert "identity(r)===focusIdentity" in script
    assert "newPage.total!==newFootprint.matching_total" in script
    assert '"/api/candidate-preview?"' in script
    assert '"/api/entity-neighborhood?"' in script
    assert "JSON.stringify(result.source_record)!==JSON.stringify(row)" in script
    assert "neighborhood.entity_key!==key" in script
    assert "source_scan_truncated" in script and "matching_records_truncated" in script
    assert "read-only" in script.lower()
    assert "commercial_lead_created" not in script
    assert "fetch(url,{cache:\"no-store\"})" in script
    assert "rel=\"noopener noreferrer\"" in script
    assert '["http:", "https:"]' in script
