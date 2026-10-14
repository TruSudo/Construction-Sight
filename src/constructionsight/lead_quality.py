"""Explain source-name classification and unknown coverage without verifying project use."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

CONFIG_PATH = Path(__file__).parent / "command_center/project_type_keywords.json"


def load_keywords() -> dict[str, Any]:
    value: dict[str, Any] = json.loads(CONFIG_PATH.read_text())
    return value


def classify_names(row: dict[str, Any]) -> dict[str, Any]:
    config = load_keywords()
    for field, confidence in (("SITE_NAME", 0.7), ("DEVELOPER_NAME", 0.4)):
        text = str(row.get(field) or "").casefold()
        text = re.sub(r"\s+", " ", text)
        for rule in config["rules"]:
            if field == "DEVELOPER_NAME" and rule["excluded"]:
                continue
            for keyword in rule["keywords"]:
                if re.search(r"(?<!\w)" + re.escape(keyword) + r"(?!\w)", text):
                    return {
                        "project_type": rule["project_type"],
                        "subtype": rule["subtype"],
                        "source": config["label"],
                        "confidence": confidence,
                        "evidence_field": field,
                        "matched_keyword": keyword,
                        "evidence_value": row.get(field),
                        "verified": False,
                        "excluded": rule["excluded"],
                    }
    return {
        "project_type": "unknown",
        "subtype": None,
        "source": config["label"],
        "confidence": 0.0,
        "matched_keyword": None,
        "verified": False,
        "excluded": False,
    }


def quality_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    unknown = [r for r in rows if r.get("project_type") == "unknown"]
    excluded = [r for r in rows if r.get("project_type") == "infrastructure"]
    eligible = len(rows) - len(excluded)
    tokens = Counter(
        t
        for r in unknown
        for t in re.findall(r"\b\w{2,}\b", str(r.get("SITE_NAME") or "").casefold())
    )
    developers = Counter(str(r.get("DEVELOPER_NAME") or "—").strip() or "—" for r in unknown)
    return {
        "total": len(rows),
        "unknown": len(unknown),
        "unknown_percent": len(unknown) / len(rows) * 100 if rows else None,
        "excluded": len(excluded),
        "non_excluded": eligible,
        "unknown_percent_non_excluded": len(unknown) / eligible * 100 if eligible else None,
        "unknown_tokens": tokens.most_common(150),
        "unknown_developers": developers.most_common(50),
        "keywords": load_keywords(),
        "method": "Sourced name inference and unverified parcel-use claims; never verification",
    }
