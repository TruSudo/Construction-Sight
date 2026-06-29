from constructionsight.external_gap_models import GapPriority
from constructionsight.external_gap_registry import (
    build_gap_alignment_report,
    gap_matrix_rows,
    get_implementation_steps,
    get_knowledge_gaps,
    get_research_findings,
    roadmap_rows,
)
from constructionsight.external_intelligence_models import ReferencePlatform


def test_research_findings_separate_regrid_and_shovels_roles() -> None:
    regrid_findings = get_research_findings(platform=ReferencePlatform.REGRID)
    shovels_findings = get_research_findings(platform=ReferencePlatform.SHOVELS)

    assert regrid_findings
    assert shovels_findings
    assert any("parcel" in finding.summary.lower() for finding in regrid_findings)
    assert any("permit" in finding.summary.lower() for finding in shovels_findings)


def test_critical_knowledge_gaps_prioritize_schema_import_and_transitions() -> None:
    critical_gaps = get_knowledge_gaps(priority=GapPriority.CRITICAL)
    gap_keys = {gap.gap_key for gap in critical_gaps}

    assert "regrid:parcel-schema-preview" in gap_keys
    assert "regrid:parcel-import-preview" in gap_keys
    assert "shovels:permit-snapshot-transition" in gap_keys
    assert "constructionsight:opportunity-enrichment" in gap_keys


def test_platform_filter_returns_shovels_gaps_only() -> None:
    gaps = get_knowledge_gaps(platform=ReferencePlatform.SHOVELS)

    assert gaps
    assert all(gap.platform == ReferencePlatform.SHOVELS for gap in gaps)


def test_gap_alignment_report_includes_next_steps() -> None:
    report = build_gap_alignment_report()

    assert report.findings_reviewed >= 3
    assert report.gaps_reviewed >= 7
    assert report.roadmap_steps >= 5
    assert report.critical_gaps
    assert report.high_gaps
    assert report.next_steps[0].step_key == "parcel-source-schema-preview"


def test_gap_matrix_rows_are_machine_readable() -> None:
    rows = gap_matrix_rows(get_knowledge_gaps(platform=ReferencePlatform.REGRID))

    assert rows
    assert {row["platform"] for row in rows} == {"regrid"}
    assert rows[0]["gap_key"]
    assert rows[0]["suggested_pr"]


def test_roadmap_rows_preserve_sequence() -> None:
    steps = get_implementation_steps()
    rows = roadmap_rows(steps)

    assert [step.sequence for step in steps] == sorted(step.sequence for step in steps)
    assert rows[0]["sequence"] == "1"
    assert rows[0]["title"] == "Parcel source schema preview"
