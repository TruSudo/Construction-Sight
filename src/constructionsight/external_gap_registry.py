"""Research-aligned Shovels/Regrid implementation gap registry."""

from __future__ import annotations

from collections.abc import Iterable

from constructionsight.external_gap_models import (
    EvidenceStrength,
    GapAlignmentReport,
    GapPriority,
    ImplementationRisk,
    ImplementationStep,
    KnowledgeGap,
    ResearchFinding,
)
from constructionsight.external_intelligence_models import ReferencePlatform


def get_research_findings(
    *,
    platform: ReferencePlatform | None = None,
) -> list[ResearchFinding]:
    """Return durable research findings, optionally filtered by platform."""

    findings = _research_findings()
    if platform is not None:
        findings = [finding for finding in findings if finding.platform == platform]
    return findings


def get_knowledge_gaps(
    *,
    platform: ReferencePlatform | None = None,
    priority: GapPriority | None = None,
) -> list[KnowledgeGap]:
    """Return actionable knowledge gaps, optionally filtered."""

    gaps = _knowledge_gaps()
    if platform is not None:
        gaps = [gap for gap in gaps if gap.platform == platform]
    if priority is not None:
        gaps = [gap for gap in gaps if gap.priority == priority]
    return gaps


def get_implementation_steps() -> list[ImplementationStep]:
    """Return the recommended implementation roadmap."""

    return _implementation_steps()


def build_gap_alignment_report() -> GapAlignmentReport:
    """Build a deterministic Shovels/Regrid alignment report."""

    findings = get_research_findings()
    gaps = get_knowledge_gaps()
    steps = get_implementation_steps()
    return GapAlignmentReport(
        report_id="shovels-regrid-gap-alignment:v1",
        findings_reviewed=len(findings),
        gaps_reviewed=len(gaps),
        roadmap_steps=len(steps),
        critical_gaps=[gap for gap in gaps if gap.priority == GapPriority.CRITICAL],
        high_gaps=[gap for gap in gaps if gap.priority == GapPriority.HIGH],
        next_steps=steps[:5],
    )


def gap_matrix_rows(gaps: Iterable[KnowledgeGap] | None = None) -> list[dict[str, str]]:
    """Return compact gap rows for CLI and UI tables."""

    reviewed = list(gaps if gaps is not None else get_knowledge_gaps())
    return [
        {
            "gap_key": gap.gap_key,
            "platform": gap.platform.value,
            "capability": gap.capability,
            "priority": gap.priority.value,
            "suggested_pr": gap.suggested_pr,
            "dependency": gap.construction_sight_dependency,
            "lawful_path_to_answer": gap.lawful_path_to_answer,
        }
        for gap in reviewed
    ]


def roadmap_rows(steps: Iterable[ImplementationStep] | None = None) -> list[dict[str, str]]:
    """Return compact implementation roadmap rows."""

    reviewed = list(steps if steps is not None else get_implementation_steps())
    return [
        {
            "sequence": str(step.sequence),
            "step_key": step.step_key,
            "title": step.title,
            "risk": step.risk.value,
            "goal": step.goal,
            "why_it_matters": step.why_it_matters,
        }
        for step in reviewed
    ]


def _research_findings() -> list[ResearchFinding]:
    """Return vetted findings from the Shovels/Regrid gap research."""

    return [
        ResearchFinding(
            finding_key="regrid:parcel-identity-spine",
            platform=ReferencePlatform.REGRID,
            title="Regrid is the parcel identity and geometry spine",
            summary=(
                "Regrid-style functionality centers on stable parcel identity, "
                "parcel paths, GeoJSON parcel responses, schemas, tiles, feature "
                "service, batch point lookup, and bulk delivery."
            ),
            evidence_strength=EvidenceStrength.VERIFIED_PUBLIC_DOCS,
            source_names=[
                "Regrid API docs",
                "Regrid schema endpoints",
                "Regrid ID documentation",
                "Regrid tiles and feature-service documentation",
            ],
            construction_sight_implication=(
                "ConstructionSight should treat parcel records and geometry as the "
                "base substrate for site resolution, maps, imports, and graph joins."
            ),
        ),
        ResearchFinding(
            finding_key="shovels:event-actor-overlay",
            platform=ReferencePlatform.SHOVELS,
            title="Shovels is the permit, contractor, decision, and actor overlay",
            summary=(
                "Shovels-style functionality centers on permit search, contractor "
                "search, contractor employees, contractor metrics, address search, "
                "residents, decisions, release metadata, and coverage metadata."
            ),
            evidence_strength=EvidenceStrength.VERIFIED_PUBLIC_DOCS,
            source_names=[
                "Shovels API docs",
                "Shovels data dictionary",
                "Shovels data-feed documentation",
            ],
            construction_sight_implication=(
                "ConstructionSight should model permit snapshots, permit transitions, "
                "contractor identity, decisions, and coverage checks as overlays on "
                "the parcel/site spine."
            ),
        ),
        ResearchFinding(
            finding_key="constructionsight:timing-advantage",
            platform=ReferencePlatform.CONSTRUCTIONSIGHT,
            title="ConstructionSight advantage is cross-layer timing intelligence",
            summary=(
                "The differentiated product should detect what changed, when it "
                "changed, who is connected, which parcel is affected, and why that "
                "movement creates a security-sales opportunity."
            ),
            evidence_strength=EvidenceStrength.RESEARCH_INFERENCE,
            source_names=["ConstructionSight research synthesis"],
            construction_sight_implication=(
                "Do not merely clone vendor surfaces; build transition scoring, "
                "evidence-backed outreach, and opportunity explanations on top of "
                "parcel, permit, contractor, and decision signals."
            ),
        ),
    ]


