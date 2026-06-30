from typer.testing import CliRunner

from constructionsight.adapters.specs import (
    AdapterFamilySpec,
    AdapterImplementationStatus,
    default_adapter_family_specs,
)
from constructionsight.models import (
    Jurisdiction,
    PlatformFamily,
    PublicSource,
    SourceType,
    VerificationStatus,
)
from constructionsight.source_status_cli import app
from constructionsight.source_status_report import build_source_status_report


def _source(
    *,
    name: str = "Test Source",
    platform: PlatformFamily = PlatformFamily.ACCELA_ACA,
    status: VerificationStatus = VerificationStatus.UNVERIFIED,
) -> PublicSource:
    return PublicSource(
        jurisdiction=Jurisdiction(
            name="Test City",
            county="San Bernardino",
            jurisdiction_type="city",
        ),
        source_name=name,
        source_type=SourceType.CITY_PORTAL,
        platform_family=platform,
        public_url="https://example.invalid/source",
        verification_status=status,
    )


def test_source_status_report_marks_unverified_as_seed_only() -> None:
    report = build_source_status_report(
        [_source(status=VerificationStatus.UNVERIFIED)],
        default_adapter_family_specs(),
    )

    row = report.rows[0]

    assert row.status_level == "seed_only"
    assert row.can_use_as_verified_source is False
    assert report.verified_source_count == 0


def test_source_status_report_marks_verified_live_adapter_usable() -> None:
    specs = default_adapter_family_specs()
    specs[PlatformFamily.ACCELA_ACA] = AdapterFamilySpec(
        platform_family=PlatformFamily.ACCELA_ACA,
        status=AdapterImplementationStatus.LIVE_READ_ONLY,
    )

    report = build_source_status_report(
        [_source(status=VerificationStatus.VERIFIED)],
        specs,
    )

    row = report.rows[0]

    assert row.status_level == "verified_live_read_only"
    assert row.can_use_as_verified_source is True
    assert report.verified_source_count == 1


def test_source_status_report_serializes_rows() -> None:
    report = build_source_status_report(
        [_source(status=VerificationStatus.UNVERIFIED)],
        default_adapter_family_specs(),
    )
    payload = report.to_dict()

    assert payload["source_count"] == 1
    assert payload["rows"][0]["status_level"] == "seed_only"


def test_source_status_cli_requires_report_subcommand(tmp_path) -> None:
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
    runner = CliRunner()

    result = runner.invoke(app, ["report", str(registry_path), "--json-output"])

    assert result.exit_code == 0
    assert '"status_level": "seed_only"' in result.output
