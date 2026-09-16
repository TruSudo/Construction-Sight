"""Bind canonical CI execution semantics to reviewed bytes and bootstrap invariants.

Workflow edits require explicit review and an updated literal digest. The digest
is a drift control, not analytical assurance or authenticated owner acceptance.
The quality bootstrap additionally forbids candidate project installation before
certification so repository-controlled build backends cannot pre-poison later gates.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Final

from constructionsight.repository_certification import CertificationFinding
from constructionsight.repository_path_certification import resolve_repository_file

_CANONICAL_WORKFLOW: Final = ".github/workflows/ci.yml"
_REVIEWED_WORKFLOW_SHA256: Final = (
    "de783e3c280f00c07fa39e9fb55c4e2138524f1dd0563266caf52b39de7f96b6"
)
_EXPECTED_QUALITY_SOURCE_PATH: Final = (
    "    env:\n"
    "      PYTHONPATH: ${{ github.workspace }}/src\n"
    "\n"
    "    strategy:\n"
)
_EXPECTED_DEPENDENCY_INSTALL_BLOCK: Final = (
    "      - name: Install exact supported dependency environment\n"
    "        id: install\n"
    "        continue-on-error: true\n"
    "        shell: /bin/bash --noprofile --norc -p -e -o pipefail {0}\n"
    "        run: |\n"
    "          set -o pipefail\n"
    "          mkdir -p \"${REPORT_DIR}\"\n"
    "          python -m pip install \\\n"
    "            --disable-pip-version-check \\\n"
    "            --require-hashes \\\n"
    "            --only-binary=:all: \\\n"
    "            --no-deps \\\n"
    "            -r \"${{ matrix.lock-file }}\" \\\n"
    "            2>&1 | tee \"${REPORT_DIR}/install-${{ matrix.lock-tag }}.txt\"\n"
)
_EXPECTED_ADAPTER_AUDIT_BLOCK: Final = (
    "      - name: Adapter contract audit\n"
    "        id: adapter-audit\n"
    "        continue-on-error: true\n"
    "        shell: /bin/bash --noprofile --norc -p -e -o pipefail {0}\n"
    "        run: |\n"
    "          set -o pipefail\n"
    "          mkdir -p \"${REPORT_DIR}\"\n"
    "          python -c 'from constructionsight.cli import app; app()' audit-adapters \\\n"
    "            2>&1 | tee \"${REPORT_DIR}/adapter-audit-${{ matrix.lock-tag }}.txt\"\n"
)
_EXPECTED_SOURCE_AUDIT_BLOCK: Final = (
    "      - name: Source adapter coverage audit\n"
    "        id: source-audit\n"
    "        continue-on-error: true\n"
    "        shell: /bin/bash --noprofile --norc -p -e -o pipefail {0}\n"
    "        run: |\n"
    "          set -o pipefail\n"
    "          mkdir -p \"${REPORT_DIR}\"\n"
    "          python -c 'from constructionsight.cli import app; app()' \\\n"
    "            audit-source-coverage data/source_registry.seed.json \\\n"
    "            2>&1 | tee \"${REPORT_DIR}/source-audit-${{ matrix.lock-tag }}.txt\"\n"
)


def _bootstrap_findings(workflow_text: str) -> tuple[CertificationFinding, ...]:
    findings: list[CertificationFinding] = []
    if workflow_text.count(_EXPECTED_QUALITY_SOURCE_PATH) != 1:
        findings.append(
            CertificationFinding(
                code="CERT-CI-009",
                path=_CANONICAL_WORKFLOW,
                line=None,
                message=(
                    "quality job must execute the reviewed src tree through the canonical "
                    "PYTHONPATH binding"
                ),
            )
        )
    if workflow_text.count(_EXPECTED_DEPENDENCY_INSTALL_BLOCK) != 1:
        findings.append(
            CertificationFinding(
                code="CERT-CI-010",
                path=_CANONICAL_WORKFLOW,
                line=None,
                message=(
                    "quality bootstrap must install only the canonical hash-locked third-party "
                    "dependency environment"
                ),
            )
        )
    if workflow_text.count("python -m pip install") != 1:
        findings.append(
            CertificationFinding(
                code="CERT-CI-011",
                path=_CANONICAL_WORKFLOW,
                line=None,
                message=(
                    "canonical CI must contain exactly one pip installation command; candidate "
                    "project installation before certification is prohibited"
                ),
            )
        )
    if workflow_text.count(_EXPECTED_ADAPTER_AUDIT_BLOCK) != 1:
        findings.append(
            CertificationFinding(
                code="CERT-CI-012",
                path=_CANONICAL_WORKFLOW,
                line=None,
                message="adapter audit must execute the reviewed source tree directly",
            )
        )
    if workflow_text.count(_EXPECTED_SOURCE_AUDIT_BLOCK) != 1:
        findings.append(
            CertificationFinding(
                code="CERT-CI-013",
                path=_CANONICAL_WORKFLOW,
                line=None,
                message="source coverage audit must execute the reviewed source tree directly",
            )
        )
    return tuple(findings)


def audit_ci_execution(root: Path) -> tuple[CertificationFinding, ...]:
    """Reject workflow drift and candidate project-build execution before certification."""

    digest_finding: CertificationFinding | None = None
    try:
        _relative, workflow = resolve_repository_file(root, _CANONICAL_WORKFLOW)
        workflow_bytes = workflow.read_bytes()
        workflow_text = workflow_bytes.decode("utf-8")
        actual_digest = hashlib.sha256(workflow_bytes).hexdigest()
        if actual_digest != _REVIEWED_WORKFLOW_SHA256:
            digest_finding = CertificationFinding(
                code="CERT-CI-008",
                path=_CANONICAL_WORKFLOW,
                line=None,
                message=(
                    "canonical CI differs from its complete reviewed execution contract: "
                    f"expected_sha256={_REVIEWED_WORKFLOW_SHA256} "
                    f"actual_sha256={actual_digest}"
                ),
            )
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        return (
            CertificationFinding(
                code="CERT-CI-008",
                path=_CANONICAL_WORKFLOW,
                line=None,
                message=str(exc),
            ),
        )

    findings = list(_bootstrap_findings(workflow_text))
    if digest_finding is not None:
        findings.append(digest_finding)
    return tuple(findings)
