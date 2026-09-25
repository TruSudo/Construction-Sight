from __future__ import annotations

from typer.testing import CliRunner

import constructionsight.audit_package_cli as cli
from constructionsight.source_verification_evidence_service import (
    build_source_verification_evidence_package,
)

runner = CliRunner()


def _registry(tmp_path):
    registry_path = tmp_path / "sources.json"
    registry_path.write_text(
        """
        [
          {
            "jurisdiction": {
              "name": "Test City",
              "county": "San Bernardino",
              "state": "CA",
              "jurisdiction_type": "city"
            },
            "source_name": "Test Source",
            "source_type": "city_portal",
            "platform_family": "accela_aca",
            "public_url": "https://example.invalid/source",
            "verification_status": "unverified"
          }
        ]
        """,
        encoding="utf-8",
    )
    return registry_path


def test_audit_package_cli_outputs_offline_json(tmp_path) -> None:
    registry_path = _registry(tmp_path)

    result = runner.invoke(cli.app, ["build", str(registry_path), "--json-output"])

    assert result.exit_code == 0
    assert '"source_count": 1' in result.output
    assert '"keep_seed_only": 1' in result.output


def test_audit_package_cli_delegates_live_check_to_authorized_service(
    tmp_path,
    monkeypatch,
) -> None:
    registry_path = _registry(tmp_path)
    calls: list[dict[str, object]] = []

    def fake_authorized(sources, adapter_specs, **kwargs):
        calls.append(kwargs)
        return build_source_verification_evidence_package(
            sources,
            adapter_specs,
            check_http=False,
        )

    monkeypatch.setattr(
        cli,
        "build_authorized_source_verification_evidence_package",
        fake_authorized,
    )
    result = runner.invoke(
        cli.app,
        [
            "build",
            str(registry_path),
            "--check-http",
            "--operator-id",
            "operator:test",
            "--authorization-reason",
            "Review the exact test registry.",
            "--json-output",
        ],
    )

    assert result.exit_code == 0
    assert calls == [
        {
            "caller_confirmation": True,
            "authorization_reason": "Review the exact test registry.",
            "operator_id": "operator:test",
        }
    ]
