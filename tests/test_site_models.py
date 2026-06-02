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
