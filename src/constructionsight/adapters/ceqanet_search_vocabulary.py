"""CEQAnet advanced-search vocabulary extraction.

CEQAnet's public advanced search page exposes official option labels for
document types, lead/public agencies, counties, cities, regions, local actions,
project issues, and development types. This module extracts that controlled
vocabulary without executing searches, downloading documents, or mutating state.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Literal

from constructionsight.adapters.ceqanet_search_contract import (
    CEQANET_FIELD_CITY,
    CEQANET_FIELD_COUNTY,
    CEQANET_FIELD_DEVELOPMENT_TYPE,
    CEQANET_FIELD_DOCUMENT_TYPE,
    CEQANET_FIELD_LEAD_AGENCY,
    CEQANET_FIELD_LOCAL_ACTION,
    CEQANET_FIELD_PROJECT_ISSUE,
    CEQANET_FIELD_REGION,
    CEQANET_FIELD_STATE_REVIEW_AGENCY,
)

CeqanetLeadAgencyType = Literal[
    "air_quality_agency",
    "city",
    "county",
    "federal_agency",
    "lafco",
    "sanitation_wastewater",
    "school_district",
    "special_district",
    "state_agency",
    "transportation_agency",
    "unknown",
]

CEQANET_VOCABULARY_FIELD_ORDER: tuple[str, ...] = (
    CEQANET_FIELD_DOCUMENT_TYPE,
    CEQANET_FIELD_LEAD_AGENCY,
    CEQANET_FIELD_STATE_REVIEW_AGENCY,
    CEQANET_FIELD_COUNTY,
    CEQANET_FIELD_CITY,
    CEQANET_FIELD_REGION,
    CEQANET_FIELD_LOCAL_ACTION,
    CEQANET_FIELD_PROJECT_ISSUE,
    CEQANET_FIELD_DEVELOPMENT_TYPE,
)


@dataclass(frozen=True)
class CeqanetSearchVocabularyOption:
    """One CEQAnet advanced-search option value."""

    field_name: str
    label: str
    value: str
    selected: bool = False

    def to_dict(self) -> dict[str, str | bool]:
        """Return a JSON-safe representation of the option."""

        return {
            "field_name": self.field_name,
            "label": self.label,
            "value": self.value,
            "selected": self.selected,
        }


@dataclass(frozen=True)
class CeqanetSearchVocabularyGroup:
    """All extracted options for one CEQAnet search field."""

    field_name: str
    options: tuple[CeqanetSearchVocabularyOption, ...]

    @property
    def labels(self) -> tuple[str, ...]:
        """Return option labels in source order."""

        return tuple(option.label for option in self.options)

    @property
    def values(self) -> tuple[str, ...]:
        """Return option values in source order."""

        return tuple(option.value for option in self.options)

    @property
    def non_empty_options(self) -> tuple[CeqanetSearchVocabularyOption, ...]:
        """Return options that contain a non-empty query value."""

        return tuple(option for option in self.options if option.value)


@dataclass(frozen=True)
class CeqanetSearchVocabulary:
    """Extracted CEQAnet controlled vocabulary grouped by search field."""

    groups: tuple[CeqanetSearchVocabularyGroup, ...]

    def group(self, field_name: str) -> CeqanetSearchVocabularyGroup:
        """Return the vocabulary group for a field name."""

        for group in self.groups:
            if group.field_name == field_name:
                return group
        raise KeyError(f"CEQAnet vocabulary field not found: {field_name}")

    def has_group(self, field_name: str) -> bool:
        """Return true when the vocabulary contains the requested field."""

        return any(group.field_name == field_name for group in self.groups)

    def to_dict(self) -> dict[str, list[dict[str, str | bool]]]:
        """Return a JSON-safe grouped representation."""

        return {
            group.field_name: [option.to_dict() for option in group.options]
            for group in self.groups
        }


class _CeqanetSearchVocabularyHtmlParser(HTMLParser):
    """Internal HTML parser for CEQAnet select/option vocabulary."""

    def __init__(self, field_order: Iterable[str]) -> None:
        super().__init__(convert_charrefs=True)
        self._field_order = tuple(field_order)
        self._field_names = set(self._field_order)
        self.options_by_field: dict[str, list[CeqanetSearchVocabularyOption]] = {
            field_name: [] for field_name in self._field_order
        }
        self._current_field: str | None = None
        self._in_option = False
        self._option_value: str | None = None
        self._option_selected = False
        self._option_text_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Track CEQAnet select fields and their option elements."""

        normalized_tag = tag.lower()
        attrs_by_name = dict(attrs)
        if normalized_tag == "select":
            field_name = self._field_name_from_attrs(attrs_by_name)
            if field_name in self._field_names:
                self._current_field = field_name
            return

        if normalized_tag == "option" and self._current_field is not None:
            self._in_option = True
            self._option_value = attrs_by_name.get("value")
            self._option_selected = "selected" in attrs_by_name
            self._option_text_parts = []

    def handle_data(self, data: str) -> None:
        """Collect visible option text."""

        if self._in_option:
            self._option_text_parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        """Finalize CEQAnet options and select groups."""

        normalized_tag = tag.lower()
        if normalized_tag == "option":
            self._finalize_option()
            return

        if normalized_tag == "select":
            self._current_field = None

    def _field_name_from_attrs(self, attrs_by_name: dict[str, str | None]) -> str | None:
        """Return a CEQAnet field name from select attributes."""

        name = attrs_by_name.get("name")
        if name in self._field_names:
            return name

        element_id = attrs_by_name.get("id")
        if element_id in self._field_names:
            return element_id

        return None

    def _finalize_option(self) -> None:
        """Create an option object from the current parser state."""

        if not self._in_option or self._current_field is None:
            return

        label = _normalize_text(" ".join(self._option_text_parts))
        raw_value = self._option_value if self._option_value is not None else label
        value = _normalize_text(raw_value)
        if label:
            self.options_by_field[self._current_field].append(
                CeqanetSearchVocabularyOption(
                    field_name=self._current_field,
                    label=label,
                    value=value,
                    selected=self._option_selected,
                )
            )

        self._in_option = False
        self._option_value = None
        self._option_selected = False
        self._option_text_parts = []


