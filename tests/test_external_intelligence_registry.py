from constructionsight.external_intelligence_models import (
    CapabilityDomain,
    CapabilityEvidenceKind,
    ImplementationStatus,
    ReferencePlatform,
)
from constructionsight.external_intelligence_registry import (
    build_capability_gap_report,
    capability_matrix_rows,
    get_external_capabilities,
)


def test_external_capabilities_include_public_and_user_research_evidence() -> None:
    capabilities = get_external_capabilities(platform=ReferencePlatform.SHOVELS)
    evidence_kinds = {
        reference.evidence_kind
        for capability in capabilities
        for reference in capability.references
    }

    assert CapabilityEvidenceKind.PUBLIC_DOCUMENTATION in evidence_kinds
    assert CapabilityEvidenceKind.USER_RESEARCH in evidence_kinds


def test_external_capabilities_include_locked_shovels_schema_concepts() -> None:
    capabilities = get_external_capabilities(platform=ReferencePlatform.SHOVELS)
    claims = "\n".join(
        reference.claim for capability in capabilities for reference in capability.references
    )

    assert "PERMITS fields include ID" in claims
    assert "CONTRACTORS includes GROUP_ID" in claims
    assert "UNIVERSAL_PERSON" in claims
    assert "FIRST_SEEN_DATE" in claims


def test_regrid_capabilities_capture_parcel_geometry_and_resolution() -> None:
    capabilities = get_external_capabilities(platform=ReferencePlatform.REGRID)
    targets = "\n".join(capability.construction_sight_target for capability in capabilities)
    strategies = "\n".join(capability.improvement_strategy for capability in capabilities)

    assert "APN" in targets
    assert "geometry" in targets
    assert "parcel-first project graph" in strategies
    assert any(capability.domain == CapabilityDomain.PARCEL_GEOMETRY for capability in capabilities)


def test_capability_matrix_rows_are_filterable() -> None:
    capabilities = get_external_capabilities(domain=CapabilityDomain.GOVERNMENT_DECISIONS)
    rows = capability_matrix_rows(capabilities)

    assert rows
    assert {row["domain"] for row in rows} == {"government_decisions"}


def test_gap_report_separates_outperform_and_license_blocked_targets() -> None:
    report = build_capability_gap_report()

    assert report.capabilities_reviewed >= 10
    assert report.outperform_targets
    assert report.blocked_by_license
    assert all(
        gap.status == ImplementationStatus.OUTPERFORM_TARGET for gap in report.outperform_targets
    )
    assert all(
        gap.status == ImplementationStatus.BLOCKED_BY_LICENSE for gap in report.blocked_by_license
    )
