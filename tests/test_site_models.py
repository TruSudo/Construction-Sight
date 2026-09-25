import pytest
from pydantic import ValidationError

from constructionsight.provenance import Provenance
from constructionsight.site_models import Site


def test_site_model_accepts_minimum_required_fields() -> None:
    site = Site(site_key="site:test:123", county="Test County")

    assert site.site_key == "site:test:123"
    assert site.county == "Test County"
    assert site.state == "CA"


def test_site_model_preserves_provenance() -> None:
    provenance = Provenance(
        source_name="Synthetic Public Source",
        confidence_score=90,
        verified=True,
    )
    site = Site(
        site_key="site:test:apn-0000",
        county="Test County",
        apn="0000-000-00-0000",
        provenance=[provenance],
    )

    assert site.provenance[0].source_name == "Synthetic Public Source"
    assert site.provenance[0].band.value == "verified"


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("latitude", -90.0001),
        ("latitude", 90.0001),
        ("longitude", -180.0001),
        ("longitude", 180.0001),
        ("lot_size_acres", -0.0001),
    ),
)
def test_site_model_rejects_impossible_physical_values(field: str, value: float) -> None:
    with pytest.raises(ValidationError):
        Site(site_key="site:test:invalid", county="Test County", **{field: value})


def test_site_model_allows_unknown_and_partial_location_facts() -> None:
    unknown = Site(site_key="site:test:unknown", county="Test County")
    partial = Site(
        site_key="site:test:partial",
        county="Test County",
        latitude=34.0549,
    )

    assert unknown.latitude is None
    assert unknown.longitude is None
    assert partial.latitude == 34.0549
    assert partial.longitude is None
