"""CEQAnet search-result page parsing.

This module parses stored CEQAnet result-page HTML into candidate project
records. It is intentionally offline and conservative: it does not execute
network requests, download documents, or mutate persistence.

Some CEQAnet /Search result rows expose SCH-style identifiers as the visible
link text instead of a human project title. The parser preserves those rows but
marks the title source and enrichment requirement explicitly instead of treating
an identifier as a verified human title.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Literal
from urllib.parse import urljoin

CEQANET_BASE_URL = "https://ceqanet.lci.ca.gov/"

CeqanetResultTitleSource = Literal[
    "human_label",
    "human_link_text",
    "sch_number",
    "link_text",
]

_RESULT_BLOCK_TAGS = {"article", "li", "tr"}
_RESULT_CLASS_HINTS = ("result", "record", "project", "card")
_IGNORED_TAGS = {"script", "style", "select", "option", "noscript"}

_NAV_TEXTS = {
    "",
    "about",
    "advanced search",
    "back to top",
    "ca.gov",
    "close search",
    "contact us",
    "custom google search",
    "home",
    "menu",
    "recent postings",
    "reset search",
    "search",
    "settings",
    "skip to main content",
    "submit",
}

_NAV_HREF_TERMS = (
    "contact",
    "settings",
    "google",
    "javascript:",
    "mailto:",
)

_RESULT_HREF_TERMS = (
    "document",
    "project",
    "details",
    "sch",
)

_RESULT_TEXT_SIGNALS = (
    "SCH Number",
    "Lead Agency",
    "Lead/Public Agency",
    "Document Type",
    "County",
    "Project Title",
    "Project Name",
    "Project Description",
    "Document Description",
    "CEQA",
)

_PROJECT_TITLE_LABELS = (
    "Project Title",
    "Project Name",
    "Project Description",
    "Document Description",
    "Description",
)

_GENERIC_LINK_TEXTS = {
    "details",
    "documents",
    "project details",
    "read more",
    "view",
    "view details",
    "view documents",
}

_SCH_PATTERN = re.compile(r"\b\d{7,}\b")


@dataclass(frozen=True)
class _TitleCandidate:
    title: str
    source: CeqanetResultTitleSource


@dataclass(frozen=True)
class CeqanetSearchResultRecord:
    """One parsed CEQAnet project/search-result record."""

    title: str
    detail_url: str
    sch_number: str | None = None
    document_type: str | None = None
    lead_agency: str | None = None
    county: str | None = None
    city: str | None = None
    source_url: str | None = None
    raw_text: str = ""
    title_source: CeqanetResultTitleSource = "link_text"
    requires_detail_enrichment: bool = False

    def to_dict(self) -> dict[str, str | bool | None]:
        """Return a JSON-safe representation of the parsed record."""

        return {
            "title": self.title,
            "detail_url": self.detail_url,
            "sch_number": self.sch_number,
            "document_type": self.document_type,
            "lead_agency": self.lead_agency,
            "county": self.county,
            "city": self.city,
            "source_url": self.source_url,
            "raw_text": self.raw_text,
            "title_source": self.title_source,
            "requires_detail_enrichment": self.requires_detail_enrichment,
        }


@dataclass(frozen=True)
class CeqanetResultPageParse:
    """Parsed CEQAnet result page with audit metadata."""

    records: tuple[CeqanetSearchResultRecord, ...]
    source_url: str | None
    candidate_block_count: int
    candidate_link_count: int

    @property
    def record_count(self) -> int:
        """Return parsed result-record count."""

        return len(self.records)

    @property
    def detail_enrichment_required_count(self) -> int:
        """Return count of records whose title needs detail-page enrichment."""

        return sum(record.requires_detail_enrichment for record in self.records)

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-safe representation of the parse report."""

        return {
            "metadata": {
                "schema_version": "ceqanet_result_page_parse.v1",
                "source_url": self.source_url,
                "record_count": self.record_count,
                "candidate_block_count": self.candidate_block_count,
                "candidate_link_count": self.candidate_link_count,
                "detail_enrichment_required_count": self.detail_enrichment_required_count,
            },
            "records": [record.to_dict() for record in self.records],
        }


