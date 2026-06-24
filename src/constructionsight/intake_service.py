"""Universal lawful intake inspection service.

The service turns finite binary/structural format detection into a source-neutral
intake record. It never mutates persistence and never assumes unfamiliar layouts
are understood; unknown material is preserved and routed for review.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import zipfile
from dataclasses import dataclass
from io import BytesIO, StringIO
from pathlib import Path

from constructionsight.intake_models import (
    DigitalFormatFamily,
    ExtractedMaterialFact,
    FactConfidence,
    FormatDetection,
    IntakeEvidenceRef,
    IntakeRouting,
    IntakeUnderstandingStatus,
    MaterialFactKind,
    UniversalIntakeRecord,
    UnmappedEvidenceFragment,
)

_ADDRESS_RE = re.compile(
    r"\b\d{1,6}\s+[A-Za-z0-9][A-Za-z0-9 .'-]{2,80}\s+"
    r"(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Court|Ct|"
    r"Way)\b",
    re.IGNORECASE,
)
_APN_RE = re.compile(
    r"\b(?:APN|Parcel(?:\s+No\.)?)[:#\s-]*"
    r"([0-9]{3,4}[-\s][0-9]{2,4}[-\s][0-9]{2,4})\b",
    re.IGNORECASE,
)
_SCH_RE = re.compile(
    r"\bSCH(?:\s*(?:No\.|Number|#))?[:#\s-]*(\d{10})\b",
    re.IGNORECASE,
)
_EMAIL_RE = re.compile(
    r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
    re.IGNORECASE,
)
_URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
_PHONE_RE = re.compile(
    r"(?:\+1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}"
)
_MONEY_RE = re.compile(r"\$\s?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{2})?")
_DATE_RE = re.compile(
    r"\b\d{1,2}/\d{1,2}/\d{2,4}\b|\b\d{4}-\d{2}-\d{2}\b"
)
_CSLB_RE = re.compile(
    r"\b(?:CSLB|License(?:\s+No\.)?)[:#\s-]*(\d{5,8})\b",
    re.IGNORECASE,
)
_PERMIT_RE = re.compile(
    r"\b(?:Permit(?:\s+No\.)?|Permit #)[:#\s-]*"
    r"([A-Z]{0,4}\d{4,}[-A-Z0-9]*)\b",
    re.IGNORECASE,
)
_AGENCY_RE = re.compile(
    r"\b(?:City|County|Town|Department|Agency)\s+of\s+"
    r"[A-Z][A-Za-z .'-]{2,60}\b"
)
_CONSTRUCTION_KEYWORDS = (
    "construction",
    "warehouse",
    "industrial",
    "logistics",
    "distribution",
    "site security",
    "grading",
    "entitlement",
    "environmental impact report",
    "mitigated negative declaration",
    "notice of preparation",
)


@dataclass(frozen=True)
class IntakeInspectionInput:
    """Input payload for one universal intake inspection."""

    content: bytes
    source_name: str
    original_filename: str | None = None
    source_family: str | None = None
    source_url: str | None = None
    snapshot_path: str | None = None


def inspect_lawful_input(payload: IntakeInspectionInput) -> UniversalIntakeRecord:
    """Inspect one lawful input and return a source-neutral intake record."""

    sha256 = hashlib.sha256(payload.content).hexdigest()
    evidence_id = f"evidence:{sha256[:16]}"
    evidence = IntakeEvidenceRef(
        evidence_id=evidence_id,
        source_name=payload.source_name,
        source_family=payload.source_family,
        source_url=payload.source_url,
        original_filename=payload.original_filename,
        snapshot_path=payload.snapshot_path,
        byte_count=len(payload.content),
        sha256=sha256,
    )
    detection = detect_format_family(
        payload.content,
        original_filename=payload.original_filename,
    )
    extracted_facts = extract_material_facts(
        payload.content,
        detection=detection,
        evidence_id=evidence_id,
    )
    unmapped_fragments = build_unmapped_fragments(
        payload.content,
        detection=detection,
        evidence_id=evidence_id,
        extracted_facts=extracted_facts,
    )
    status = determine_understanding_status(
        detection=detection,
        extracted_facts=extracted_facts,
        unmapped_fragments=unmapped_fragments,
    )
    routing = determine_routing(
        status=status,
        extracted_facts=extracted_facts,
        unmapped_fragments=unmapped_fragments,
        source_family=payload.source_family,
    )

    return UniversalIntakeRecord(
        intake_id=f"intake:{sha256[:16]}",
        evidence=evidence,
        format_detection=detection,
        understanding_status=status,
        routing=routing,
        extracted_facts=extracted_facts,
        unmapped_fragments=unmapped_fragments,
        source_hints=_source_hints(payload),
        record_hints=_record_hints(extracted_facts),
        adapter_candidate=adapter_candidate(
            detection=detection,
            source_family=payload.source_family,
        ),
        next_action=next_action_for(status=status, routing=routing),
    )


def inspect_lawful_file(
    path: Path,
    *,
    source_name: str | None = None,
    source_family: str | None = None,
    source_url: str | None = None,
) -> UniversalIntakeRecord:
    """Inspect one local lawful file as universal intake evidence."""

    return inspect_lawful_input(
        IntakeInspectionInput(
            content=path.read_bytes(),
            source_name=source_name or path.name,
            original_filename=path.name,
            source_family=source_family,
            source_url=source_url,
            snapshot_path=str(path),
        )
    )


def detect_format_family(
    content: bytes,
    *,
    original_filename: str | None = None,
) -> FormatDetection:
    """Detect a finite high-level digital format family from bytes and filename hints."""

    filename = (original_filename or "").lower()
    if content.startswith(b"%PDF-"):
        return FormatDetection(
            format_family=DigitalFormatFamily.PDF,
            media_type="application/pdf",
            matched_signals=["magic:%PDF"],
            limitations=["pdf text extraction requires a dedicated parser"],
        )
    if _is_zip(content):
        return _detect_zip_family(content, filename=filename)
    if content.startswith(b"SQLite format 3\x00"):
        return FormatDetection(
            format_family=DigitalFormatFamily.SQLITE,
            media_type="application/vnd.sqlite3",
            matched_signals=["magic:SQLite format 3"],
            limitations=["sqlite inspection requires a dedicated database reader"],
        )
    image_detection = _detect_image(content)
    if image_detection is not None:
        return image_detection
    media_detection = _detect_media(content)
    if media_detection is not None:
        return media_detection

    text = _decode_text(content)
    if text is None:
        return FormatDetection(
            format_family=DigitalFormatFamily.BINARY,
            media_type="application/octet-stream",
            matched_signals=["binary:undecodable"],
            limitations=[
                "content is not UTF-8 text and no supported binary signature matched"
            ],
        )

    stripped = text.lstrip("\ufeff\n\r\t ")
    if _looks_like_email(text):
        return FormatDetection(
            format_family=DigitalFormatFamily.EMAIL,
            media_type="message/rfc822",
            encoding="utf-8",
            matched_signals=["headers:email"],
        )
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            json.loads(stripped)
        except json.JSONDecodeError:
            pass
        else:
            return FormatDetection(
                format_family=DigitalFormatFamily.JSON,
                media_type="application/json",
                encoding="utf-8",
                matched_signals=["json:loads"],
            )
    if _looks_like_jsonl(text):
        return FormatDetection(
            format_family=DigitalFormatFamily.JSONL,
            media_type="application/x-ndjson",
            encoding="utf-8",
            matched_signals=["jsonl:line-delimited-json"],
        )
    if _looks_like_html(stripped):
        return FormatDetection(
            format_family=DigitalFormatFamily.HTML,
            media_type="text/html",
            encoding="utf-8",
            matched_signals=["text:html-tags"],
        )
    if _looks_like_xml(stripped):
        return FormatDetection(
            format_family=DigitalFormatFamily.XML,
            media_type="application/xml",
            encoding="utf-8",
            matched_signals=["text:xml-prolog-or-root"],
        )
    if _looks_like_csv(text):
        delimiter = _sniff_delimiter(text)
        return FormatDetection(
            format_family=_delimited_format_family(delimiter),
            media_type=_delimited_media_type(delimiter),
            encoding="utf-8",
            matched_signals=["text:delimited-table"],
        )
    return FormatDetection(
        format_family=DigitalFormatFamily.PLAIN_TEXT,
        media_type="text/plain",
        encoding="utf-8",
        matched_signals=["text:utf-8"],
    )


def extract_material_facts(
    content: bytes,
    *,
    detection: FormatDetection,
    evidence_id: str,
) -> list[ExtractedMaterialFact]:
    """Extract generic cross-source material facts when safe."""

    text = _text_for_generic_extraction(content, detection=detection)
    if text is None:
        return []

    values: list[tuple[MaterialFactKind, str, str | None]] = []
    values.extend(_regex_values(MaterialFactKind.ADDRESS, _ADDRESS_RE, text))
    values.extend(_regex_values(MaterialFactKind.APN, _APN_RE, text))
    values.extend(_regex_values(MaterialFactKind.SCH_NUMBER, _SCH_RE, text))
    values.extend(_regex_values(MaterialFactKind.PERMIT_NUMBER, _PERMIT_RE, text))
    values.extend(_regex_values(MaterialFactKind.CSLB_LICENSE, _CSLB_RE, text))
    values.extend(_regex_values(MaterialFactKind.EMAIL, _EMAIL_RE, text))
    values.extend(_regex_values(MaterialFactKind.PHONE, _PHONE_RE, text))
    values.extend(_regex_values(MaterialFactKind.URL, _URL_RE, text))
    values.extend(_regex_values(MaterialFactKind.MONEY, _MONEY_RE, text))
    values.extend(_regex_values(MaterialFactKind.DATE, _DATE_RE, text))
    values.extend(_regex_values(MaterialFactKind.AGENCY, _AGENCY_RE, text))
    values.extend(_keyword_values(text))

    seen: set[tuple[MaterialFactKind, str]] = set()
    facts: list[ExtractedMaterialFact] = []
    for kind, value, context in values:
        normalized = normalize_fact_value(kind=kind, value=value)
        key = (kind, normalized)
        if key in seen:
            continue
        seen.add(key)
        fact_id = f"fact:{evidence_id.removeprefix('evidence:')}:{len(facts) + 1:03d}"
        facts.append(
            ExtractedMaterialFact(
                fact_id=fact_id,
                fact_kind=kind,
                value=value,
                normalized_value=normalized,
                confidence=FactConfidence.SOURCE_CLAIMED,
                evidence_id=evidence_id,
                context=context,
            )
        )
    return facts


def build_unmapped_fragments(
    content: bytes,
    *,
    detection: FormatDetection,
    evidence_id: str,
    extracted_facts: list[ExtractedMaterialFact],
) -> list[UnmappedEvidenceFragment]:
    """Build deterministic unmapped evidence fragments when understanding is incomplete."""

    if detection.format_family in {
        DigitalFormatFamily.PDF,
        DigitalFormatFamily.DOCX,
        DigitalFormatFamily.XLSX,
        DigitalFormatFamily.PPTX,
        DigitalFormatFamily.IMAGE,
        DigitalFormatFamily.MEDIA,
        DigitalFormatFamily.SQLITE,
        DigitalFormatFamily.ZIP,
        DigitalFormatFamily.BINARY,
        DigitalFormatFamily.UNKNOWN,
    }:
        reason = f"{detection.format_family.value} requires a dedicated adapter or extractor"
        return [
            UnmappedEvidenceFragment(
                fragment_id=f"fragment:{evidence_id.removeprefix('evidence:')}:001",
                evidence_id=evidence_id,
                reason=reason,
                preview=_binary_preview(content),
                suggested_adapter_family=detection.format_family.value,
            )
        ]

    text = _decode_text(content) or ""
    if extracted_facts:
        return []
    return [
        UnmappedEvidenceFragment(
            fragment_id=f"fragment:{evidence_id.removeprefix('evidence:')}:001",
            evidence_id=evidence_id,
            reason="text was readable but no universal construction facts were extracted",
            preview=_text_preview(text),
        )
    ]


def determine_understanding_status(
    *,
    detection: FormatDetection,
    extracted_facts: list[ExtractedMaterialFact],
    unmapped_fragments: list[UnmappedEvidenceFragment],
) -> IntakeUnderstandingStatus:
    """Determine honest intake understanding status."""

    if detection.format_family in {DigitalFormatFamily.BINARY, DigitalFormatFamily.UNKNOWN}:
        return IntakeUnderstandingStatus.PRESERVED_ONLY
    if extracted_facts and not unmapped_fragments:
        if detection.format_family in {
            DigitalFormatFamily.JSON,
            DigitalFormatFamily.CSV,
            DigitalFormatFamily.TSV,
            DigitalFormatFamily.HTML,
            DigitalFormatFamily.XML,
            DigitalFormatFamily.PLAIN_TEXT,
            DigitalFormatFamily.EMAIL,
            DigitalFormatFamily.JSONL,
        }:
            return IntakeUnderstandingStatus.PARTIALLY_UNDERSTOOD
    if extracted_facts or unmapped_fragments:
        return IntakeUnderstandingStatus.PARTIALLY_UNDERSTOOD
    return IntakeUnderstandingStatus.FORMAT_DETECTED


def determine_routing(
    *,
    status: IntakeUnderstandingStatus,
    extracted_facts: list[ExtractedMaterialFact],
    unmapped_fragments: list[UnmappedEvidenceFragment],
    source_family: str | None,
) -> IntakeRouting:
    """Determine next route for inspected input."""

    if source_family:
        return IntakeRouting.SOURCE_ADAPTER
    if extracted_facts:
        return IntakeRouting.OPPORTUNITY_INTAKE
    if status == IntakeUnderstandingStatus.PRESERVED_ONLY:
        return IntakeRouting.HUMAN_REVIEW
    if unmapped_fragments:
        return IntakeRouting.ADAPTER_BACKLOG
    return IntakeRouting.GENERIC_EXTRACTION


def adapter_candidate(*, detection: FormatDetection, source_family: str | None) -> str | None:
    """Return adapter candidate name for routing/backlog."""

    if source_family:
        return source_family
    if detection.format_family in {
        DigitalFormatFamily.PDF,
        DigitalFormatFamily.DOCX,
        DigitalFormatFamily.XLSX,
        DigitalFormatFamily.HTML,
        DigitalFormatFamily.CSV,
        DigitalFormatFamily.JSON,
        DigitalFormatFamily.EMAIL,
    }:
        return f"{detection.format_family.value}_adapter_candidate"
    return None


def next_action_for(*, status: IntakeUnderstandingStatus, routing: IntakeRouting) -> str:
    """Return a human-readable deterministic next action."""

    if routing == IntakeRouting.OPPORTUNITY_INTAKE:
        return "Review extracted facts and convert qualifying records into lead candidates."
    if routing == IntakeRouting.SOURCE_ADAPTER:
        return "Route to the declared source-family adapter for structured parsing."
    if routing == IntakeRouting.ADAPTER_BACKLOG:
        return "Review unmapped structure and create an adapter rule if the pattern repeats."
    if routing == IntakeRouting.HUMAN_REVIEW:
        return "Human review required before material facts can be safely mapped."
    if status == IntakeUnderstandingStatus.FORMAT_DETECTED:
        return "Run generic extraction or provide source-family context."
    return "Preserve evidence and defer unsupported processing."


def normalize_fact_value(*, kind: MaterialFactKind, value: str) -> str:
    """Normalize extracted fact values for deterministic comparison."""

    normalized = " ".join(value.strip().split())
    if kind in {
        MaterialFactKind.EMAIL,
        MaterialFactKind.URL,
        MaterialFactKind.KEYWORD,
        MaterialFactKind.AGENCY,
    }:
        return normalized.lower()
    if kind in {
        MaterialFactKind.APN,
        MaterialFactKind.SCH_NUMBER,
        MaterialFactKind.PERMIT_NUMBER,
        MaterialFactKind.CSLB_LICENSE,
        MaterialFactKind.PHONE,
    }:
        return re.sub(r"[^A-Za-z0-9]", "", normalized).upper()
    return normalized


def _delimited_format_family(delimiter: str) -> DigitalFormatFamily:
    """Return delimited table format family."""

    if delimiter == "\t":
        return DigitalFormatFamily.TSV
    return DigitalFormatFamily.CSV


def _delimited_media_type(delimiter: str) -> str:
    """Return delimited table media type."""

    if delimiter == "\t":
        return "text/tab-separated-values"
    return "text/csv"


def _detect_zip_family(content: bytes, *, filename: str) -> FormatDetection:
    """Detect ZIP-derived Office families from archive members."""

    try:
        with zipfile.ZipFile(BytesIO(content)) as archive_file:
            names = set(archive_file.namelist())
    except zipfile.BadZipFile:
        return FormatDetection(
            format_family=DigitalFormatFamily.BINARY,
            media_type="application/octet-stream",
            matched_signals=["magic:PK", "zip:invalid"],
            limitations=["zip signature present but archive is invalid"],
        )

    if "word/document.xml" in names or filename.endswith(".docx"):
        return FormatDetection(
            format_family=DigitalFormatFamily.DOCX,
            media_type=(
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            ),
            matched_signals=["magic:PK", "zip:word/document.xml"],
            limitations=["docx text extraction requires a dedicated parser"],
        )
    if "xl/workbook.xml" in names or filename.endswith(".xlsx"):
        return FormatDetection(
            format_family=DigitalFormatFamily.XLSX,
            media_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
            matched_signals=["magic:PK", "zip:xl/workbook.xml"],
            limitations=["xlsx table extraction requires a dedicated parser"],
        )
    if "ppt/presentation.xml" in names or filename.endswith(".pptx"):
        return FormatDetection(
            format_family=DigitalFormatFamily.PPTX,
            media_type=(
                "application/vnd.openxmlformats-officedocument.presentationml."
                "presentation"
            ),
            matched_signals=["magic:PK", "zip:ppt/presentation.xml"],
            limitations=["pptx extraction requires a dedicated parser"],
        )
    return FormatDetection(
        format_family=DigitalFormatFamily.ZIP,
        media_type="application/zip",
        matched_signals=["magic:PK", "zip:valid"],
        limitations=["generic zip archives require explicit file selection before extraction"],
    )


def _detect_image(content: bytes) -> FormatDetection | None:
    """Detect common image signatures."""

    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return FormatDetection(
            format_family=DigitalFormatFamily.IMAGE,
            media_type="image/png",
            matched_signals=["magic:png"],
            limitations=["image text extraction requires OCR or metadata parsing"],
        )
    if content.startswith(b"\xff\xd8\xff"):
        return FormatDetection(
            format_family=DigitalFormatFamily.IMAGE,
            media_type="image/jpeg",
            matched_signals=["magic:jpeg"],
            limitations=["image text extraction requires OCR or metadata parsing"],
        )
    if content.startswith(b"GIF87a") or content.startswith(b"GIF89a"):
        return FormatDetection(
            format_family=DigitalFormatFamily.IMAGE,
            media_type="image/gif",
            matched_signals=["magic:gif"],
            limitations=["image text extraction requires OCR or metadata parsing"],
        )
    return None


def _detect_media(content: bytes) -> FormatDetection | None:
    """Detect common audio/video container signatures."""

    if content[4:8] == b"ftyp":
        return FormatDetection(
            format_family=DigitalFormatFamily.MEDIA,
            media_type="video/mp4",
            matched_signals=["magic:mp4-ftyp"],
            limitations=["media transcription requires a dedicated media pipeline"],
        )
    return None


def _is_zip(content: bytes) -> bool:
    """Return whether content starts with a ZIP local/header signature."""

    return content.startswith((b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"))


def _decode_text(content: bytes) -> str | None:
    """Decode UTF-8 text while rejecting binary-looking content."""

    if b"\x00" in content[:1024]:
        return None
    try:
        return content.decode("utf-8")
    except UnicodeDecodeError:
        return None


def _text_for_generic_extraction(
    content: bytes,
    *,
    detection: FormatDetection,
) -> str | None:
    """Return text eligible for generic extraction."""

    if detection.format_family in {
        DigitalFormatFamily.PLAIN_TEXT,
        DigitalFormatFamily.HTML,
        DigitalFormatFamily.XML,
        DigitalFormatFamily.JSON,
        DigitalFormatFamily.JSONL,
        DigitalFormatFamily.CSV,
        DigitalFormatFamily.TSV,
        DigitalFormatFamily.EMAIL,
    }:
        text = _decode_text(content)
        if text is None:
            return None
        if detection.format_family == DigitalFormatFamily.HTML:
            return _strip_markup(text)
        return text
    return None


def _looks_like_email(text: str) -> bool:
    """Return whether text resembles an RFC822 email message."""

    first_lines = text.splitlines()[:8]
    header_names = {line.split(":", 1)[0].lower() for line in first_lines if ":" in line}
    return {"from", "to", "subject"}.issubset(header_names) or {"from", "subject"}.issubset(
        header_names
    )


def _looks_like_jsonl(text: str) -> bool:
    """Return whether text resembles line-delimited JSON."""

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 2:
        return False
    try:
        return all(isinstance(json.loads(line), dict) for line in lines[:10])
    except json.JSONDecodeError:
        return False


def _looks_like_html(stripped_text: str) -> bool:
    """Return whether text resembles HTML."""

    lowered = stripped_text[:500].lower()
    return "<html" in lowered or "<!doctype html" in lowered or "<table" in lowered


def _looks_like_xml(stripped_text: str) -> bool:
    """Return whether text resembles XML."""

    if stripped_text.startswith("<?xml"):
        return True
    return bool(re.match(r"<[A-Za-z_][\w:.-]*(\s|>|/>)", stripped_text))


def _looks_like_csv(text: str) -> bool:
    """Return whether text resembles CSV/TSV using csv.Sniffer."""

    sample = text[:4096]
    if "\n" not in sample:
        return False
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
    except csv.Error:
        return False
    rows = list(csv.reader(StringIO(sample), dialect))
    return len(rows) >= 2 and len(rows[0]) >= 2


def _sniff_delimiter(text: str) -> str:
    """Return detected delimited-table delimiter."""

    try:
        return str(csv.Sniffer().sniff(text[:4096], delimiters=",\t;|").delimiter)
    except csv.Error:
        return ","


def _regex_values(
    kind: MaterialFactKind,
    pattern: re.Pattern[str],
    text: str,
) -> list[tuple[MaterialFactKind, str, str | None]]:
    """Extract regex values with context."""

    values: list[tuple[MaterialFactKind, str, str | None]] = []
    for match in pattern.finditer(text):
        value = match.group(1) if match.groups() else match.group(0)
        context = _context_for_match(text, match.start(), match.end())
        values.append((kind, value, context))
    return values


def _keyword_values(
    text: str,
) -> list[tuple[MaterialFactKind, str, str | None]]:
    """Extract construction-relevant keywords."""

    lowered = text.lower()
    values: list[tuple[MaterialFactKind, str, str | None]] = []
    for keyword in _CONSTRUCTION_KEYWORDS:
        if keyword in lowered:
            values.append((MaterialFactKind.KEYWORD, keyword, None))
    return values


def _context_for_match(text: str, start: int, end: int) -> str:
    """Return short deterministic context for an extracted match."""

    lower = max(0, start - 80)
    upper = min(len(text), end + 80)
    return " ".join(text[lower:upper].split())[:240]


def _strip_markup(text: str) -> str:
    """Strip simple HTML tags for generic extraction."""

    return re.sub(r"<[^>]+>", " ", text)


def _source_hints(payload: IntakeInspectionInput) -> dict[str, str]:
    """Return deterministic source hints."""

    hints: dict[str, str] = {}
    if payload.source_family:
        hints["source_family"] = payload.source_family
    if payload.source_url:
        hints["source_url"] = payload.source_url
    if payload.original_filename:
        hints["original_filename"] = payload.original_filename
    return hints


def _record_hints(facts: list[ExtractedMaterialFact]) -> dict[str, str]:
    """Return first extracted universal record hints by fact kind."""

    hints: dict[str, str] = {}
    for fact in facts:
        key = fact.fact_kind.value
        if key not in hints:
            hints[key] = fact.normalized_value or fact.value
    return hints


def _binary_preview(content: bytes) -> str:
    """Return deterministic binary preview."""

    return content[:16].hex()


def _text_preview(text: str) -> str:
    """Return deterministic text preview."""

    return " ".join(text.split())[:240]
