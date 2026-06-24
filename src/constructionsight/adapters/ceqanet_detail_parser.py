"""CEQAnet detail/project page parsing.

This module parses stored CEQAnet detail-page HTML into project metadata. It is
intentionally offline and conservative: it does not execute network requests,
download documents, or mutate persistence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Literal
from urllib.parse import urljoin

CEQANET_BASE_URL = "https://ceqanet.lci.ca.gov/"

CeqanetDetailTitleSource = Literal[
    "human_label",
    "human_heading",
    "html_title",
    "sch_number",
    "unavailable",
]

_IGNORED_TAGS = {"script", "style", "select", "option", "noscript"}
_BLOCK_TAGS = {
    "article",
    "br",
    "dd",
    "div",
    "dl",
    "dt",
    "h1",
    "h2",
    "h3",
    "header",
    "li",
    "main",
    "p",
    "section",
    "td",
    "th",
    "tr",
}
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
_SCH_PATTERN = re.compile(r"\b\d{7,}\b")

_LABEL_ALIASES: dict[str, str] = {
    "sch": "sch_number",
    "sch #": "sch_number",
    "sch number": "sch_number",
    "state clearinghouse number": "sch_number",
    "project title": "project_title",
    "project name": "project_title",
    "title": "project_title",
    "document title": "project_title",
    "document description": "project_description",
    "description": "project_description",
    "project description": "project_description",
    "lead agency": "lead_agency",
    "lead/public agency": "lead_agency",
    "lead agency / applicant": "lead_agency",
    "document type": "document_type",
    "type": "document_type",
    "county": "county",
    "city": "city",
    "location": "project_location",
    "project location": "project_location",
    "address": "project_location",
    "contact": "contact",
    "contact person": "contact",
    "project issues": "project_issues",
    "development type": "development_type",
    "local action": "local_action",
    "posted": "posted_date",
    "posted date": "posted_date",
    "received": "received_date",
    "received date": "received_date",
    "review period": "review_period",
    "review period start": "review_period_start",
    "review period end": "review_period_end",
}


@dataclass(frozen=True)
class CeqanetDetailLink:
    """One link discovered on a CEQAnet detail/project page."""

    text: str
    href: str
    absolute_url: str

    def to_dict(self) -> dict[str, str]:
        """Return a JSON-safe representation of the link."""

        return {
            "text": self.text,
            "href": self.href,
            "absolute_url": self.absolute_url,
        }


@dataclass(frozen=True)
class CeqanetDetailPageParse:
    """Parsed CEQAnet detail/project page."""

    source_url: str | None
    title: str | None
    title_source: CeqanetDetailTitleSource
    sch_number: str | None
    document_type: str | None
    lead_agency: str | None
    county: str | None
    city: str | None
    project_location: str | None
    project_description: str | None
    contact: str | None
    label_values: dict[str, str]
    links: tuple[CeqanetDetailLink, ...]
    raw_text: str

    @property
    def has_human_title(self) -> bool:
        """Return whether the parsed title came from human-readable page content."""

        return self.title_source in {"human_label", "human_heading", "html_title"}

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-safe representation of the detail parse report."""

        return {
            "metadata": {
                "schema_version": "ceqanet_detail_page_parse.v1",
                "source_url": self.source_url,
                "has_human_title": self.has_human_title,
                "label_count": len(self.label_values),
                "link_count": len(self.links),
            },
            "detail": {
                "title": self.title,
                "title_source": self.title_source,
                "sch_number": self.sch_number,
                "document_type": self.document_type,
                "lead_agency": self.lead_agency,
                "county": self.county,
                "city": self.city,
                "project_location": self.project_location,
                "project_description": self.project_description,
                "contact": self.contact,
                "label_values": self.label_values,
                "links": [link.to_dict() for link in self.links],
                "raw_text": self.raw_text,
            },
        }


@dataclass
class _ParsedLink:
    text: str
    href: str