@dataclass
class _ParsedLink:
    text: str
    href: str


@dataclass
class _ParsedBlock:
    tag: str
    attrs: dict[str, str]
    text_parts: list[str]
    links: list[_ParsedLink]

    @property
    def raw_text(self) -> str:
        """Return normalized block text with label boundaries preserved."""

        return " | ".join(part for part in self.text_parts if part)


class _CeqanetResultHtmlParser(HTMLParser):
    """Internal parser collecting result-like blocks and links."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[_ParsedBlock] = []
        self.links: list[_ParsedLink] = []
        self._current_block: _ParsedBlock | None = None
        self._block_depth = 0
        self._link_href: str | None = None
        self._link_text_parts: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Track result-like containers and anchors."""

        normalized_tag = tag.lower()
        attrs_by_name = {name: value or "" for name, value in attrs}

        if normalized_tag in _IGNORED_TAGS:
            self._ignored_depth += 1
            return

        if self._ignored_depth:
            return

        if self._current_block is None and _is_result_block_start(
            normalized_tag,
            attrs_by_name,
        ):
            self._current_block = _ParsedBlock(
                tag=normalized_tag,
                attrs=attrs_by_name,
                text_parts=[],
                links=[],
            )
            self._block_depth = 1
        elif self._current_block is not None:
            self._block_depth += 1

        if normalized_tag == "a":
            self._link_href = attrs_by_name.get("href", "")
            self._link_text_parts = []

    def handle_data(self, data: str) -> None:
        """Collect normalized visible text."""

        if self._ignored_depth:
            return

        text = _normalize_text(data)
        if not text:
            return

        if self._current_block is not None:
            self._current_block.text_parts.append(text)

        if self._link_href is not None:
            self._link_text_parts.append(text)

    def handle_endtag(self, tag: str) -> None:
        """Finalize anchors and result-like blocks."""

        normalized_tag = tag.lower()

        if normalized_tag in _IGNORED_TAGS:
            if self._ignored_depth:
                self._ignored_depth -= 1
            return

        if self._ignored_depth:
            return

        if normalized_tag == "a" and self._link_href is not None:
            link = _ParsedLink(
                text=_normalize_text(" ".join(self._link_text_parts)),
                href=self._link_href.strip(),
            )
            self.links.append(link)
            if self._current_block is not None:
                self._current_block.links.append(link)
            self._link_href = None
            self._link_text_parts = []

        if self._current_block is not None:
            self._block_depth -= 1
            if self._block_depth <= 0:
                self.blocks.append(self._current_block)
                self._current_block = None
                self._block_depth = 0

    def finish(self) -> None:
        """Finalize dangling blocks from imperfect HTML."""

        if self._current_block is not None:
            self.blocks.append(self._current_block)
            self._current_block = None
            self._block_depth = 0


def parse_ceqanet_result_page(
    html: str,
    *,
    source_url: str | None = None,
    base_url: str = CEQANET_BASE_URL,
) -> CeqanetResultPageParse:
    """Parse candidate CEQAnet result records from stored HTML."""

    parser = _CeqanetResultHtmlParser()
    parser.feed(html)
    parser.finish()

    candidate_blocks = tuple(block for block in parser.blocks if _is_result_candidate_block(block))
    candidate_links = tuple(link for link in parser.links if _is_result_link(link))
    block_records = tuple(
        record
        for record in (
            _record_from_block(block, source_url=source_url, base_url=base_url)
            for block in candidate_blocks
        )
        if record is not None
    )
    link_records = (
        ()
        if block_records
        else tuple(
            _record_from_link(link, source_url=source_url, base_url=base_url)
            for link in candidate_links
        )
    )

    return CeqanetResultPageParse(
        records=_dedupe_records(block_records + link_records),
        source_url=source_url,
        candidate_block_count=len(candidate_blocks),
        candidate_link_count=len(candidate_links),
    )


