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
        "UNASSESSED", "Stored status, not outreach approval",
        "No monitoring or notifications", "Not deduplicated projects",
    ):
        assert required in html + script
    for endpoint in (
        "/api/snapshot?", "/api/footprint?", "/api/workflows?",
        "/api/health", "/api/workflow-summary",
    ):
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
    assert "const items = records();" in script
    assert "const items = records().slice(0,7);" not in script
    assert "identity(r)===identity(p)" in script
    assert "identity(r)===focusIdentity" in script
    assert "newPage.total!==newFootprint.matching_total" in script
    assert '"/api/candidate-preview?"' in script
    assert '"/api/parcel-candidates?"' in script
    assert "parcels.source_record_id===row.record_id" in script
    assert "parcels.linked_site_verified===false" in script
    assert '"/api/entity-neighborhood?"' in script
    assert "JSON.stringify(result.source_record)!==JSON.stringify(row)" in script
    assert "neighborhood.entity_key!==key" in script
    assert "source_scan_truncated" in script and "matching_records_truncated" in script
    assert "read-only" in script.lower()
    for identifier in ("workflow-ready", "workflow-review", "workflow-hold"):
        assert f'id="{identifier}"' in html
    assert "workflowStatus.total===newWorkflow.total" in script
    assert "workflowStatus.outreach_authorized===false" in script
    assert 'new URLSearchParams({kind:item.kind,county:item.county,limit:"1",offset:"0"})' in script
    assert "sanBernardino+riverside>all" in script
    assert "Other / unknown" in script
    assert "commercial_lead_created" not in script
    assert "fetch(url,{cache:\"no-store\"})" in script
    assert "rel=\"noopener noreferrer\"" in script
    assert '["http:", "https:"]' in script


def test_ai_center_is_dedicated_opt_in_surface_with_no_hidden_ai_dependency() -> None:
    """Reserve visible and passive AI separately without implying a live model."""
    html = (ASSETS / "operator_command_center.html").read_text(encoding="utf-8")
    script = (ASSETS / "operator_command_center.js").read_text(encoding="utf-8")
    original_sections = (
        "Command Center", "Project Intelligence", "Site Map", "Entity Network",
        "Evidence Chains", "Lead Console", "Outreach", "Bid Studio",
        "Royalty Ledger", "Watchlist", "Sources &amp; Collection",
    )
    assert all(section in html for section in original_sections)
    assert html.index("Sources &amp; Collection") < html.index("AI AUGMENTATION")
    assert 'data-section="ai"' in html
    assert 'AI Center <span class="nav-count ai-off-indicator">OFF</span>' in html
    assert 'if(name==="ai")' in script
    for indicator in (
        "AI OFF", "NO MODEL CONNECTED", "AI Research Assistant",
        "Ambient Intelligence", "Remote data transmission: disabled",
        "No monitoring, alerts or AI suggestions are running.",
        "There is no live model selector or enable switch yet.",
    ):
        assert indicator in script
    # No assistant call, inferred authority or provider network endpoint is introduced.
    assert "fetch(\"/api/ai" not in script
    assert "openai.com" not in script.lower()
    assert "outreach, bids, payments" in script


def test_lead_console_reads_exact_persisted_workflows_not_unqualified_sources() -> None:
    """The Command Center now offers bounded workflow history without authorizing outreach."""
    html = (ASSETS / "operator_command_center.html").read_text(encoding="utf-8")
    script = (ASSETS / "operator_command_center.js").read_text(encoding="utf-8")
    assert 'data-section="leads"' in html
    assert 'if(name==="leads")' in script
    assert '"/api/workflows?"' in script
    assert 'new URLSearchParams({limit:"25",offset:String(offset)})' in script
    assert "data.read_only!==true" in script
    assert "ids.has(row.workflow_id)" in script
    assert "row.package_id" in script and "row.base_candidate_id" in script
    assert 'id="leads-prev"' in script and 'id="leads-next"' in script
    assert "workflowDetails(row)" in script
    assert "does not independently verify" in script
    assert "No synthetic lead records were substituted" in script
    assert "outreach or submit a bid" in script


