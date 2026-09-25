"""Conservative public-source verifier.

The verifier classifies portal hints from a policy-bound retained public response. It
does not own an HTTP client, follow redirects, bypass authentication, captchas,
paywalls, access controls, or source terms.
"""

from __future__ import annotations

from dataclasses import dataclass

from constructionsight.http_transport_models import HttpExecutor
from constructionsight.legal import AccessDecision, SourceAccessProfile, evaluate_access
from constructionsight.models import PlatformFamily, PublicSource, SourceVerificationResult
from constructionsight.source_verification_http import fetch_source_verification


@dataclass(frozen=True)
class PortalHint:
    """Detected platform hint and confidence contribution."""

    platform_family: PlatformFamily
    confidence: int
    reason: str


class SourceVerifier:
    """Verify public source reachability and exposed portal traits."""

    def __init__(
        self,
        executor: HttpExecutor | None = None,
        timeout_seconds: float = 20.0,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.executor = executor
        self.timeout_seconds = timeout_seconds

    def verify(
        self,
        source: PublicSource,
        access_profile: SourceAccessProfile | None = None,
    ) -> SourceVerificationResult:
        """Verify one public source without crossing lawful-access boundaries."""

        access_profile = access_profile or SourceAccessProfile(
            public_url=str(source.public_url)
        )
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

        observation, policy = fetch_source_verification(
            source,
            timeout_seconds=self.timeout_seconds,
            executor=self.executor,
        )
        if not observation.succeeded:
            status_code = observation.status_code
            return SourceVerificationResult(
                source_name=source.source_name,
                public_url=source.public_url,
                url_reachable=False,
                portal_type_detected=PlatformFamily.UNKNOWN,
                public_search_available=False,
                login_required=(
                    True if status_code in {401, 403, 407} else None
                ),
                confidence_score=(25 if status_code in {401, 403} else 0),
                notes=(
                    "HTTP verification failed closed: "
                    f"{observation.failure_kind.value}"
                ),
                raw_observations={
                    "policy_id": observation.policy_id,
                    "status_code": status_code,
                    "final_url": observation.final_url,
                    "failure_kind": observation.failure_kind.value,
                    "error_type": observation.error_type,
                    "body_truncated": observation.body_truncated,
                    "response_size": observation.response_size,
                },
            )

        body_text = observation.decode_text(policy.accepted_encodings)
        lower_body = body_text.casefold()
        hint = self._detect_platform(observation.final_url, lower_body)
        assert observation.status_code is not None
        access_flags = self._detect_access_flags(lower_body, observation.status_code)
        public_search_available = self._detect_public_search(lower_body)
        pdfs_downloadable = ".pdf" in lower_body or "application/pdf" in lower_body

        confidence = self._score_confidence(
            status_code=observation.status_code,
            hint=hint,
            access_flags=access_flags,
            public_search_available=public_search_available,
        )

        return SourceVerificationResult(
            source_name=source.source_name,
            public_url=source.public_url,
            url_reachable=True,
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
                "policy_id": observation.policy_id,
                "status_code": observation.status_code,
                "final_url": observation.final_url,
                "content_type": observation.content_type,
                "content_encoding": observation.content_encoding,
                "response_size": observation.response_size,
                "body_truncated": observation.body_truncated,
                "failure_kind": observation.failure_kind.value,
                "access_flags": access_flags,
            },
        )

    @staticmethod
    def _detect_platform(url: str, lower_body: str) -> PortalHint:
        """Detect likely platform family from public URL/body hints."""

        lower_url = url.casefold()
        candidates: list[PortalHint] = []

        if "citizenaccess" in lower_url or "accela" in lower_url or "cap/caphome" in lower_body:
            candidates.append(
                PortalHint(PlatformFamily.ACCELA_ACA, 80, "Accela ACA URL/body hints detected.")
            )
        if "energov" in lower_url or "tylerhost" in lower_url or "energov" in lower_body:
            candidates.append(
                PortalHint(
                    PlatformFamily.TYLER_ENERGOV,
                    80,
                    "Tyler EnerGov URL/body hints detected.",
                )
            )
        if "ceqanet" in lower_url or "state clearinghouse" in lower_body:
            candidates.append(
                PortalHint(
                    PlatformFamily.CEQANET,
                    85,
                    "CEQAnet/State Clearinghouse hints detected.",
                )
            )
        if "cslb" in lower_url or "contractors state license board" in lower_body:
            candidates.append(PortalHint(PlatformFamily.CSLB, 85, "CSLB hints detected."))
        if "legistar" in lower_url or "granicus" in lower_url or "legistar" in lower_body:
            candidates.append(
                PortalHint(
                    PlatformFamily.GRANICUS_LEGISTAR,
                    75,
                    "Granicus/Legistar hints detected.",
                )
            )
        if "primegov" in lower_url or "civicplus" in lower_url or "civicclerk" in lower_body:
            candidates.append(
                PortalHint(
                    PlatformFamily.CIVICPLUS_PRIMEGOV,
                    70,
                    "PrimeGov/CivicPlus hints detected.",
                )
            )
        if "laserfiche" in lower_url or "weblink" in lower_url or "laserfiche" in lower_body:
            candidates.append(
                PortalHint(PlatformFamily.LASERFICHE, 70, "Laserfiche/WebLink hints detected.")
            )

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