def _knowledge_gaps() -> list[KnowledgeGap]:
    """Return the prioritized gap matrix from the research."""

    return [
        KnowledgeGap(
            gap_key="regrid:parcel-schema-preview",
            platform=ReferencePlatform.REGRID,
            capability="parcel schema preview",
            what_we_know=(
                "Regrid exposes parcel and add-on schema concepts, grouped field "
                "documentation, and plan-dependent standard/premium field behavior."
            ),
            what_we_do_not_know=(
                "Which fields are available in a future trial or licensed account "
                "for San Bernardino and Riverside workflows."
            ),
            why_it_matters=(
                "Import, field mapping, confidence scoring, and coverage warnings "
                "must be driven by observed schema instead of hard-coded hope."
            ),
            lawful_path_to_answer=(
                "Use public schema documentation now; later compare with a lawful "
                "trial/API response or user-provided licensed export."
            ),
            construction_sight_dependency="parcel source registry",
            priority=GapPriority.CRITICAL,
            suggested_pr="PR 46: parcel source schema preview",
            acceptance_criteria=[
                "Schema preview lists canonical fields, observed source fields, and gaps",
                "Preview output is JSON-serializable and test-backed",
                "No live import occurs during schema preview",
            ],
        ),
        KnowledgeGap(
            gap_key="regrid:parcel-import-preview",
            platform=ReferencePlatform.REGRID,
            capability="parcel import preview",
            what_we_know=(
                "Regrid-style bulk and API flows support CSV, GeoJSON, WKT-like, "
                "feature, and batch-oriented parcel onboarding patterns."
            ),
            what_we_do_not_know=(
                "Which source format will be available first for ConstructionSight: "
                "open county export, user-provided file, or licensed Regrid sample."
            ),
            why_it_matters=(
                "ConstructionSight needs safe row counts, field mapping, geometry "
                "sniffing, and validation before any parcel data is persisted."
            ),
            lawful_path_to_answer=(
                "Build fixture-based import preview now; later validate against lawful "
                "county files or user-provided licensed exports."
            ),
            construction_sight_dependency="parcel source schema preview",
            priority=GapPriority.CRITICAL,
            suggested_pr="PR 47: parcel import preview",
            acceptance_criteria=[
                "CSV and GeoJSON fixtures produce preview reports",
                "Preview reports identify APN, address, centroid, and geometry candidates",
                "Invalid rows are reported without persistence",
            ],
        ),
        KnowledgeGap(
            gap_key="regrid:parcel-record-geometry",
            platform=ReferencePlatform.REGRID,
            capability="ParcelRecord and geometry normalization",
            what_we_know=(
                "Regrid-style parcels require stable IDs, source lineage, centroid "
                "fields, Polygon/MultiPolygon support, and geometry-aware matching."
            ),
            what_we_do_not_know=(
                "Which geometry format and coordinate quality will arrive from the "
                "first actual parcel source."
            ),
            why_it_matters=(
                "A parcel-backed site resolver needs a canonical parcel object and a "
                "geometry abstraction before graph linking or map output can be sane."
            ),
            lawful_path_to_answer=(
                "Implement provider-neutral geometry models and test them with public "
                "fixtures before wiring live sources."
            ),
            construction_sight_dependency="parcel import preview",
            priority=GapPriority.CRITICAL,
            suggested_pr="PR 48: ParcelRecord and geometry normalization",
            acceptance_criteria=[
                "ParcelRecord stores source key, parcel identifier, APN, address, and lineage",
                "Polygon and MultiPolygon fixtures normalize into one internal contract",
                "Centroid and envelope are deterministic",
            ],
        ),
        KnowledgeGap(
            gap_key="shovels:permit-snapshot-transition",
            platform=ReferencePlatform.SHOVELS,
            capability="PermitSnapshot and PermitTransition",
            what_we_know=(
                "Shovels-style permit data exposes permit status, lifecycle dates, "
                "job value, fees, tags, durations, inspection pass rate, contractors, "
                "property attributes, and geography identifiers."
            ),
            what_we_do_not_know=(
                "Exact county freshness, edge cases for reopened/late-changing permits, "
                "and whether county-native feeds beat vendor latency."
            ),
            why_it_matters=(
                "Permit transitions are the direct sales trigger for issued permits, "
                "contractor movement, valuation changes, inspections, and finalization."
            ),
            lawful_path_to_answer=(
                "Model snapshots from public documented fields; validate edge cases "
                "against lawful trial data or county-native public permit snapshots."
            ),
            construction_sight_dependency="project/site graph linkage",
            priority=GapPriority.CRITICAL,
            suggested_pr="PR 51: PermitSnapshot and PermitTransition",
            acceptance_criteria=[
                "Permit snapshots are idempotent by source and source record key",
                "Transition detector emits no-op, new, status, value, and contractor changes",
                "Every transition preserves source evidence and limitations",
            ],
        ),
        KnowledgeGap(
            gap_key="shovels:contractor-identity-metrics",
            platform=ReferencePlatform.SHOVELS,
            capability="contractor identity and metrics",
            what_we_know=(
                "Shovels-style contractor intelligence includes contractor identity, "
                "licenses, business attributes, employees, permit counts, job values, "
                "durations, inspection pass rates, and monthly metrics."
            ),
            what_we_do_not_know=(
                "How much identity collision will exist in county-native data and "
                "which contact/enrichment fields are licensed versus public."
            ),
            why_it_matters=(
                "Security outreach often targets a GC, subcontractor, owner, or project "
                "operator; bad contractor identity creates bad outreach."
            ),
            lawful_path_to_answer=(
                "Build contractor models and CSLB enrichment from public data; treat "
                "contact/audience fields as licensed unless independently lawful."
            ),
            construction_sight_dependency="PermitSnapshot and PermitTransition",
            priority=GapPriority.HIGH,
            suggested_pr="PR 53: contractor identity and CSLB enrichment",
            acceptance_criteria=[
                "Contractors dedupe by conservative license/name rules",
                "CSLB enrichment is separate from licensed audience/contact fields",
                "Contractor metrics can be derived from ConstructionSight permit history",
            ],
        ),
        KnowledgeGap(
            gap_key="shovels:decision-parcel-matching",
            platform=ReferencePlatform.SHOVELS,
            capability="government decisions and decision-to-parcel matching",
            what_we_know=(
                "Shovels-style decisions expose decision date, source URL, category, "
                "zoning changes, allowed uses, project value, parties, and geography."
            ),
            what_we_do_not_know=(
                "San Bernardino/Riverside decision coverage quality, match rate to parcels, "
                "and whether local agenda ingestion will outperform vendor coverage."
            ),
            why_it_matters=(
                "Decisions and CEQA can expose project movement before permits, which is "
                "central to ConstructionSight's early lead timing advantage."
            ),
            lawful_path_to_answer=(
                "Model decisions from documented fields and validate with local public "
                "agendas, staff reports, CEQA notices, and lawful trial samples."
            ),
            construction_sight_dependency="parcel-backed site resolver",
            priority=GapPriority.HIGH,
            suggested_pr="PR 55: decision record and decision-to-parcel matching",
            acceptance_criteria=[
                "Decision records preserve source URL and parties",
                "High-confidence parcel matches are separated from review-needed matches",
                "Decision signals can feed opportunity scoring before permits exist",
            ],
        ),
        KnowledgeGap(
            gap_key="constructionsight:opportunity-enrichment",
            platform=ReferencePlatform.CONSTRUCTIONSIGHT,
            capability="opportunity enrichment and timing score",
            what_we_know=(
                "The winning product is a cross-layer timing model: parcel movement, "
                "permit transition, contractor signal, decision signal, and evidence."
            ),
            what_we_do_not_know=(
                "Which signal weights best predict security-sales conversion for Ron's "
                "actual workflow."
            ),
            why_it_matters=(
                "This is where ConstructionSight can beat generic parcel or permit data vendors."
            ),
            lawful_path_to_answer=(
                "Start with explainable deterministic scoring; tune only after real sales feedback."
            ),
            construction_sight_dependency=("parcel, permit, contractor, and decision primitives"),
            priority=GapPriority.CRITICAL,
            suggested_pr="PR 57: opportunity enrichment from parcel, permit, contractor, decision",
            acceptance_criteria=[
                "Opportunity scores explain every contributing signal",
                "Confidence penalties reflect stale or missing source data",
                "Outreach preview can cite source evidence and limitations",
            ],
        ),
    ]


