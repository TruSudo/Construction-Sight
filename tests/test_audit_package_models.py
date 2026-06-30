from constructionsight.source_verification_evidence_models import SourceVerificationEvidencePackage


def test_package_from_empty_rows_has_zero_counts() -> None:
    package = SourceVerificationEvidencePackage.from_rows([])

    assert package.source_count == 0
    assert package.recommendation_counts == {}
    assert package.redirect_counts == {}
