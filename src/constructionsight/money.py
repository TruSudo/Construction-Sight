"""Canonical fixed-decimal money and rate primitives."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Final, TypeAlias

DecimalInput: TypeAlias = Decimal | int | float | str
MONEY_QUANTUM: Final = Decimal("0.01")
RATE_QUANTUM: Final = Decimal("0.000001")
MONEY_ROUNDING: Final = ROUND_HALF_UP


def decimal_value(value: DecimalInput, *, field_name: str) -> Decimal:
    """Parse one finite nonnegative decimal without binary arithmetic."""

    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a decimal number")
    try:
        parsed = value if isinstance(value, Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field_name} must be a decimal number") from exc
    if not parsed.is_finite():
        raise ValueError(f"{field_name} must be finite")
    if parsed < 0:
        raise ValueError(f"{field_name} must not be negative")
    return parsed


def _decimal_places(value: Decimal) -> int:
    exponent = value.as_tuple().exponent
    if not isinstance(exponent, int):
        raise ValueError("decimal value must be finite")
    return max(0, -exponent)


def money_decimal(value: DecimalInput, *, field_name: str = "money") -> Decimal:
    """Return a cent-scale decimal, rejecting precision beyond cents."""

    parsed = decimal_value(value, field_name=field_name)
    if _decimal_places(parsed) > 2:
        raise ValueError(f"{field_name} must use at most 2 decimal places")
    return parsed.quantize(MONEY_QUANTUM)


def rate_decimal(value: DecimalInput, *, field_name: str = "share_rate") -> Decimal:
    """Return a six-place rate between zero and one."""

    parsed = decimal_value(value, field_name=field_name)
    if parsed > 1:
        raise ValueError(f"{field_name} must be between 0 and 1")
    if _decimal_places(parsed) > 6:
        raise ValueError(f"{field_name} must use at most 6 decimal places")
    return parsed.quantize(RATE_QUANTUM)


def calculate_share(gross_value: DecimalInput, share_rate: DecimalInput) -> Decimal:
    """Calculate a monetary share with explicit round-half-up cent rounding."""

    gross = money_decimal(gross_value, field_name="gross_value")
    rate = rate_decimal(share_rate, field_name="share_rate")
    return (gross * rate).quantize(MONEY_QUANTUM, rounding=MONEY_ROUNDING)


def money_text(value: DecimalInput) -> str:
    """Return canonical cent-scale storage text."""

    return format(money_decimal(value, field_name="money"), ".2f")


def rate_text(value: DecimalInput) -> str:
    """Return canonical six-place rate storage text."""

    return format(rate_decimal(value), ".6f")


def rate_identity_text(value: DecimalInput) -> str:
    """Preserve the historical four-place minimum while extending to six places."""

    text = rate_text(value)
    whole, fractional = text.split(".", 1)
    while len(fractional) > 4 and fractional.endswith("0"):
        fractional = fractional[:-1]
    return f"{whole}.{fractional}"


def storage_money_text(value: DecimalInput) -> str:
    """Return exact canonical text, retaining readable legacy >cent values."""

    parsed = decimal_value(value, field_name="gross_value")
    if _decimal_places(parsed) <= 2:
        return format(parsed.quantize(MONEY_QUANTUM), ".2f")
    text = format(parsed.normalize(), "f")
    return "0" if text in {"-0", "-0.0"} else text