def _is_result_block_start(tag: str, attrs: dict[str, str]) -> bool:
    """Return true for containers likely to hold one CEQAnet search result."""

    if tag in _RESULT_BLOCK_TAGS:
        return True

    class_or_id = " ".join((attrs.get("class", ""), attrs.get("id", ""))).lower()
    return tag == "div" and any(hint in class_or_id for hint in _RESULT_CLASS_HINTS)


def _is_result_candidate_block(block: _ParsedBlock) -> bool:
    """Return true when a parsed block looks like one result record."""

    if not block.links:
        return False

    raw_text = block.raw_text.lower()
    has_signal = any(signal.lower() in raw_text for signal in _RESULT_TEXT_SIGNALS)
    has_usable_link = any(_usable_result_link(link) for link in block.links)
    return has_signal and has_usable_link


def _is_result_link(link: _ParsedLink) -> bool:
    """Return true when an anchor looks like a CEQAnet result-detail link."""

    if not _usable_result_link(link):
        return False

    text = link.text.lower()
    href = link.href.lower()
    if any(term in href for term in _RESULT_HREF_TERMS):
        return True

    return bool(_SCH_PATTERN.search(href)) and len(text) > 5


def _usable_result_link(link: _ParsedLink) -> bool:
    """Reject navigation, blank, script, and search-control links."""

    text = _normalize_text(link.text)
    href = link.href.strip()
    if not href or href == "#":
        return False

    lower_text = text.lower()
    lower_href = href.lower()
    if lower_text in _NAV_TEXTS:
        return False

    return not any(term in lower_href for term in _NAV_HREF_TERMS)


def _record_from_block(
    block: _ParsedBlock,
    *,
    source_url: str | None,
    base_url: str,
) -> CeqanetSearchResultRecord | None:
    """Build one result record from a candidate HTML block."""

    detail_link = _best_detail_link(block.links)
    if detail_link is None:
        return None

    raw_text = block.raw_text
    title_candidate = _title_from_block(block, detail_link)
    if not title_candidate.title:
        return None

    sch_number = _extract_labeled_value(raw_text, ("SCH Number", "SCH #", "SCH"))
    if sch_number is None:
        sch_number = _extract_sch_number(detail_link.text, detail_link.href, raw_text)

    requires_detail_enrichment = title_candidate.source == "sch_number"
    return CeqanetSearchResultRecord(
        title=title_candidate.title,
        detail_url=urljoin(base_url, detail_link.href),
        sch_number=sch_number,
        document_type=_extract_labeled_value(raw_text, ("Document Type", "Type")),
        lead_agency=_extract_labeled_value(raw_text, ("Lead/Public Agency", "Lead Agency")),
        county=_extract_labeled_value(raw_text, ("County",)),
        city=_extract_labeled_value(raw_text, ("City",)),
        source_url=source_url,
        raw_text=raw_text,
        title_source=title_candidate.source,
        requires_detail_enrichment=requires_detail_enrichment,
    )


def _record_from_link(
    link: _ParsedLink,
    *,
    source_url: str | None,
    base_url: str,
) -> CeqanetSearchResultRecord:
    """Build a minimal record from a result-looking fallback anchor."""

    title_candidate = _title_from_link(link)
    return CeqanetSearchResultRecord(
        title=title_candidate.title,
        detail_url=urljoin(base_url, link.href),
        sch_number=_extract_sch_number(link.text, link.href),
        source_url=source_url,
        raw_text=title_candidate.title,
        title_source=title_candidate.source,
        requires_detail_enrichment=title_candidate.source == "sch_number",
    )


