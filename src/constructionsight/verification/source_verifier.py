"""Conservative public-source verifier.

The verifier performs lightweight public reachability checks and classifies portal
hints from response metadata/body text. It does not bypass authentication,
captchas, paywalls, access controls, or source terms.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import httpx

from constructionsight.legal import AccessDecision, SourceAccessProfile, evaluate_access
from constructionsight.models import PlatformFamily, PublicSource, SourceVerificationResult


class HttpClient(Protocol):
    """Minimal sync HTTP client protocol used by the verifier."""

    def get(self, url: str, *, follow_redirects: bool, timeout: float) -> httpx.Response:
        """Fetch a URL."""


@dataclass(frozen=True)
class PortalHint:
    """Detected platform hint and confidence contribution."""

    platform_family: PlatformFamily
    confidence: int
    reason: str


class SourceVerifier:
    """Verify public source reachability and basic exposed portal traits."""

    def __init__(self, client: HttpClient | None = None, timeout_seconds: float = 20.0) -> None:
        self.client = client or httpx.Client(headers={"User-Agent": "ConstructionSight/0.1"})
        self.timeout_seconds = timeout_seconds

    def verify(self, source: PublicSource) -> SourceVerificationResult:
        """Verify a public source without crossing lawful-access boundaries."""

        access_profile = SourceAccessProfile(public_url=str(source.public_url))
        access_result = evaluate_access(access_profile)
        if access_result.decision is not AccessDecision.ALLOWED:
            return SourceVerificationResult(
                source_name=source.source_name,
                public_url=source.public_url,
                url_reachable=False,
                portal_type_detected=PlatformFamily.UNKNOWN,
                confidence_score=0,
                notes=access_result.reason,
                raw_observations={"access_decision": access_result.decision.value},
            )

        try:
            response = self.client.get(
                str(source.public_url),
                follow_redirects=True,
                timeout=self.timeout_seconds,
            )
        except httpx.HTTPError as exc:
            return SourceVerificationResult(
                source_name=source.source_name,
                public_url=source.public_url,
                url_reachable=False,
                portal_type_detected=PlatformFamily.UNKNOWN,
                confidence_score=0,
                notes=f"HTTP request failed: {exc.__class__.__name__}",
                raw_observations={"error": str(exc)},
            )

        body_text = response.text[:50_000]
        lower_body = body_text.lower()
        hint = self._detect_platform(str(response.url), lower_body)
        access_flags = self._detect_access_flags(lower_body, response.status_code)
        public_search_available = self._detect_public_search(lower_body)
        pdfs_downloadable = ".pdf" in lower_body or "application/pdf" in lower_body

        confidence = self._score_confidence(
            status_code=response.status_code,
            hint=hint,
            access_flags=access_flags,
            public_search_available=public_search_available,
        )

        return SourceVerificationResult(
            source_name=source.source_name,
            public_url=source.public_url,
            url_reachable=200 <= response.status_code < 400,
            portal_type_detected=hint.platform_family,
            public_search_available=public_search_available,
            login_required=access_flags["login_required"],
            permit_details_visible=self._detect_permit_terms(lower_body),
            agenda_packets_visible=self._detect_agenda_terms(lower_body),
            pdfs_downloadable=pdfs_downloadable,
            contractor_owner_applicant_fields_visible=self._detect_party_terms(lower_body),
            evidence_snapshot_text=self._snapshot(body_text),
            confidence_score=confidence,
            notes=hint.reason,
            raw_observations={
                "status_code": response.status_code,
                "final_url": str(response.url),
                "content_type": response.headers.get("content-type"),
                "access_flags": access_flags,
            },
        )

    @staticmethod
    def _detect_platform(url: str, lower_body: str) -> PortalHint:
        """Detect likely platform family from public URL/body hints."""

        lower_url = url.lower()
        candidates: list[PortalHint] = []

        if "citizenaccess" in lower_url or "accela" in lower_url or "cap/caphome" in lower_body:
            candidates.append(PortalHint(PlatformFamily.ACCELA_ACA, 80, "Accela ACA URL/body hints detected."))
        if "energov" in lower_url or "tylerhost" in lower_url or "energov" in lower_body:
            candidates.append(PortalHint(PlatformFamily.TYLER_ENERGOV, 80, "Tyler EnerGov URL/body hints detected."))
        if "ceqanet" in lower_url or "state clearinghouse" in lower_body:
            candidates.append(PortalHint(PlatformFamily.CEQANET, 85, "CEQAnet/State Clearinghouse hints detected."))
        if "cslb" in lower_url or "contractors state license board" in lower_body:
            candidates.append(PortalHint(PlatformFamily.CSLB, 85, "CSLB hints detected."))
        if "legistar" in lower_url or "granicus" in lower_url or "legistar" in lower_body:
            candidates.append(PortalHint(PlatformFamily.GRANICUS_LEGISTAR, 75, "Granicus/Legistar hints detected."))
        if "primegov" in lower_url or "civicplus" in lower_url or "civicclerk" in lower_body:
            candidates.append(PortalHint(PlatformFamily.CIVICPLUS_PRIMEGOV, 70, "PrimeGov/CivicPlus hints detected."))
        if "laserfiche" in lower_url or "weblink" in lower_url or "laserfiche" in lower_body:
            candidates.append(PortalHint(PlatformFamily.LASERFICHE, 70, "Laserfiche/WebLink hints detected."))

        if not candidates:
            return PortalHint(PlatformFamily.UNKNOWN, 20, "No strong platform hints detected.")
        return max(candidates, key=lambda item: item.confidence)

    @staticmethod
    def _detect_access_flags(lower_body: str, status_code: int) -> dict[str, bool]:
        """Detect access-warning flags from a public response."""

        return {
            "login_required": status_code in {401, 403}
            or "login" in lower_body
            and "password" in lower_body,
            "captcha_detected": "captcha" in lower_body or "recaptcha" in lower_body,
            "paywall_detected": "payment required" in lower_body or "subscribe" in lower_body,
            "robots_warning": "robots.txt" in lower_body and "disallow" in lower_body,
        }

    @staticmethod
    def _detect_public_search(lower_body: str) -> bool:
        """Detect whether public search terms appear on the response."""

        terms = (
            "search",
            "record search",
            "permit search",
            "agenda search",
            "project search",
            "license search",
            "advanced search",
        )
        return any(term in lower_body for term in terms)

    @staticmethod
    def _detect_permit_terms(lower_body: str) -> bool:
        """Detect permit/detail terms."""

        terms = ("permit", "record detail", "inspection", "plan check", "application")
        return any(term in lower_body for term in terms)

    @staticmethod
    def _detect_agenda_terms(lower_body: str) -> bool:
        """Detect agenda packet terms."""

        terms = ("agenda", "minutes", "staff report", "planning commission", "city council")
        return any(term in lower_body for term in terms)

    @staticmethod
    def _detect_party_terms(lower_body: str) -> bool:
        """Detect contractor/owner/applicant field hints."""

        terms = ("contractor", "owner", "applicant", "licensed professional", "developer")
        return any(term in lower_body for term in terms)

    @staticmethod
    def _snapshot(body_text: str, max_chars: int = 2_000) -> str:
        """Create a compact evidence snapshot from response text."""

        collapsed = " ".join(body_text.split())
        return collapsed[:max_chars]

    @staticmethod
    def _score_confidence(
        *,
        status_code: int,
        hint: PortalHint,
        access_flags: dict[str, bool],
        public_search_available: bool,
    ) -> int:
        """Compute a conservative verification confidence score."""

        if status_code >= 500:
            return 10
        if status_code in {401, 403}:
            return 25

        score = 30 if 200 <= status_code < 400 else 15
        score += min(hint.confidence, 50)
        if public_search_available:
            score += 10
        if access_flags["captcha_detected"] or access_flags["paywall_detected"]:
            score -= 30
        if access_flags["login_required"]:
            score -= 20

        return max(0, min(score, 100))
