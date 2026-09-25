import pytest
from pydantic import ValidationError

from constructionsight.lead_dedupe_models import (
    LeadDuplicateResult,
    LeadDuplicateStatus,
    LeadFingerprint,
    canonical_lead_fingerprint_key,
)


def test_lead_fingerprint_requires_match_basis() -> None:
    with pytest.raises(ValidationError):
        LeadFingerprint(
            fingerprint_key=canonical_lead_fingerprint_key(
                site_key="site:test",
                source_key=None,
                source_record_id=None,
                normalized_title=None,
            ),
            base_candidate_id="candidate:test",
        )


def test_lead_fingerprint_accepts_site_key_basis() -> None:
    fingerprint = LeadFingerprint(
        fingerprint_key=canonical_lead_fingerprint_key(
            site_key="site:test",
            source_key=None,
            source_record_id=None,
            normalized_title=None,
        ),
        base_candidate_id="candidate:test",
        site_key="site:test",
    )

    assert fingerprint.site_key == "site:test"


def test_duplicate_result_requires_matched_keys_for_duplicate_status() -> None:
    fingerprint = LeadFingerprint(
        fingerprint_key=canonical_lead_fingerprint_key(
            site_key="site:test",
            source_key=None,
            source_record_id=None,
            normalized_title=None,
        ),
        base_candidate_id="candidate:test",
        site_key="site:test",
    )

    with pytest.raises(ValidationError):
        LeadDuplicateResult(
            result_id="lead-duplicate:test",
            status=LeadDuplicateStatus.DUPLICATE,
            candidate=fingerprint,
        )


def test_duplicate_result_rejects_duplicate_reasons() -> None:
    fingerprint = LeadFingerprint(
        fingerprint_key=canonical_lead_fingerprint_key(
            site_key="site:test",
            source_key=None,
            source_record_id=None,
            normalized_title=None,
        ),
        base_candidate_id="candidate:test",
        site_key="site:test",
    )

    with pytest.raises(ValidationError):
        LeadDuplicateResult(
            result_id="lead-duplicate:test",
            status=LeadDuplicateStatus.UNIQUE,
            candidate=fingerprint,
            reasons=["x", "x"],
        )


def test_duplicate_result_serializes() -> None:
    fingerprint = LeadFingerprint(
        fingerprint_key=canonical_lead_fingerprint_key(
            site_key="site:test",
            source_key=None,
            source_record_id=None,
            normalized_title=None,
        ),
        base_candidate_id="candidate:test",
        site_key="site:test",
    )
    result = LeadDuplicateResult(
        result_id="lead-duplicate:test",
        status=LeadDuplicateStatus.UNIQUE,
        candidate=fingerprint,
    )

    assert result.to_dict()["status"] == "unique"
