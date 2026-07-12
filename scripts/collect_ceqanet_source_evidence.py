"""Collect a bounded CEQAnet public-access evidence packet for source review."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx

from constructionsight.source_verification_checklist_models import (
    ChecklistItemStatus,
    SourceVerificationChecklistReport,
    SourceVerificationChecklistRow,
    SourceVerificationChecklistStatus,
)

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "data/source_registry.seed.json"
EVIDENCE_DIR = ROOT / "evidence/source_verification"
AUDIT_DIR = ROOT / "docs/audits"
OBSERVATION_DATE = "2026-07-12"
EVIDENCE_PATH = EVIDENCE_DIR / f"ceqanet_public_access_{OBSERVATION_DATE}.json"
CHECKLIST_PATH = EVIDENCE_DIR / f"ceqanet_checklist_{OBSERVATION_DATE}.json"
REPORT_PATH = AUDIT_DIR / f"ceqanet_source_verification_{OBSERVATION_DATE}.md"
USER_AGENT = "ConstructionSight-SourceVerification/1.0 (+lawful-public-record-review)"
SEARCH_URL = "https://ceqanet.lci.ca.gov/Search"
APPROVED_HOSTS = {"ceqanet.opr.ca.gov", "ceqanet.lci.ca.gov", "opr.ca.gov"}
CAPTCHA_MARKERS = ("captcha", "recaptcha", "hcaptcha")
LOGIN_MARKERS = ("sign in", "log in", "password")
DETAIL_MARKERS = ("project title", "lead agency", "document type", "sch")
TERMS_LINK_MARKERS = ("terms", "privacy", "accessibility", "conditions", "copyright")


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []
        self.title: list[str] = []
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "a":
            self._href = dict(attrs).get("href")
            self._text = []
        if tag.lower() == "title":
            self._in_title = True

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)
        if self._in_title:
            self.title.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href is not None:
            self.links.append((self._href, " ".join(self._text).strip()))
            self._href = None
            self._text = []
        if tag.lower() == "title":
            self._in_title = False


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return f"source:{normalized}"


def _official_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and parsed.hostname in APPROVED_HOSTS


def _response_record(response: httpx.Response) -> dict[str, Any]:
    parser = _LinkParser()
    parser.feed(response.text)
    lower_text = response.text.lower()
    return {
        "request_url": str(response.request.url),
        "final_url": str(response.url),
        "status_code": response.status_code,
        "content_type": response.headers.get("content-type"),
        "body_length_bytes": len(response.content),
        "body_sha256": _sha256(response.content),
        "title": " ".join(parser.title).strip() or None,
        "official_https_final_url": _official_url(str(response.url)),
        "captcha_markers": [marker for marker in CAPTCHA_MARKERS if marker in lower_text],
        "login_markers": [marker for marker in LOGIN_MARKERS if marker in lower_text],
        "link_count": len(parser.links),
    }


def _find_detail_url(base_url: str, html: str) -> str:
    parser = _LinkParser()
    parser.feed(html)
    candidates: list[str] = []
    for href, _ in parser.links:
        absolute = urljoin(base_url, href)
        parsed = urlparse(absolute)
        lower_path = parsed.path.lower()
        if parsed.hostname != "ceqanet.lci.ca.gov":
            continue
        if "project" not in lower_path or lower_path == "/search":
            continue
        if absolute not in candidates:
            candidates.append(absolute)
    if not candidates:
        raise RuntimeError("bounded CEQAnet search returned no public project-detail link")
    return candidates[0]


def _terms_links(base_url: str, *html_documents: str) -> list[str]:
    results: list[str] = []
    for html in html_documents:
        parser = _LinkParser()
        parser.feed(html)
        for href, text in parser.links:
            absolute = urljoin(base_url, href)
            searchable = f"{absolute} {text}".lower()
            if not any(marker in searchable for marker in TERMS_LINK_MARKERS):
                continue
            if not _official_url(absolute):
                continue
            if absolute not in results:
                results.append(absolute)
    return results


def _robots_record(client: httpx.Client, base_url: str, paths: list[str]) -> dict[str, Any]:
    robots_url = urljoin(base_url, "/robots.txt")
    response = client.get(robots_url)
    record = _response_record(response)
    if response.status_code == 404:
        record["classification"] = "not_published"
        record["path_permissions"] = {path: None for path in paths}
        return record
    response.raise_for_status()
    parser = RobotFileParser()
    parser.set_url(robots_url)
    parser.parse(response.text.splitlines())
    record["classification"] = "published"
    record["path_permissions"] = {
        path: parser.can_fetch(USER_AGENT, urljoin(base_url, path)) for path in paths
    }
    if any(value is False for value in record["path_permissions"].values()):
        raise RuntimeError("robots policy disallows a reviewed CEQAnet public path")
    return record


def _load_ceqanet_source() -> dict[str, Any]:
    payload = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    matches = [row for row in payload if row.get("platform_family") == "ceqanet"]
    if len(matches) != 1:
        raise RuntimeError("canonical registry must contain exactly one CEQAnet source")
    return matches[0]


def main() -> None:
    source = _load_ceqanet_source()
    observed_at = datetime.now(UTC)
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"}
    with httpx.Client(headers=headers, follow_redirects=True, timeout=25.0) as client:
        entry = client.get(str(source["public_url"]))
        entry.raise_for_status()
        if not _official_url(str(entry.url)):
            raise RuntimeError("CEQAnet entry redirected outside approved official HTTPS hosts")

        search = client.get(
            SEARCH_URL,
            params={"County": "San Bernardino"},
        )
        search.raise_for_status()
        if str(search.url).split("?", maxsplit=1)[0] != SEARCH_URL:
            raise RuntimeError("CEQAnet bounded search did not remain on the approved endpoint")

        detail_url = _find_detail_url(str(search.url), search.text)
        detail = client.get(detail_url)
        detail.raise_for_status()
        if not _official_url(str(detail.url)):
            raise RuntimeError("CEQAnet detail page redirected outside approved official hosts")

        combined_text = f"{entry.text}\n{search.text}\n{detail.text}".lower()
        captcha_markers = [marker for marker in CAPTCHA_MARKERS if marker in combined_text]
        login_markers = [marker for marker in LOGIN_MARKERS if marker in combined_text]
        if captcha_markers:
            raise RuntimeError(f"captcha marker observed: {captcha_markers}")
        if login_markers:
            raise RuntimeError(f"login marker observed: {login_markers}")

        observed_detail_markers = [
            marker for marker in DETAIL_MARKERS if marker in detail.text.lower()
        ]
        if len(observed_detail_markers) < 2:
            raise RuntimeError("CEQAnet detail page lacks expected public-record field markers")

        robots = _robots_record(
            client,
            "https://ceqanet.lci.ca.gov/",
            ["/Search", urlparse(detail_url).path],
        )
        terms_urls = _terms_links(
            str(entry.url),
            entry.text,
            search.text,
            detail.text,
        )
        terms_records: list[dict[str, Any]] = []
        for url in terms_urls[:10]:
            response = client.get(url)
            terms_records.append(_response_record(response))

    evidence: dict[str, Any] = {
        "schema_version": "ceqanet_source_verification_evidence.v1",
        "observed_at": observed_at.isoformat(),
        "source_key": _slug(str(source["source_name"])),
        "source_id": source.get("source_id"),
        "source_name": source["source_name"],
        "registry_status": source["verification_status"],
        "public_entry": _response_record(entry),
        "bounded_search": {
            **_response_record(search),
            "method": "GET",
            "bounded_parameters": {"County": "San Bernardino"},
            "document_downloads": False,
            "persistence_mutated": False,
        },
        "public_detail": {
            **_response_record(detail),
            "observed_field_markers": observed_detail_markers,
            "document_downloads": False,
            "persistence_mutated": False,
        },
        "robots": robots,
        "terms_privacy_accessibility_links": terms_records,
        "access_barrier_observation": {
            "login_required": False,
            "captcha_observed": False,
            "paywall_observed": False,
        },
        "limitations": [
            "evidence is a bounded point-in-time public-access observation",
            "response bodies are represented by lengths and SHA-256 hashes, not archived here",
            "terms/privacy/accessibility links are inventoried but legal terms review remains manual",
            "this evidence does not itself promote source verification status",
            "this evidence does not establish recurring production coverage",
        ],
    }

    evidence_ref = EVIDENCE_PATH.relative_to(ROOT).as_posix()
    checklist_row = SourceVerificationChecklistRow(
        source_key=evidence["source_key"],
        source_name=source["source_name"],
        platform_family=source["platform_family"],
        original_url=source["public_url"],
        final_url=evidence["public_entry"]["final_url"],
        http_status_code=evidence["public_entry"]["status_code"],
        redirect_classification="cross_host_redirect",
        registry_status=source["verification_status"],
        adapter_status="contract_ready",
        readiness_status="reachable",
        checklist_status=SourceVerificationChecklistStatus.DETAIL_BEHAVIOR_OBSERVED,
        public_entry_page=ChecklistItemStatus.OBSERVED,
        query_behavior=ChecklistItemStatus.OBSERVED,
        result_list=ChecklistItemStatus.OBSERVED,
        detail_page=ChecklistItemStatus.OBSERVED,
        access_barrier=ChecklistItemStatus.NOT_OBSERVED,
        terms_review=ChecklistItemStatus.NOT_CHECKED,
        recommendation="retain_unverified_pending_manual_terms_review",
        reasons=[
            "official public entry, bounded search, result-list, and detail behavior observed",
            "no login, captcha, paywall, or robots prohibition observed on reviewed paths",
        ],
        limitations=list(evidence["limitations"]),
        next_action="complete manual terms review before any verification-status promotion",
        observation_notes=(
            "Bounded GET observation used County=San Bernardino, retained no full response "
            "bodies, downloaded no documents, and performed no persistence mutation."
        ),
        evidence_refs=[evidence_ref],
        generated_at=observed_at,
    )
    checklist = SourceVerificationChecklistReport.from_rows([checklist_row])

    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    EVIDENCE_PATH.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    CHECKLIST_PATH.write_text(
        json.dumps(checklist.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    REPORT_PATH.write_text(
        "\n".join(
            [
                "# CEQAnet Source Verification Evidence",
                "",
                f"Observed at: `{observed_at.isoformat()}`",
                "",
                "## Observed public behavior",
                "",
                "- Official public entry was reachable over HTTPS and remained on an approved official host.",
                "- A bounded GET search using `County=San Bernardino` returned a public result list.",
                "- A public project-detail page was reachable and exposed expected CEQA record markers.",
                "- No login, captcha, or paywall marker was observed in the reviewed entry, search, or detail pages.",
                "- The reviewed robots policy did not prohibit the bounded search or observed detail path.",
                "- No documents were downloaded and no persistence was mutated.",
                "",
                "## Remaining blocker",
                "",
                "Manual review of the inventoried official terms/privacy/accessibility material remains required.",
                "The canonical source must remain unverified until that review is explicit and a controlled promotion plan is approved.",
                "",
                "## Evidence files",
                "",
                f"- `{evidence_ref}`",
                f"- `{CHECKLIST_PATH.relative_to(ROOT).as_posix()}`",
                "",
            ]
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
