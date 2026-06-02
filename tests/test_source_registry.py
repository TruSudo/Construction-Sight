import json
from pathlib import Path

from pydantic import ValidationError

from constructionsight.models import PublicSource


def test_seed_registry_records_validate() -> None:
    registry_path = Path("data/source_registry.seed.json")
    records = json.loads(registry_path.read_text(encoding="utf-8"))

    sources = [PublicSource.model_validate(record) for record in records]

    assert len(sources) == 4
    assert {source.source_name for source in sources} == {
        "CEQAnet State Clearinghouse",
        "CSLB Public License Search",
        "San Bernardino County EZOP",
        "Riverside County PLUS Online",
    }


def test_duplicate_record_categories_are_rejected() -> None:
    record = {
        "jurisdiction": {
            "name": "Test City",
            "county": "San Bernardino",
            "state": "CA",
            "jurisdiction_type": "city",
        },
        "source_name": "Test Portal",
        "source_type": "city_portal",
        "platform_family": "unknown",
        "public_url": "https://example.gov/",
        "record_categories": ["permit", "permit"],
    }

    try:
        PublicSource.model_validate(record)
    except ValidationError as exc:
        assert "record_categories must be unique" in str(exc)
    else:
        raise AssertionError("duplicate record categories should fail validation")
