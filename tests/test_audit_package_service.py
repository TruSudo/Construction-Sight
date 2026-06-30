from constructionsight.source_verification_evidence_service import _redirect_classification
from constructionsight.source_verification_evidence_models import RedirectClassification


def test_redirect_classification_not_checked() -> None:
    result = _redirect_classification(
        "https://example.invalid/source",
        None,
        False,
    )

    assert result == RedirectClassification.NOT_CHECKED


def test_redirect_classification_cross_host() -> None:
    result = _redirect_classification(
        "https://example.invalid/source",
        "https://other.invalid/source",
        True,
    )

    assert result == RedirectClassification.CROSS_HOST_REDIRECT
