"""Serialization helpers for normalized domain models."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel


def model_to_json(model: BaseModel | None) -> str | None:
    """Serialize one Pydantic model to JSON, preserving date/datetime values."""

    if model is None:
        return None
    return model.model_dump_json(exclude_computed_fields=True)


def models_to_json(models: Sequence[BaseModel]) -> str:
    """Serialize a list of Pydantic models to JSON."""

    return json.dumps(
        [
            json.loads(model.model_dump_json(exclude_computed_fields=True))
            for model in models
        ],
        sort_keys=True,
    )


def strings_to_json(values: list[str]) -> str:
    """Serialize a list of strings to JSON."""

    return json.dumps(values, sort_keys=True)


def json_to_dict(value: str | None) -> dict[str, Any] | None:
    """Deserialize a JSON object string into a dictionary."""

    if value is None:
        return None
    loaded = json.loads(value)
    if not isinstance(loaded, dict):
        raise ValueError("expected JSON object")
    return loaded


def json_to_list(value: str | None) -> list[dict[str, Any]]:
    """Deserialize a JSON list string into a list of dictionaries."""

    if value is None:
        return []
    loaded = json.loads(value)
    if not isinstance(loaded, list):
        raise ValueError("expected JSON list")
    if not all(isinstance(item, dict) for item in loaded):
        raise ValueError("expected JSON list of objects")
    return loaded


def json_to_string_list(value: str | None) -> list[str]:
    """Deserialize a JSON list string into a list of strings."""

    if value is None:
        return []
    loaded = json.loads(value)
    if not isinstance(loaded, list):
        raise ValueError("expected JSON list")
    if not all(isinstance(item, str) for item in loaded):
        raise ValueError("expected JSON list of strings")
    return loaded
