from constructionsight.lead_dedupe_models import LeadDuplicateStatus
from constructionsight.lead_dedupe_service import (
    build_lead_fingerprint,
    check_lead_duplicate,
    normalize_lead_title,
)
from constructionsight.lead_review_models import LeadReviewPackage, LeadReviewStatus


def _package(candidate_id: str = "candidate:test", score: int = 80) -> LeadReviewPackage:
    return LeadReviewPackage(
        package_id="lead-review:test",
        base_candidate_id=candidate_id,
        lead_score=score,
        status=LeadReviewStatus.MONITOR,
        summary="test package",
    )


def test_normalize_lead_title_is_deterministic() -> None:
    assert normalize_lead_title("  Warehouse - Phase II ") == "WAREHOUSE PHASE II"


def test_build_lead_fingerprint_is_deterministic() -> None:
    first = build_lead_fingerprint(
        package=_package(),
        site_key="site:test",
        source_key="permit:test",
        source_record_id="1",
        title="Warehouse Phase II",
    )
    second = build_lead_fingerprint(
        package=_package(),
        site_key="site:test",
        source_key="permit:test",
        source_record_id="1",
        title="warehouse phase ii",
    )

    assert first.fingerprint_key == second.fingerprint_key
    assert first.normalized_title == "WAREHOUSE PHASE II"


def test_check_lead_duplicate_detects_exact_duplicate() -> None:
    existing = build_lead_fingerprint(package=_package(), site_key="site:test")
    candidate = build_lead_fingerprint(package=_package(), site_key="site:test")

    result = check_lead_duplicate(candidate, [existing])

    assert result.status == LeadDuplicateStatus.DUPLICATE
    assert result.matched_fingerprint_keys == [existing.fingerprint_key]
    assert result.reasons == ["exact lead fingerprint already exists"]


def test_check_lead_duplicate_detects_same_source_review() -> None:
    existing = build_lead_fingerprint(
        package=_package(),
        source_key="permit:test",
        source_record_id="1",
    )
    candidate = build_lead_fingerprint(
        package=_package("candidate:new"),
        source_key="permit:test",
        source_record_id="1",
        title="Different Title",
    )

    result = check_lead_duplicate(candidate, [existing])

    assert result.status == LeadDuplicateStatus.REVIEW_NEEDED
    assert result.matched_fingerprint_keys == [existing.fingerprint_key]
    assert result.reasons == ["same source record appears in existing lead"]


def test_check_lead_duplicate_returns_unique() -> None:
    existing = build_lead_fingerprint(package=_package(), site_key="site:old")
    candidate = build_lead_fingerprint(package=_package("candidate:new"), site_key="site:new")

    result = check_lead_duplicate(candidate, [existing])

    assert result.status == LeadDuplicateStatus.UNIQUE
    assert result.matched_fingerprint_keys == []
    assert result.reasons == ["no duplicate lead fingerprint found"]
