from __future__ import annotations

import pytest
from pydantic import ValidationError

from constructionsight.adapters.ceqanet_listing import CeqanetListingQuery
from constructionsight.ceqanet_recurring_run_models import CeqanetRecurringQueryTemplate


def test_listing_query_rejects_untransmitted_text_terms() -> None:
    with pytest.raises(
        ValueError,
        match="text_terms are unsupported by the verified search contract",
    ):
        CeqanetListingQuery(text_terms=("warehouse",))


def test_recurring_run_template_rejects_untransmitted_text_terms() -> None:
    with pytest.raises(
        ValidationError,
        match="text_terms are unsupported by the verified search contract",
    ):
        CeqanetRecurringQueryTemplate(text_terms=["warehouse"])
