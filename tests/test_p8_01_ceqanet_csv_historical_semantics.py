"""P8-01 comparisons against the archived CEQAnet CSV parser contract.

Old: agent/ceqanet-csv-export-contract-v2 (tests/test_ceqanet_csv_export.py).
New: guarded canonical inspector, which deliberately rejects unsupported or
unverified evidence and never grants live access or persistence by inspecting it.
Tests are offline and do not import or restore the old network executor.
"""

from __future__ import annotations

import hashlib

import pytest

from constructionsight.ceqanet_csv_service import (
    build_ceqanet_csv_export_request,
    inspect_ceqanet_csv_bytes,
)


def test_historical_quotes_and_bom_are_supported_with_exact_bytes_digest() -> None:
    raw = (
        b"\xef\xbb\xbfSCH Number,Title,Lead/Public Agency\r\n"
        b'2026030377,"Warehouse, Phase 2",City of Fontana\r\n'
    )
    request = build_ceqanet_csv_export_request(sch_number="2026030377")

    report = inspect_ceqanet_csv_bytes(request, raw, content_type="text/csv")

    assert report.encoding == "utf-8-sig"
    assert report.row_count == 1
    assert report.rows[0]["title"] == "Warehouse, Phase 2"
    assert report.rows[0]["sch_number"] == "2026030377"
    assert report.body_sha256 == hashlib.sha256(raw).hexdigest()
    assert report.byte_length == len(raw)
    assert report.network_executed is False
    assert report.persistence_authorized is False
    report.assert_integrity()


@pytest.mark.parametrize(
    ("body", "error"),
    [
        (b"SCH Number,Title\n", "header and at least one data row"),
        (
            b"SCH Number,Title,Title\n2026030377,A,B\n",
            "duplicate normalized headers",
        ),
        (
            b"SCH Number,Title\n2026030377,Example,unexpected\n",
            "has 3 values; expected 2",
        ),
    ],
)
def test_historical_loose_parser_shapes_are_safely_rejected(
    body: bytes, error: str,
) -> None:
    """Header-only was historically permitted; canonical evidence requires a row."""
    request = build_ceqanet_csv_export_request(sch_number="2026030377")
    with pytest.raises(ValueError, match=error):
        inspect_ceqanet_csv_bytes(request, body)


def test_historical_untrimmed_text_is_normalized_in_view_but_digest_is_raw() -> None:
    """Canonical viewing strips field padding; never claim source-byte identity."""
    raw = b'SCH Number,Title\r\n2026030377,"  Warehouse  "\r\n'
    request = build_ceqanet_csv_export_request(sch_number="2026030377")

    report = inspect_ceqanet_csv_bytes(request, raw, content_type="text/csv")

    assert report.rows[0]["title"] == "Warehouse"
    assert report.body_sha256 == hashlib.sha256(raw).hexdigest()
    assert report.byte_length == len(raw)
    assert report.network_executed is False
    assert report.persistence_authorized is False