class _CeqanetDetailHtmlParser(HTMLParser):
    """Internal parser collecting visible text, headings, page title, and links."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.text_parts: list[str] = []
        self.heading_parts: list[str] = []
        self.html_title_parts: list[str] = []
        self.links: list[_ParsedLink] = []
        self._ignored_depth = 0
        self._current_tag: str | None = None
        self._current_link_href: str | None = None
        self._current_link_text_parts: list[str] = []
        self._current_heading_parts: list[str] = []
        self._current_title_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Track visible text regions and anchors."""

        normalized_tag = tag.lower()
        attrs_by_name = {name: value or "" for name, value in attrs}

        if normalized_tag in _IGNORED_TAGS:
            self._ignored_depth += 1
            return

        if self._ignored_depth:
            return

        if normalized_tag in _BLOCK_TAGS:
            self._append_separator()

        self._current_tag = normalized_tag
        if normalized_tag == "a":
            self._current_link_href = attrs_by_name.get("href", "")
            self._current_link_text_parts = []
        elif normalized_tag in {"h1", "h2", "h3"}:
            self._current_heading_parts = []
        elif normalized_tag == "title":
            self._current_title_parts = []

    def handle_data(self, data: str) -> None:
        """Collect normalized visible text."""

        if self._ignored_depth:
            return

        text = _normalize_text(data)
        if not text:
            return

        self.text_parts.append(text)
        if self._current_link_href is not None:
            self._current_link_text_parts.append(text)
        if self._current_tag in {"h1", "h2", "h3"}:
            self._current_heading_parts.append(text)
        if self._current_tag == "title":
            self._current_title_parts.append(text)

    def handle_endtag(self, tag: str) -> None:
        """Finalize anchors, headings, titles, and block separators."""

        normalized_tag = tag.lower()

        if normalized_tag in _IGNORED_TAGS:
            if self._ignored_depth:
                self._ignored_depth -= 1
            return

        if self._ignored_depth:
            return

        if normalized_tag == "a" and self._current_link_href is not None:
            link = _ParsedLink(
                text=_normalize_text(" ".join(self._current_link_text_parts)),
                href=self._current_link_href.strip(),
            )
            if _usable_link(link):
                self.links.append(link)
            self._current_link_href = None
            self._current_link_text_parts = []
        elif normalized_tag in {"h1", "h2", "h3"}:
            heading = _normalize_text(" ".join(self._current_heading_parts))
            if heading:
                self.heading_parts.append(heading)
            self._current_heading_parts = []
        elif normalized_tag == "title":
            title = _normalize_text(" ".join(self._current_title_parts))
            if title:
                self.html_title_parts.append(title)
            self._current_title_parts = []

        if normalized_tag in _BLOCK_TAGS:
            self._append_separator()
        self._current_tag = None

    def _append_separator(self) -> None:
        """Append a text separator if needed."""

        if self.text_parts and self.text_parts[-1] != "|":
            self.text_parts.append("|")


def parse_ceqanet_detail_page(
    html: str,
    *,
    source_url: str | None = None,
    base_url: str = CEQANET_BASE_URL,
) -> CeqanetDetailPageParse:
    """Parse project/detail metadata from stored CEQAnet HTML."""

    parser = _CeqanetDetailHtmlParser()
    parser.feed(html)

    raw_text = _collapse_separators(parser.text_parts)
    label_values = _extract_label_values(raw_text)
    sch_number = label_values.get("sch_number") or _extract_sch_number(raw_text, source_url or "")
    title, title_source = _extract_title(
        label_values=label_values,
        headings=tuple(parser.heading_parts),
        html_titles=tuple(parser.html_title_parts),
        sch_number=sch_number,
    )

    links = tuple(
        CeqanetDetailLink(
            text=link.text,
            href=link.href,
            absolute_url=urljoin(base_url, link.href),
        )
        for link in parser.links
    )
    return CeqanetDetailPageParse(
        source_url=source_url,
        title=title,
        title_source=title_source,
        sch_number=sch_number,
        document_type=label_values.get("document_type"),
        lead_agency=label_values.get("lead_agency"),
        county=label_values.get("county"),
        city=label_values.get("city"),
        project_location=label_values.get("project_location"),
        project_description=label_values.get("project_description"),
        contact=label_values.get("contact"),
        label_values=label_values,
        links=links,
        raw_text=raw_text,
    )