def _implementation_steps() -> list[ImplementationStep]:
    """Return the next implementation sequence."""

    return [
        ImplementationStep(
            step_key="parcel-source-schema-preview",
            sequence=1,
            title="Parcel source schema preview",
            goal=("Inspect a parcel source's expected or observed schema before import."),
            likely_files=[
                "src/constructionsight/parcel_schema_models.py",
                "src/constructionsight/parcel_schema_preview.py",
                "src/constructionsight/parcel_source_cli.py",
            ],
            required_tests=[
                "schema model validation tests",
                "preview service fixture tests",
                "CLI JSON/table tests",
            ],
            acceptance_criteria=[
                "Preview reports canonical APN/address/owner/geometry candidates",
                "Required missing fields are reported as gaps",
                "No import or persistence occurs",
            ],
            risk=ImplementationRisk.LOW,
            why_it_matters="It removes field-mapping guesswork before live parcel ingestion.",
            unlocks=["parcel import preview", "ParcelRecord model"],
        ),
        ImplementationStep(
            step_key="parcel-import-preview",
            sequence=2,
            title="Parcel import preview",
            goal="Preview rows and geometry from lawful parcel files or sample payloads.",
            likely_files=[
                "src/constructionsight/parcel_import_models.py",
                "src/constructionsight/parcel_import_preview.py",
                "tests/fixtures/parcel_sources/",
            ],
            required_tests=[
                "CSV fixture tests",
                "GeoJSON fixture tests",
                "invalid-row reporting tests",
            ],
            acceptance_criteria=[
                "Preview reports row count, accepted rows, rejected rows, and limitations",
                "APN/address/geometry field candidates are detected",
                "Preview output is deterministic JSON",
            ],
            risk=ImplementationRisk.MEDIUM,
            why_it_matters="It creates safe ingestion visibility before data enters storage.",
            unlocks=["ParcelRecord model", "geometry normalization"],
        ),
        ImplementationStep(
            step_key="parcel-record-geometry",
            sequence=3,
            title="ParcelRecord and geometry normalization",
            goal="Create the internal parcel object and canonical geometry contract.",
            likely_files=[
                "src/constructionsight/parcel_models.py",
                "src/constructionsight/parcel_geometry.py",
                "tests/test_parcel_geometry.py",
            ],
            required_tests=[
                "stable parcel key tests",
                "Polygon/MultiPolygon normalization tests",
                "centroid/envelope tests",
            ],
            acceptance_criteria=[
                "ParcelRecord preserves source lineage and source record identity",
                "Geometry fixtures normalize consistently",
                "Malformed geometry produces limitations rather than silent corruption",
            ],
            risk=ImplementationRisk.MEDIUM,
            why_it_matters="It turns site resolution into real parcel-backed intelligence.",
            unlocks=["site resolver enrichment", "project/site graph linkage"],
        ),
        ImplementationStep(
            step_key="site-resolver-parcel-enrichment",
            sequence=4,
            title="Site resolver enrichment from parcels",
            goal="Resolve APN/address/coordinate hints against ParcelRecord candidates.",
            likely_files=[
                "src/constructionsight/site_resolution_service.py",
                "src/constructionsight/parcel_match_service.py",
            ],
            required_tests=[
                "exact APN match tests",
                "address fallback tests",
                "ambiguous candidate ranking tests",
            ],
            acceptance_criteria=[
                "Resolver returns parcel-backed candidates with confidence and reasons",
                "Conflicts are preserved for review",
                "No vendor is treated as infallible",
            ],
            risk=ImplementationRisk.MEDIUM,
            why_it_matters="It attaches messy public records to the parcel spine.",
            unlocks=["project/site graph linkage", "permit snapshot matching"],
        ),
        ImplementationStep(
            step_key="permit-transition-spine",
            sequence=5,
            title="Permit snapshot and transition detector",
            goal="Represent permit snapshots and detect source-field movement over time.",
            likely_files=[
                "src/constructionsight/permit_snapshot_models.py",
                "src/constructionsight/permit_transition_service.py",
            ],
            required_tests=[
                "snapshot idempotency tests",
                "status transition tests",
                "valuation and contractor-change tests",
            ],
            acceptance_criteria=[
                "Permit changes emit transition events with source evidence",
                "No-op refreshes do not create false opportunities",
                "Transitions can feed opportunity scoring",
            ],
            risk=ImplementationRisk.MEDIUM,
            why_it_matters="It creates the Shovels-like event layer ConstructionSight needs.",
            unlocks=["contractor identity", "opportunity enrichment"],
        ),
    ]