def parse_ceqanet_search_vocabulary(
    html: str,
    *,
    field_order: tuple[str, ...] = CEQANET_VOCABULARY_FIELD_ORDER,
) -> CeqanetSearchVocabulary:
    """Extract CEQAnet search vocabulary groups from advanced-search HTML."""

    parser = _CeqanetSearchVocabularyHtmlParser(field_order)
    parser.feed(html)
    groups = tuple(
        CeqanetSearchVocabularyGroup(
            field_name=field_name,
            options=tuple(parser.options_by_field[field_name]),
        )
        for field_name in field_order
        if parser.options_by_field[field_name]
    )
    return CeqanetSearchVocabulary(groups=groups)


def classify_ceqanet_lead_agency(label: str) -> CeqanetLeadAgencyType:
    """Classify a CEQAnet lead/public agency label by practical source type."""

    normalized = _normalize_text(label)
    lower_label = normalized.lower()
    if not normalized or normalized == "(Any)":
        return "unknown"

    if lower_label.startswith("city of ") or lower_label.endswith(", city of"):
        return "city"

    if lower_label.endswith(" county"):
        return "county"

    if "school district" in lower_label or "union high school" in lower_label:
        return "school_district"

    if "water district" in lower_label or "water agency" in lower_label:
        return "special_district"

    if "waterworks" in lower_label:
        return "special_district"

    if "transportation" in lower_label or "transit" in lower_label:
        return "transportation_agency"

    if "local agency formation commission" in lower_label or "lafco" in lower_label:
        return "lafco"

    if "sanitation" in lower_label or "wastewater" in lower_label:
        return "sanitation_wastewater"

    if "sewer" in lower_label:
        return "sanitation_wastewater"

    if "air pollution" in lower_label or "air quality" in lower_label:
        return "air_quality_agency"

    if "united states" in lower_label:
        return "federal_agency"

    if "department of" in lower_label or "office of" in lower_label:
        return "state_agency"

    if "district" in lower_label or "authority" in lower_label:
        return "special_district"

    if "agency" in lower_label or "commission" in lower_label:
        return "special_district"

    return "unknown"


def _normalize_text(value: str | None) -> str:
    """Collapse HTML text whitespace into stable comparison text."""

    if value is None:
        return ""
    return " ".join(value.split())