def _extract_title(
    *,
    label_values: dict[str, str],
    headings: tuple[str, ...],
    html_titles: tuple[str, ...],
    sch_number: str | None,
) -> tuple[str | None, CeqanetDetailTitleSource]:
    """Extract the best title and title provenance."""

    for key in ("project_title", "project_description"):
        title = label_values.get(key)
        if title and not _is_sch_like(title):
            return title, "human_label"

    for heading in headings:
        cleaned = _clean_title(heading)
        if _is_human_title_candidate(cleaned):
            return cleaned, "human_heading"

    for html_title in html_titles:
        cleaned = _clean_title(html_title)
        if _is_human_title_candidate(cleaned):
            return cleaned, "html_title"

    if sch_number is not None:
        return sch_number, "sch_number"
    return None, "unavailable"


def _extract_label_values(raw_text: str) -> dict[str, str]:
    """Extract known label/value pairs from normalized detail-page text."""

    values: dict[str, str] = {}
    parts = [part.strip() for part in raw_text.split("|") if part.strip()]
    for index, part in enumerate(parts):
        canonical = _canonical_label(part)
        if canonical is not None and index + 1 < len(parts):
            value = _clean_field_value(parts[index + 1])
            if _is_valid_adjacent_label_value(value):
                values.setdefault(canonical, value)
            continue

        split_label, split_value = _split_colon_label(part)
        if split_label is None or split_value is None:
            continue
        canonical = _canonical_label(split_label)
        value = _clean_field_value(split_value)
        if canonical is not None and value is not None:
            values.setdefault(canonical, value)
    return values


def _is_valid_adjacent_label_value(value: str | None) -> bool:
    """Return false when adjacent text is another label/header, not a field value."""

    if value is None:
        return False
    if _canonical_label(value) is not None:
        return False
    if _normalize_label(value) in _NAV_TEXTS:
        return False
    return True


def _canonical_label(value: str) -> str | None:
    """Return canonical field name for a label-like string."""

    normalized = _normalize_label(value)
    return _LABEL_ALIASES.get(normalized)


def _split_colon_label(value: str) -> tuple[str | None, str | None]:
    """Split a label/value string when it is colon-delimited."""

    if ":" not in value:
        return None, None
    label, raw_value = value.split(":", 1)
    return label, raw_value


def _usable_link(link: _ParsedLink) -> bool:
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


def _is_human_title_candidate(text: str) -> bool:
    """Return true when text looks like a human title rather than page chrome."""

    cleaned = _clean_title(text)
    if not cleaned:
        return False
    lower_text = cleaned.lower()
    if lower_text in _NAV_TEXTS:
        return False
    if _is_sch_like(cleaned):
        return False
    return len(cleaned) > 5


def _extract_sch_number(*values: str) -> str | None:
    """Extract the first SCH-like number from text or URL values."""

    for value in values:
        match = _SCH_PATTERN.search(value)
        if match:
            return match.group(0)
    return None


def _is_sch_like(value: str) -> bool:
    """Return true when text is essentially only an SCH-style number."""

    return bool(re.fullmatch(r"\d{7,}", _normalize_text(value)))


def _clean_title(value: str) -> str:
    """Normalize a title candidate."""

    cleaned = _normalize_text(value)
    for suffix in ("- CEQAnet", "| CEQAnet", "CEQAnet"):
        if cleaned.endswith(suffix):
            cleaned = _normalize_text(cleaned[: -len(suffix)])
    for prefix in ("Project Details", "Document Details", "CEQAnet"):
        if cleaned.lower().startswith(prefix.lower()):
            cleaned = _normalize_text(cleaned[len(prefix) :]).strip("-:| ")
    return cleaned


def _clean_field_value(value: str) -> str | None:
    """Normalize an extracted field value."""

    cleaned = _normalize_text(value).strip(":- ")
    return cleaned or None


def _normalize_label(value: str) -> str:
    """Normalize a possible label for lookup."""

    return _normalize_text(value).lower().strip(":- ")


def _collapse_separators(parts: list[str]) -> str:
    """Collapse parser text parts into stable pipe-delimited text."""

    cleaned_parts: list[str] = []
    for part in parts:
        cleaned = _normalize_text(part)
        if not cleaned:
            continue
        if cleaned == "|" and (not cleaned_parts or cleaned_parts[-1] == "|"):
            continue
        cleaned_parts.append(cleaned)
    while cleaned_parts and cleaned_parts[-1] == "|":
        cleaned_parts.pop()
    return " ".join(cleaned_parts).replace(" | ", "|").replace("|", " | ")


def _normalize_text(value: str | None) -> str:
    """Collapse whitespace into stable text."""

    if value is None:
        return ""
    return " ".join(value.split())
