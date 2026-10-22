"""Pin the known historical/current rounding divergence without rewriting contracts.

Historical blob 80aaacb249a77881e713e82b3db93923734a9703
(src/constructionsight/money.py on remediation/cs-sr-053-fixed-decimal-v2)
used Decimal ROUND_HALF_UP. The retained current result ledger service uses
round-half-even. This test documents the difference, not an approved financial
policy, owner contract, historic ledger migration, or a claim of equivalence.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

import pytest

from constructionsight.result_ledger_service import calculate_share_minor_units


@pytest.mark.parametrize(
    ("gross_cents", "rate_ppm", "old_half_up_cents", "current_half_even_cents"),
    [
        (5, 100_000, 1, 0),
        (15, 100_000, 2, 2),
        (25, 100_000, 3, 2),
        (35, 100_000, 4, 4),
    ],
)
def test_p8_01_historical_share_rounding_difference_is_explicit(
    gross_cents: int,
    rate_ppm: int,
    old_half_up_cents: int,
    current_half_even_cents: int,
) -> None:
    """Half-cent ties are a financial-contract decision, not UI display drift."""
    gross = Decimal(gross_cents) / 100
    rate = Decimal(rate_ppm) / 1_000_000
    historically_rounded = (gross * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    assert int(historically_rounded * 100) == old_half_up_cents
    assert calculate_share_minor_units(gross_cents, rate_ppm) == current_half_even_cents
