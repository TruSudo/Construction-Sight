"""Apply and validate evidence-bound source verification metadata governance."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from constructionsight.adapters import default_adapter_family_specs
from constructionsight.models import PublicSource
from constructionsight.source_verification_checklist_models import (
    SourceVerificationChecklistReport,
    SourceVerificationObservation,
)
from constructionsight.source_verification_checklist_service import (
    build_source_verification_checklist_report,
)

ROOT = Path(__file__).resolve().parents[1]
DATE = "2026-07-12"
EVIDENCE_DIR = ROOT / "evidence/source_verification"
OBSERVATIONS_PATH = EVIDENCE_DIR / f"ceqanet_observations_{DATE}.json"
CHECKLIST_PATH = EVIDENCE_DIR / f"ceqanet_verified_checklist_{DATE}.json"
PLAN_PATH = EVIDENCE_DIR / f"ceqanet_verification_metadata_update_plan_{DATE}.json"
AUDIT_PATH = EVIDENCE_DIR / f"ceqanet_verification_metadata_apply_audit_{DATE}.json"
REGISTRY_PATH = ROOT / "data/source_registry.seed.json"
REPORT_PATH = ROOT / f"docs/audits/ceqanet_verified_maturity_{DATE}.md"
SOURCE_NAME = "CEQAnet State Clearinghouse"
EXPECTED_PROVENANCE = (
    "Evidence-backed source review completed 2026-07-12. Verification status: verified. "
    "Evidence refs: evidence/source_verification/ceqanet_public_access_2026-07-12.json; "
    "evidence/source_verification/ceqanet_terms_review_2026-07-12.json."
)


def _replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected one patch anchor in {path}: {old!r}; found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def patch() -> None:
    _patch_checklist_models()
    _patch_checklist_service()
    _patch_promotion_models()
    _patch_promotion_service()
    _patch_update_plan_service()
    _patch_apply_models()
    _patch_apply_service()
    _patch_registry_tests()
    _patch_verified_source_test()
    _patch_observation_artifact()
    _patch_documentation()


def _patch_checklist_models() -> None:
    path = ROOT / "src/constructionsight/source_verification_checklist_models.py"
    _replace_once(path, "from datetime import UTC, datetime\n", "from datetime import UTC, date, datetime\n")
    _replace_once(
        path,
        "    source_name: str | None = None\n    public_entry_observed: bool | None = None\n",
        "    source_name: str | None = None\n    checked_date: date | None = None\n    public_entry_observed: bool | None = None\n",
    )
    _replace_once(
        path,
        "    public_url: str = Field(min_length=1)\n    public_entry_observed: bool | None = None\n",
        "    public_url: str = Field(min_length=1)\n    checked_date: date | None = None\n    public_entry_observed: bool | None = None\n",
    )
    _replace_once(
        path,
        "            source_name=self.source_name,\n            public_entry_observed=self.public_entry_observed,\n",
        "            source_name=self.source_name,\n            checked_date=self.checked_date,\n            public_entry_observed=self.public_entry_observed,\n",
    )
    _replace_once(
        path,
        "    next_action: str = Field(min_length=1)\n    observation_notes: str | None = None\n",
        "    next_action: str = Field(min_length=1)\n    observation_checked_date: date | None = None\n    observation_notes: str | None = None\n",
    )


def _patch_checklist_service() -> None:
    path = ROOT / "src/constructionsight/source_verification_checklist_service.py"
    _replace_once(
        path,
        "        next_action=_next_action(checklist_status),\n        observation_notes=observation.notes if observation else None,\n",
        "        next_action=_next_action(checklist_status),\n        observation_checked_date=observation.checked_date if observation else None,\n        observation_notes=observation.notes if observation else None,\n",
    )
    _replace_once(
        path,
        '                "Set booleans only after manual lawful public review.",\n',
        '                "Set checked_date and booleans only after manual lawful public review.",\n',
    )


def _patch_promotion_models() -> None:
    path = ROOT / "src/constructionsight/source_promotion_plan_models.py"
    _replace_once(path, "from datetime import UTC, datetime\n", "from datetime import UTC, date, datetime\n")
    _replace_once(
        path,
        "    proposed_registry_status: str | None = None\n    reasons: list[str] = Field(default_factory=list)\n",
        "    proposed_registry_status: str | None = None\n    verification_checked_date: date | None = None\n    reasons: list[str] = Field(default_factory=list)\n",
    )


def _patch_promotion_service() -> None:
    path = ROOT / "src/constructionsight/source_promotion_plan_service.py"
    _replace_once(
        path,
        "        proposed_registry_status=_proposed_registry_status(action),\n        reasons=_unique([*row.reasons, *_plan_reasons(row, action)]),\n",
        "        proposed_registry_status=_proposed_registry_status(action),\n        verification_checked_date=row.observation_checked_date,\n        reasons=_unique([*row.reasons, *_plan_reasons(row, action)]),\n",
    )
    _replace_once(
        path,
        "    if not row.evidence_refs:\n        limitations.append(\"no evidence references were supplied\")\n",
        "    if not row.evidence_refs:\n        limitations.append(\"no evidence references were supplied\")\n    if row.observation_checked_date is None:\n        limitations.append(\"verification checked date was not supplied\")\n",
    )


def _patch_update_plan_service() -> None:
    path = ROOT / "src/constructionsight/source_registry_update_plan_service.py"
    _replace_once(
        path,
        "from collections.abc import Iterable\nfrom typing import Any\n",
        "from collections.abc import Iterable\nfrom datetime import date\nfrom typing import Any\n",
    )
    _replace_once(
        path,
        "    proposed_status = plan_row.proposed_registry_status\n    original_payload = source.model_dump(mode=\"json\")\n    proposed_payload = _proposed_payload(original_payload, proposed_status)\n    update_required = (\n        proposed_status is not None\n        and proposed_status != source.verification_status.value\n    )\n",
        "    proposed_status = plan_row.proposed_registry_status\n    original_payload = source.model_dump(mode=\"json\")\n    proposed_payload = _proposed_payload(\n        original_payload,\n        proposed_status,\n        checked_date=plan_row.verification_checked_date,\n        evidence_refs=plan_row.evidence_refs,\n    )\n    update_required = proposed_payload is not None and proposed_payload != original_payload\n",
    )
    _replace_once(
        path,
        "def _proposed_payload(\n    original_payload: dict[str, Any],\n    proposed_status: str | None,\n) -> dict[str, Any] | None:\n    if proposed_status is None:\n        return None\n    proposed = dict(original_payload)\n    proposed[\"verification_status\"] = proposed_status\n    return proposed\n",
        "def _proposed_payload(\n    original_payload: dict[str, Any],\n    proposed_status: str | None,\n    *,\n    checked_date: date | None,\n    evidence_refs: list[str],\n) -> dict[str, Any] | None:\n    if proposed_status is None or checked_date is None:\n        return None\n    proposed = dict(original_payload)\n    proposed[\"verification_status\"] = proposed_status\n    proposed[\"last_checked_date\"] = checked_date.isoformat()\n    proposed[\"provenance_notes\"] = _verification_provenance(\n        proposed_status,\n        checked_date=checked_date,\n        evidence_refs=evidence_refs,\n    )\n    return proposed\n\n\ndef _verification_provenance(\n    proposed_status: str,\n    *,\n    checked_date: date,\n    evidence_refs: list[str],\n) -> str:\n    references = \"; \".join(sorted(evidence_refs)) or \"none\"\n    return (\n        f\"Evidence-backed source review completed {checked_date.isoformat()}. \"\n        f\"Verification status: {proposed_status}. Evidence refs: {references}.\"\n    )\n",
    )
    _replace_once(
        path,
        '        limitations.append("no registry status change is proposed")\n',
        '        limitations.append("no verification status or metadata change is proposed")\n',
    )
    _replace_once(
        path,
        '        return "review proposed verified status before any explicit apply workflow"\n',
        '        return "review proposed verified status and evidence metadata before apply"\n',
    )


def _patch_apply_models() -> None:
    path = ROOT / "src/constructionsight/source_registry_apply_models.py"
    _replace_once(path, "from datetime import UTC, datetime\n", "from datetime import UTC, date, datetime\n")
    _replace_once(
        path,
        "    previous_verification_status: str = Field(min_length=1)\n    resulting_verification_status: str = Field(min_length=1)\n    applied: bool\n",
        "    previous_verification_status: str = Field(min_length=1)\n    resulting_verification_status: str = Field(min_length=1)\n    previous_last_checked_date: date | None = None\n    resulting_last_checked_date: date | None = None\n    previous_provenance_notes: str | None = None\n    resulting_provenance_notes: str | None = None\n    applied: bool\n",
    )


def _patch_apply_service() -> None:
    path = ROOT / "src/constructionsight/source_registry_apply_service.py"
    _replace_once(
        path,
        "        if row.update_required:\n            updated_source = _validated_update(source, row)\n            updates[row.source_key] = updated_source\n            resulting_status = updated_source.verification_status.value\n        else:\n            resulting_status = source.verification_status.value\n",
        "        if row.update_required:\n            updated_source = _validated_update(source, row)\n            updates[row.source_key] = updated_source\n        else:\n            updated_source = source\n        resulting_status = updated_source.verification_status.value\n",
    )
    _replace_once(
        path,
        "                previous_verification_status=source.verification_status.value,\n                resulting_verification_status=resulting_status,\n                applied=row.update_required,\n",
        "                previous_verification_status=source.verification_status.value,\n                resulting_verification_status=resulting_status,\n                previous_last_checked_date=source.last_checked_date,\n                resulting_last_checked_date=updated_source.last_checked_date,\n                previous_provenance_notes=source.provenance_notes,\n                resulting_provenance_notes=updated_source.provenance_notes,\n                applied=row.update_required,\n",
    )
    _replace_once(
        path,
        "    if source.verification_status == VerificationStatus.VERIFIED:\n        raise SourceRegistryApplyError(\n            \"verified source status cannot be changed by the promotion apply workflow; \"\n            f\"separate revocation review is required: {row.source_key}\"\n        )\n",
        "    if (\n        source.verification_status == VerificationStatus.VERIFIED\n        and expected_status is not VerificationStatus.VERIFIED\n    ):\n        raise SourceRegistryApplyError(\n            \"verified source status cannot be downgraded by the promotion apply workflow; \"\n            f\"separate revocation review is required: {row.source_key}\"\n        )\n",
    )
    _replace_once(
        path,
        "    if changed_fields != {\"verification_status\"}:\n        changed = \", \".join(sorted(changed_fields)) or \"none\"\n        raise SourceRegistryApplyError(\n            \"source registry apply may change only verification_status; \"\n            f\"observed fields for {row.source_key}: {changed}\"\n        )\n",
        "    allowed_fields = {\"verification_status\", \"last_checked_date\", \"provenance_notes\"}\n    required_metadata_fields = {\"last_checked_date\", \"provenance_notes\"}\n    if not changed_fields or not changed_fields <= allowed_fields:\n        changed = \", \".join(sorted(changed_fields)) or \"none\"\n        raise SourceRegistryApplyError(\n            \"source registry apply may change only verification status and evidence metadata; \"\n            f\"observed fields for {row.source_key}: {changed}\"\n        )\n    if not required_metadata_fields <= changed_fields:\n        missing = \", \".join(sorted(required_metadata_fields - changed_fields))\n        raise SourceRegistryApplyError(\n            \"verification apply must update checked date and provenance; \"\n            f\"missing fields for {row.source_key}: {missing}\"\n        )\n",
    )
    _replace_once(
        path,
        "    if row.proposed_source_payload.get(\"verification_status\") != expected_status.value:\n        raise SourceRegistryApplyError(\n            f\"proposed source payload status is inconsistent for source: {row.source_key}\"\n        )\n\n    updated_source = PublicSource.model_validate(row.proposed_source_payload)\n",
        "    if row.proposed_source_payload.get(\"verification_status\") != expected_status.value:\n        raise SourceRegistryApplyError(\n            f\"proposed source payload status is inconsistent for source: {row.source_key}\"\n        )\n    if row.proposed_source_payload.get(\"last_checked_date\") is None:\n        raise SourceRegistryApplyError(\n            f\"proposed source payload lacks last_checked_date: {row.source_key}\"\n        )\n    provenance = row.proposed_source_payload.get(\"provenance_notes\")\n    if not isinstance(provenance, str) or not provenance.strip():\n        raise SourceRegistryApplyError(\n            f\"proposed source payload lacks verification provenance: {row.source_key}\"\n        )\n\n    updated_source = PublicSource.model_validate(row.proposed_source_payload)\n",
    )
    _replace_once(
        path,
        '            "registry status apply does not establish production-grade recurring source integration"\n',
        '            "registry verification apply does not establish production-grade recurring source integration"\n',
    )


def _patch_registry_tests() -> None:
    path = ROOT / "tests/test_source_registry_update_plan.py"
    _replace_once(path, "import json\n\nimport pytest\n", "import json\nfrom datetime import date\n\nimport pytest\n")
    _replace_once(
        path,
        '        "source_name": "Test Source",\n        "public_entry_observed": true,\n',
        '        "source_name": "Test Source",\n        "checked_date": "2026-07-12",\n        "public_entry_observed": true,\n',
    )
    _replace_once(
        path,
        '        source_name="Test Source",\n        public_entry_observed=True,\n',
        '        source_name="Test Source",\n        checked_date=date(2026, 7, 12),\n        public_entry_observed=True,\n',
    )
    _replace_once(
        path,
        '    assert row.proposed_source_payload["verification_status"] == "partial"\n    assert row.original_source_payload["verification_status"] == "unverified"\n',
        '    assert row.proposed_source_payload["verification_status"] == "partial"\n    assert row.proposed_source_payload["last_checked_date"] == "2026-07-12"\n    assert "Evidence-backed source review completed 2026-07-12" in (\n        row.proposed_source_payload["provenance_notes"]\n    )\n    assert row.original_source_payload["verification_status"] == "unverified"\n',
    )
    _replace_once(
        path,
        "    assert updated[0].verification_status == VerificationStatus.PARTIAL\n    assert report.applied_count == 1\n",
        "    assert updated[0].verification_status == VerificationStatus.PARTIAL\n    assert updated[0].last_checked_date == date(2026, 7, 12)\n    assert updated[0].provenance_notes is not None\n    assert report.rows[0].previous_last_checked_date is None\n    assert report.rows[0].resulting_last_checked_date == date(2026, 7, 12)\n    assert report.rows[0].previous_provenance_notes is None\n    assert report.rows[0].resulting_provenance_notes == updated[0].provenance_notes\n    assert report.applied_count == 1\n",
    )
    insertion = '''\n\ndef test_apply_reconciles_verified_source_metadata_without_status_change() -> None:\n    source = _source().model_copy(\n        update={\n            "verification_status": VerificationStatus.VERIFIED,\n            "last_checked_date": None,\n            "provenance_notes": "stale seed note",\n        }\n    )\n    plan = build_source_registry_update_plan(\n        [source],\n        default_adapter_family_specs(),\n        observations=[_complete_observation()],\n    )\n\n    row = plan.rows[0]\n    assert row.current_verification_status == "verified"\n    assert row.proposed_verification_status == "verified"\n    assert row.update_required is True\n\n    updated, report = apply_source_registry_update_plan(\n        [source],\n        plan,\n        approved_plan_digest=plan.plan_digest,\n    )\n\n    assert updated[0].verification_status is VerificationStatus.VERIFIED\n    assert updated[0].last_checked_date == date(2026, 7, 12)\n    assert updated[0].provenance_notes != "stale seed note"\n    assert report.rows[0].previous_verification_status == "verified"\n    assert report.rows[0].resulting_verification_status == "verified"\n    assert report.rows[0].applied is True\n'''
    text = path.read_text(encoding="utf-8")
    anchor = "\n\ndef test_apply_rejects_tampered_plan_content() -> None:\n"
    if text.count(anchor) != 1:
        raise RuntimeError("registry test insertion anchor mismatch")
    path.write_text(text.replace(anchor, insertion + anchor, 1), encoding="utf-8")


def _patch_verified_source_test() -> None:
    path = ROOT / "tests/test_ceqanet_verified_source_maturity.py"
    _replace_once(
        path,
        "    assert ceqanet.last_checked_date is None\n",
        "    assert ceqanet.last_checked_date == date(2026, 7, 12)\n    assert ceqanet.provenance_notes == EXPECTED_PROVENANCE\n",
    )
    _replace_once(
        path,
        "EVIDENCE_DIR = ROOT / \"evidence/source_verification\"\n",
        "EVIDENCE_DIR = ROOT / \"evidence/source_verification\"\nEXPECTED_PROVENANCE = (\n    \"Evidence-backed source review completed 2026-07-12. Verification status: verified. \"\n    \"Evidence refs: evidence/source_verification/ceqanet_public_access_2026-07-12.json; \"\n    \"evidence/source_verification/ceqanet_terms_review_2026-07-12.json.\"\n)\n",
    )
    _replace_once(
        path,
        '    audit_path = EVIDENCE_DIR / "ceqanet_verified_apply_audit_2026-07-12.json"\n',
        '    audit_path = EVIDENCE_DIR / "ceqanet_verified_apply_audit_2026-07-12.json"\n    metadata_plan_path = (\n        EVIDENCE_DIR / "ceqanet_verification_metadata_update_plan_2026-07-12.json"\n    )\n    metadata_audit_path = (\n        EVIDENCE_DIR / "ceqanet_verification_metadata_apply_audit_2026-07-12.json"\n    )\n',
    )
    _replace_once(
        path,
        "        plan_path,\n        audit_path,\n",
        "        plan_path,\n        audit_path,\n        metadata_plan_path,\n        metadata_audit_path,\n",
    )
    _replace_once(
        path,
        "    assert applied_rows[0][\"applied\"] is True\n\n    definition =",
        "    assert applied_rows[0][\"applied\"] is True\n\n    metadata_plan = _load_json(metadata_plan_path)\n    assert metadata_plan[\"update_count\"] == 1\n    metadata_rows = [\n        item\n        for item in metadata_plan[\"rows\"]\n        if item[\"source_name\"] == \"CEQAnet State Clearinghouse\"\n    ]\n    assert len(metadata_rows) == 1\n    assert metadata_rows[0][\"current_verification_status\"] == \"verified\"\n    assert metadata_rows[0][\"proposed_verification_status\"] == \"verified\"\n    assert metadata_rows[0][\"proposed_source_payload\"][\"last_checked_date\"] == (\n        \"2026-07-12\"\n    )\n    assert metadata_rows[0][\"proposed_source_payload\"][\"provenance_notes\"] == (\n        EXPECTED_PROVENANCE\n    )\n\n    metadata_audit = _load_json(metadata_audit_path)\n    assert metadata_audit[\"applied_count\"] == 1\n    metadata_audit_rows = [\n        item\n        for item in metadata_audit[\"rows\"]\n        if item[\"source_name\"] == \"CEQAnet State Clearinghouse\"\n    ]\n    assert len(metadata_audit_rows) == 1\n    assert metadata_audit_rows[0][\"previous_verification_status\"] == \"verified\"\n    assert metadata_audit_rows[0][\"resulting_verification_status\"] == \"verified\"\n    assert metadata_audit_rows[0][\"previous_last_checked_date\"] is None\n    assert metadata_audit_rows[0][\"resulting_last_checked_date\"] == \"2026-07-12\"\n    assert metadata_audit_rows[0][\"resulting_provenance_notes\"] == EXPECTED_PROVENANCE\n\n    definition =",
    )
    _replace_once(
        path,
        '        ROOT / "scripts/patch_ceqanet_collector_current.py",\n',
        '        ROOT / "scripts/patch_ceqanet_collector_current.py",\n        ROOT / ".github/workflows/source-verification-metadata-governance.yml",\n        ROOT / "scripts/apply_source_verification_metadata_governance.py",\n',
    )


def _patch_observation_artifact() -> None:
    payload = _load_json(OBSERVATIONS_PATH)
    if not isinstance(payload, list) or len(payload) != 1:
        raise RuntimeError("CEQAnet observation artifact must contain one row")
    payload[0]["checked_date"] = DATE
    _write_json(OBSERVATIONS_PATH, payload)


def _patch_documentation() -> None:
    readme = ROOT / "README.md"
    _replace_once(
        readme,
        "controlled registry-status apply\n",
        "controlled verification-state and evidence-metadata apply\n",
    )
    _replace_once(
        readme,
        "Controlled apply requires a reviewed plan digest, evidence references, explicit `--apply`, status-only mutation, stale-state validation, audit output, and atomic file replacement.",
        "Controlled apply requires a reviewed plan digest, evidence references, an explicit checked date, explicit `--apply`, verification-field-only mutation, stale-state validation, audit output, and atomic file replacement.",
    )
    _replace_once(
        readme,
        "and only `verification_status` changes.",
        "and only `verification_status`, `last_checked_date`, and deterministic verification provenance may change.",
    )

    architecture = ROOT / "docs/architecture/source_registry_update_plan.md"
    _replace_once(
        architecture,
        "A separate controlled apply command may write only an explicitly approved verification-status change.",
        "A separate controlled apply command may write only explicitly approved verification state and evidence metadata.",
    )
    _replace_once(
        architecture,
        "- proposed verification status, if any\n",
        "- proposed verification status, if any\n- verification checked date\n",
    )
    _replace_once(
        architecture,
        "7. Every applied status change has at least one evidence reference.\n8. The planned action and proposed status agree.\n9. The proposed payload changes only `verification_status`.\n10. The proposed payload preserves the canonical source identity.\n11. A currently verified source is not downgraded through the promotion workflow.\n12. The entire plan validates before any registry output is written.\n",
        "7. Every applied verification change has at least one evidence reference and an explicit checked date.\n8. The planned action and proposed status agree.\n9. The proposed payload changes only `verification_status`, `last_checked_date`, and deterministic verification provenance.\n10. Checked date and provenance are updated together, including metadata-only reconciliation for an already verified source.\n11. The proposed payload preserves the canonical source identity.\n12. A currently verified source is not downgraded through the promotion workflow.\n13. The entire plan validates before any registry output is written.\n",
    )
    _replace_once(
        architecture,
        "The audit report preserves the plan digest, original and updated registry digests, row-level reasons, limitations, evidence references, and applied statuses.",
        "The audit report preserves the plan digest, original and updated registry digests, row-level reasons, limitations, evidence references, applied statuses, checked dates, and provenance before and after apply.",
    )
    _replace_once(
        architecture,
        "This workflow does not make any current seed source verified, does not implement live adapters, and does not establish production coverage.",
        "A verified registry state remains narrower than production integration; it does not establish scheduling, persistence ingestion, or complete coverage.",
    )

    status = ROOT / "docs/architecture/current_implementation_status.md"
    _replace_once(
        status,
        "Controlled apply changes only an approved status and does not create production coverage.",
        "Controlled apply changes only approved verification fields—status, checked date, and deterministic provenance—and does not create production coverage.",
    )
    _replace_once(
        status,
        "| CS-VIAM-017 | P1 | CEQAnet evidence phase | PR #93 merged temporary write-enabled collection tooling instead of the claimed evidence packet and audit report. | The repair phase regenerated and committed current-structure evidence, reviewed official policies, removed all temporary tooling, applied `unverified → verified` through controlled apply, reconciled documentation, and added regression coverage. |",
        "| CS-VIAM-017 | P1 | CEQAnet evidence phase | PR #93 merged temporary write-enabled collection tooling instead of the claimed evidence packet and audit report. | The repair phase regenerated and committed current-structure evidence, reviewed official policies, removed all temporary tooling, applied `unverified → verified` through controlled apply, reconciled documentation, and added regression coverage. |\n| CS-VIAM-018 | P1 | Verification metadata | Status-only promotion could leave a verified source with a null checked date and stale seed provenance. | Verification observations now carry checked dates; plans derive deterministic evidence provenance; controlled apply restricts writes to status, checked date, and provenance; metadata-only verified reconciliation is audited and tested. |",
    )

    audit = ROOT / "docs/audits/full_repo_audit_inventory.md"
    _replace_once(
        audit,
        "Full-snapshot, digest, evidence, identity, status-only, path, audit, and explicit-authorization controls apply.",
        "Full-snapshot, digest, evidence, identity, verification-field-only, path, audit, and explicit-authorization controls apply.",
    )
    _replace_once(
        audit,
        "| CS-AUDIT-023 | P1 | CEQAnet evidence phase | PR #93 merged temporary write-enabled collection files while the claimed evidence JSON and audit report were absent from `main`. | The repair phase regenerated current-structure evidence, added an official-policy review, removed temporary tooling, used deterministic controlled apply for `unverified → verified`, reconciled all maturity claims, and added permanent regression coverage. |",
        "| CS-AUDIT-023 | P1 | CEQAnet evidence phase | PR #93 merged temporary write-enabled collection files while the claimed evidence JSON and audit report were absent from `main`. | The repair phase regenerated current-structure evidence, added an official-policy review, removed temporary tooling, used deterministic controlled apply for `unverified → verified`, reconciled all maturity claims, and added permanent regression coverage. |\n| CS-AUDIT-024 | P1 | Verification metadata | Status-only controlled apply could preserve null checked dates and stale provenance after verification. | Checked dates are explicit observation evidence, plans generate deterministic provenance, apply permits only the three verification fields, audit rows preserve before/after metadata, and an already verified source can receive metadata-only reconciliation without allowing downgrade. |",
    )


def validate_plan() -> None:
    plan = _load_json(PLAN_PATH)
    if plan.get("update_count") != 1:
        raise RuntimeError("verification metadata plan must propose exactly one update")
    rows = [row for row in plan.get("rows", []) if row.get("source_name") == SOURCE_NAME]
    if len(rows) != 1:
        raise RuntimeError("verification metadata plan must contain one CEQAnet row")
    row = rows[0]
    if row.get("current_verification_status") != "verified":
        raise RuntimeError("metadata reconciliation must start from verified status")
    if row.get("proposed_verification_status") != "verified":
        raise RuntimeError("metadata reconciliation must preserve verified status")
    if row.get("update_required") is not True:
        raise RuntimeError("metadata reconciliation must require an update")
    payload = row.get("proposed_source_payload") or {}
    if payload.get("last_checked_date") != DATE:
        raise RuntimeError("metadata plan checked date mismatch")
    if payload.get("provenance_notes") != EXPECTED_PROVENANCE:
        raise RuntimeError("metadata plan provenance mismatch")


def reconcile() -> None:
    registry_payload = _load_json(REGISTRY_PATH)
    sources = [PublicSource.model_validate(item) for item in registry_payload]
    matches = [source for source in sources if source.source_name == SOURCE_NAME]
    if len(matches) != 1:
        raise RuntimeError("registry must contain one CEQAnet source")
    source = matches[0]
    if source.verification_status.value != "verified":
        raise RuntimeError("metadata reconciliation changed verified status")
    if source.last_checked_date is None or source.last_checked_date.isoformat() != DATE:
        raise RuntimeError("registry checked date was not reconciled")
    if source.provenance_notes != EXPECTED_PROVENANCE:
        raise RuntimeError("registry provenance was not reconciled")

    audit = _load_json(AUDIT_PATH)
    if audit.get("applied_count") != 1 or audit.get("registry_changed") is not True:
        raise RuntimeError("metadata apply audit does not record one change")
    rows = [row for row in audit.get("rows", []) if row.get("source_name") == SOURCE_NAME]
    if len(rows) != 1:
        raise RuntimeError("metadata apply audit must contain one CEQAnet row")
    row = rows[0]
    if row.get("previous_verification_status") != "verified":
        raise RuntimeError("metadata audit previous status mismatch")
    if row.get("resulting_verification_status") != "verified":
        raise RuntimeError("metadata audit resulting status mismatch")
    if row.get("previous_last_checked_date") is not None:
        raise RuntimeError("metadata audit previous checked date mismatch")
    if row.get("resulting_last_checked_date") != DATE:
        raise RuntimeError("metadata audit resulting checked date mismatch")
    if row.get("resulting_provenance_notes") != EXPECTED_PROVENANCE:
        raise RuntimeError("metadata audit resulting provenance mismatch")

    observations_payload = _load_json(OBSERVATIONS_PATH)
    observations = [SourceVerificationObservation.model_validate(item) for item in observations_payload]
    checklist = build_source_verification_checklist_report(
        sources,
        default_adapter_family_specs(),
        observations=observations,
    )
    _write_json(CHECKLIST_PATH, checklist.to_dict())

    _replace_once(
        REPORT_PATH,
        "The controlled apply changed only `verification_status`. It did not modify `last_checked_date`, provenance, URLs, adapter maturity, or unrelated sources.",
        "The historical promotion apply changed `verification_status` from `unverified` to `verified`. A second digest-bound metadata reconciliation then set `last_checked_date` and replaced stale seed provenance with deterministic evidence references. No URL, adapter, jurisdiction, category, confidence, or unrelated source field changed.",
    )
    text = REPORT_PATH.read_text(encoding="utf-8")
    anchor = "- `evidence/source_verification/ceqanet_verified_apply_audit_2026-07-12.json`\n"
    addition = (
        anchor
        + "- `evidence/source_verification/ceqanet_verification_metadata_update_plan_2026-07-12.json`\n"
        + "- `evidence/source_verification/ceqanet_verification_metadata_apply_audit_2026-07-12.json`\n"
    )
    if text.count(anchor) != 1:
        raise RuntimeError("verified report artifact-list anchor mismatch")
    REPORT_PATH.write_text(text.replace(anchor, addition, 1), encoding="utf-8")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: apply_source_verification_metadata_governance.py patch|validate-plan|reconcile")
    command = sys.argv[1]
    if command == "patch":
        patch()
    elif command == "validate-plan":
        validate_plan()
    elif command == "reconcile":
        reconcile()
    else:
        raise SystemExit(f"unknown command: {command}")
