"""Explicit audited provenance-source aliases for local operator attribution."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field, field_validator

from constructionsight.storage.runtime_artifacts import read_runtime_artifact

SOURCE_ALIAS_SCHEMA = "constructionsight.source_attribution_aliases.v1"
SOURCE_ALIAS_MAX_BYTES = 512 * 1024
SOURCE_ALIAS_MAX_MAPPINGS = 1_000
SOURCE_ALIAS_MAX_EVIDENCE_REFS = 20


class SourceAttributionAlias(BaseModel):
    """One exact provenance source-name assertion to a canonical registry source."""

    model_config = ConfigDict(extra="forbid")

    alias_source_name: str = Field(min_length=1, max_length=255)
    canonical_source_name: str = Field(min_length=1, max_length=255)
    reason: str = Field(min_length=1, max_length=1_000)
    evidence_refs: list[str] = Field(min_length=1, max_length=SOURCE_ALIAS_MAX_EVIDENCE_REFS)

    @field_validator(
        "alias_source_name",
        "canonical_source_name",
        "reason",
    )
    @classmethod
    def reject_control_characters(cls, value: str) -> str:
        if value != value.strip() or any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError("source attribution alias text must be trimmed printable text")
        return value

    @field_validator("evidence_refs")
    @classmethod
    def validate_evidence_refs(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("source attribution alias evidence references must be unique")
        for value in values:
            if (
                not value
                or value != value.strip()
                or len(value) > 1_000
                or any(ord(char) < 32 or ord(char) == 127 for char in value)
            ):
                raise ValueError(
                    "source attribution alias evidence references must be bounded printable text"
                )
        return values


class SourceAttributionAliasArtifact(BaseModel):
    """Bounded retained alias artifact with no collection or persistence authority."""

    model_config = ConfigDict(extra="forbid")

    schema_version: str
    mapping_count: int = Field(ge=0, le=SOURCE_ALIAS_MAX_MAPPINGS)
    network_executed: bool
    persistence_mutated: bool
    mappings: list[SourceAttributionAlias] = Field(max_length=SOURCE_ALIAS_MAX_MAPPINGS)


@dataclass(frozen=True)
class LoadedSourceAttributionAliases:
    """Validated immutable operator alias configuration."""

    artifact_sha256: str
    mappings: tuple[SourceAttributionAlias, ...]

    @property
    def mapping_count(self) -> int:
        return len(self.mappings)

    def alias_to_canonical(self) -> dict[str, str]:
        return {
            mapping.alias_source_name: mapping.canonical_source_name
            for mapping in self.mappings
        }


def load_source_attribution_aliases(path) -> LoadedSourceAttributionAliases:
    """Load one bounded exact-name alias artifact without network or database access."""

    raw = read_runtime_artifact(path, max_bytes=SOURCE_ALIAS_MAX_BYTES)
    try:
        payload: object = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("source attribution aliases are not valid bounded UTF-8 JSON") from exc
    artifact = SourceAttributionAliasArtifact.model_validate(payload)
    if artifact.schema_version != SOURCE_ALIAS_SCHEMA:
        raise ValueError("source attribution aliases use an unsupported schema")
    if artifact.mapping_count != len(artifact.mappings):
        raise ValueError("source attribution alias mapping count disagrees with retained mappings")
    if artifact.network_executed is not False or artifact.persistence_mutated is not False:
        raise ValueError("source attribution alias artifact carries unsupported authority state")

    ordered = sorted(
        artifact.mappings,
        key=lambda item: (item.alias_source_name, item.canonical_source_name),
    )
    if artifact.mappings != ordered:
        raise ValueError("source attribution aliases are not canonically ordered")
    aliases: set[str] = set()
    pairs: set[tuple[str, str]] = set()
    for mapping in artifact.mappings:
        if mapping.alias_source_name == mapping.canonical_source_name:
            raise ValueError("source attribution alias cannot equal its canonical source name")
        if mapping.alias_source_name in aliases:
            raise ValueError("source attribution alias name maps more than once")
        pair = (mapping.alias_source_name, mapping.canonical_source_name)
        if pair in pairs:
            raise ValueError("source attribution alias mapping is duplicated")
        aliases.add(mapping.alias_source_name)
        pairs.add(pair)

    return LoadedSourceAttributionAliases(
        artifact_sha256=hashlib.sha256(raw).hexdigest(),
        mappings=tuple(artifact.mappings),
    )