def test_royalty_panel_uses_real_revisioned_results_without_claiming_payment() -> None:
    """UI must distinguish a stored share calculation from verified royalty entitlement."""
    html = (ASSETS / "operator_command_center.html").read_text(encoding="utf-8")
    script = (ASSETS / "operator_command_center.js").read_text(encoding="utf-8")
    assert 'data-section="royalty"' in html
    assert 'if(name==="royalty")' in script
    assert '"/api/results?"' in script
    assert 'new URLSearchParams({limit:"25",offset:String(offset)})' in script
    assert "data.payment_status_verified!==false" in script
    assert "data.royalty_entitlement_verified!==false" in script
    assert 'id="results-prev"' in script and 'id="results-next"' in script
    assert "entry.history[entry.history.length-1].ledger_id" in script
    assert "previous corrected revisions must not be summed" in script.lower()
    assert "No royalty entitlement, payment, outstanding balance" in script
    assert "No payout, balance, or synthetic result was substituted" in script


def test_local_source_revision_refreshes_dashboard_without_remote_ai_or_collection() -> None:
    """External SQLite writes become visible without introducing an operator write route."""
    script = (ASSETS / "operator_command_center.js").read_text(encoding="utf-8")
    assert 'fetchJson("/api/source-revision")' in script
    assert 'window.setInterval(refreshAfterExternalSourceChange,90_000)' in script
    assert "document.visibilityState" in script
    assert 'byId("command-view").hidden' in script
    assert "sourceProbeActive" in script
    assert "sourceRevision!==null" in script
    assert "state.live_collection_enabled!==false" in script
    assert "const previousSelection=selected, previousOffset=pageOffset" in script
    assert "loadData(previousOffset,previousSelection)" in script
    assert "Remote collection is not running" in script
    assert "window.fetch(" not in script


def test_command_center_source_and_county_filters_share_exact_list_map_scope() -> None:
    """Source-family/county controls must constrain list, map, and pagination together."""
    html = (ASSETS / "operator_command_center.html").read_text(encoding="utf-8")
    script = (ASSETS / "operator_command_center.js").read_text(encoding="utf-8")
    for fragment in (
        'id="filter-kind"', 'id="filter-county"',
        '<option value="ceqa">CEQA</option>',
        '<option value="permit">Permits</option>',
        '<option value="San Bernardino">San Bernardino</option>',
        '<option value="Riverside">Riverside</option>',
    ):
        assert fragment in html
    assert 'let activeKind = "all", activeCounty = "";' in script
    assert 'kind:activeKind,county:activeCounty,limit:"50",offset:String(offset),q:activeQuery' in script
    assert 'kind:activeKind,county:activeCounty,q:activeQuery' in script
    assert 'newPage.selection!==activeKind || newFootprint.selection!==activeKind' in script
    assert 'for (const id of ["filter-kind","filter-county"])' in script
    assert 'data-source-kind="' in script and 'data-source-county="' in script
    assert 'applySourceFilter(kind,county)' in script
    assert 'button.dataset.sourceKind, county=button.dataset.sourceCounty' in script
    assert 'pageOffset=0;showHome();loadData(0);' in script


def test_watchlist_bookmark_opens_fresh_exact_source_not_cached_display_text() -> None:
    """A local bookmark resolves a current, exact database record without writing or alerting."""
    script = (ASSETS / "operator_command_center.js").read_text(encoding="utf-8")
    assert 'data-open="' in script
    assert 'openWatchBookmark(currentKey)' in script
    assert 'new URLSearchParams({kind:entry.record_kind,record_id:entry.record_id})' in script
    assert 'fetchJson("/api/candidate-preview?" + params)' in script
    assert 'identity(row) !== key || result.read_only !== true' in script
    assert 'token !== featureRequest || byId("command-view").hidden' in script
    assert 'No cached source facts were substituted.' in script
    assert 'Bookmark is not monitoring or outreach approval.' in script
    assert 'fetch(url,{cache:"no-store"})' in script


def test_source_activity_uses_existing_bounded_historical_read_api() -> None:
    """Historical pulse must stay scoped, provenance-labeled and read-only."""
    script = (ASSETS / "operator_command_center.js").read_text(encoding="utf-8")
    assert 'id="show-historical-pulse"' in script
    assert 'byId("show-historical-pulse").onclick=showHistoricalPulse' in script
    assert '"/api/timeline?"+new URLSearchParams({kind,county,q:query})' in script
    assert 'data.read_only!==true || data.live_collection_enabled!==false' in script
    assert 'data.selection!==kind' in script
    assert 'data.returned_events!==data.events.length' in script
    assert 'data.source_scan_truncated!==(data.matching_total>data.records_scanned)' in script
    assert "Historical source-claimed dates are not evidence of current site activity" in script
    assert 'data.event_result_truncated?' in script
    assert "source_date_order_conflict" in script
