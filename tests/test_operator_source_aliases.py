"""Validation tests for explicit local source-attribution alias artifacts."""

from __future__ import annotations

import json

import pytest

from constructionsight.operator_source_aliases import load_source_attribution_aliases


def _payload() -> dict[str, object]:
    return {
        "schema_version": "constructionsight.source_attribution_aliases.v1",
        "mapping_count": 1,
        "network_executed": False,
        "persistence_mutated": False,
        "mappings": [
            {
                "alias_source_name": "Retained official export label",
                "canonical_source_name": "Canonical public source",
                "reason": "Synthetic explicit identity assertion.",
                "evidence_refs": ["evidence/synthetic.json"],
            }
        ],
    }


def _write(tmp_path, payload: object):
    path = tmp_path / "source-aliases.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_source_alias_artifact_loads_exact_mapping_and_digest(tmp_path):
    aliases = load_source_attribution_aliases(_write(tmp_path, _payload()))

    assert aliases.mapping_count == 1
    assert len(aliases.artifact_sha256) == 64
    assert aliases.alias_to_canonical() == {
        "Retained official export label": "Canonical public source"
    }


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda value: value.update(mapping_count=2), "mapping count"),
        (lambda value: value.update(network_executed=True), "authority state"),
        (
            lambda value: value["mappings"][0].update(
                canonical_source_name="Retained official export label"
            ),
            "cannot equal",
        ),
    ],
)
def test_source_alias_artifact_rejects_inconsistent_authority_and_identity(
    tmp_path, mutation, message
):
    payload = _payload()
    mutation(payload)

    with pytest.raises(ValueError, match=message):
        load_source_attribution_aliases(_write(tmp_path, payload))


def test_source_alias_artifact_rejects_duplicate_alias_targets(tmp_path):
    payload = _payload()
    duplicate = dict(payload["mappings"][0])
    duplicate["canonical_source_name"] = "Another canonical source"
    payload["mappings"] = [payload["mappings"][0], duplicate]
    payload["mapping_count"] = 2

    with pytest.raises(ValueError, match="maps more than once"):
        load_source_attribution_aliases(_write(tmp_path, payload))


def test_source_alias_artifact_requires_canonical_order(tmp_path):
    payload = _payload()
    second = {
        "alias_source_name": "Earlier retained label",
        "canonical_source_name": "Canonical public source",
        "reason": "Synthetic explicit identity assertion.",
        "evidence_refs": ["evidence/synthetic.json"],
    }
    payload["mappings"] = [payload["mappings"][0], second]
    payload["mapping_count"] = 2

    with pytest.raises(ValueError, match="canonically ordered"):
        load_source_attribution_aliases(_write(tmp_path, payload))
