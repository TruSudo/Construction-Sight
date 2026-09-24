"""Separately governed identities for generic public-source HTTP reads."""

from __future__ import annotations

from constructionsight.http_transport_models import canonicalize_http_url
from constructionsight.models import PublicSource

_GOVERNED_SOURCE_URLS = frozenset(
    {
        "https://ceqanet.opr.ca.gov/",
        "https://ezop.sbcounty.gov/citizenaccess/",
        "https://rivcoplus.org/",
        "https://www.cslb.ca.gov/",
    }
)


def governed_source_url(source: PublicSource) -> str:
    """Return the exact reviewed URL or reject caller-controlled source authority."""

    url = canonicalize_http_url(str(source.public_url))
    if url not in _GOVERNED_SOURCE_URLS:
        raise ValueError("source URL is outside separately governed public-source authority")
    return url