def _best_detail_link(links: list[_ParsedLink]) -> _ParsedLink | None:
    """Choose the best URL-bearing result-detail link from a result block."""

    usable_links = [link for link in links if _usable_result_link(link)]
    if not usable_links:
        return None

    project_links = [link for link in usable_links if "/project/" in link.href.lower()]
    if project_links:
        return project_links[0]

    numeric_links = [link for link in usable_links if _SCH_PATTERN.search(link.href)]
    if numeric_links:
        return numeric_links[0]

    return usable_links[0]


def _title_from_block(block: _ParsedBlock, detail_link: _ParsedLink) -> _TitleCandidate:
    """Return the best available title candidate for one result block."""

    labeled_title = _extract_labeled_value(block.raw_text, _PROJECT_TITLE_LABELS)
    if labeled_title and not _is_sch_like(labeled_title):
        return _TitleCandidate(title=labeled_title, source="human_label")

    human_link_text = _best_human_link_text(block.links)
    if human_link_text:
        return _TitleCandidate(title=human_link_text, source="human_link_text")

    return _title_from_link(detail_link)


def _title_from_link(link: _ParsedLink) -> _TitleCandidate:
    """Return title candidate and source from one link."""

    title = _clean_title(link.text)
    if _is_sch_like(title):
        return _TitleCandidate(title=title, source="sch_number")
    return _TitleCandidate(title=title, source="link_text")


def _best_human_link_text(links: list[_ParsedLink]) -> str | None:
    """Return the best non-SCH, non-generic link text in source order."""

    for link in links:
        text = _clean_title(link.text)
        if _is_human_title_candidate(text):
            return text
    return None


def _is_human_title_candidate(text: str) -> bool:
    """Return true when text looks like a project title rather than a control/SCH."""

    if not text:
        return False

    lower_text = text.lower()
    if lower_text in _NAV_TEXTS or lower_text in _GENERIC_LINK_TEXTS:
        return False

    if _is_sch_like(text):
        return False

    return len(text) > 5


def _is_sch_like(value: str) -> bool:
    """Return true when text is essentially only an SCH-style number."""

    cleaned = _normalize_text(value)
    return bool(re.fullmatch(r"\d{7,}", cleaned))


def _extract_sch_number(*values: str) -> str | None:
    """Extract the first SCH-like number from text or href values."""

    for value in values:
        match = _SCH_PATTERN.search(value)
        if match:
            return match.group(0)
    return None


def _dedupe_records(
    records: tuple[CeqanetSearchResultRecord, ...],
) -> tuple[CeqanetSearchResultRecord, ...]:
    """Deduplicate records by strongest available identity while preserving order."""

    seen: set[tuple[str, str]] = set()
    deduped: list[CeqanetSearchResultRecord] = []
    for record in records:
        key = (record.sch_number or record.title, record.detail_url)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(record)
    return tuple(deduped)


def _extract_labeled_value(raw_text: str, labels: tuple[str, ...]) -> str | None:
    """Extract a value from pipe-delimited or colon-delimited result text."""

    parts = [part.strip() for part in raw_text.split("|") if part.strip()]
    for index, part in enumerate(parts):
        for label in labels:
            normalized_label = label.lower()
            normalized_part = part.lower().rstrip(":")
            if normalized_part == normalized_label and index + 1 < len(parts):
                return _clean_field_value(parts[index + 1])

            prefix = f"{label}:"
            if part.lower().startswith(prefix.lower()):
                return _clean_field_value(part[len(prefix) :])
    return None


def _clean_title(value: str) -> str:
    """Return normalized result-title text."""

    title = _normalize_text(value)
    for prefix in ("View Details", "Project Details"):
        if title.lower().startswith(prefix.lower()):
            title = _normalize_text(title[len(prefix) :])
    return title


def _clean_field_value(value: str) -> str | None:
    """Normalize an extracted field value."""

    cleaned = _normalize_text(value).strip(":- ")
    return cleaned or None


def _normalize_text(value: str | None) -> str:
    """Collapse whitespace into stable text."""

    if value is None:
        return ""
    return " ".join(value.split())
