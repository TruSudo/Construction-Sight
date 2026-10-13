"""Strict native-reference gate plus an explicitly provisional scaled diagnostic.

Usage: python compare_mockup.py REFERENCE.png ACTUAL.png OUTPUT_DIRECTORY
Requires Pillow. Data regions are masked only in the structural score. Raw diff
is always saved and scored; no font, border, sidebar or card-header masks exist.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageStat


def compare(reference: Path, actual: Path, output: Path) -> dict:
    tokens = json.loads(
        (
            Path(__file__).parents[2] / "src/constructionsight/command_center/design_tokens.json"
        ).read_text()
    )
    expected_size = tuple(tokens["requested_viewport"])
    original = Image.open(reference).convert("RGB")
    screenshot = Image.open(actual).convert("RGB")
    native = original.size == expected_size
    reference_matches = (
        hashlib.sha256(reference.read_bytes()).hexdigest() == tokens["reference_sha256"]
    )
    fonts_verified = not tokens["font_identity"].startswith("unverified")
    if screenshot.size != expected_size:
        raise ValueError("Actual screenshot must be exactly 1672×941 at device scale 1")
    expected = original if native else original.resize(expected_size, Image.Resampling.LANCZOS)
    diff = ImageChops.difference(expected, screenshot)
    sx, sy = expected_size[0] / 1536, expected_size[1] / 864
    mask = Image.new("L", expected_size, 255)
    draw = ImageDraw.Draw(mask)
    # Genuine source values: KPI digits, map geography/markers, dossier photo/text,
    # and table body. Static labels, card outlines, navigation and typography remain.
    dynamic = [
        (377, 195, 520, 237),
        (600, 199, 735, 237),
        (841, 199, 976, 237),
        (1085, 199, 1240, 237),
        (1325, 199, 1493, 237),
        (312, 301, 1062, 620),
        (1093, 300, 1519, 414),
        (1093, 422, 1518, 477),
        (1215, 482, 1518, 630),
        (329, 700, 1044, 837),
        (330, 12, 910, 37),
        (1380, 13, 1483, 40),
    ]
    for x0, y0, x1, y1 in dynamic:
        draw.rectangle((round(x0 * sx), round(y0 * sy), round(x1 * sx), round(y1 * sy)), fill=0)
    structural = ImageChops.multiply(diff, Image.merge("RGB", (mask, mask, mask)))
    tolerance = tokens["visual_test"]["channel_tolerance"]
    selected = [
        (c, m)
        for c, m in zip(diff.get_flattened_data(), mask.get_flattened_data(), strict=True)
        if m
    ]
    score = sum(max(c) > tolerance for c, _ in selected) / len(selected)
    mae = sum(sum(c) for c, _ in selected) / (len(selected) * 3)
    raw_mae = sum(ImageStat.Stat(diff).mean) / 3
    passed = (
        native
        and reference_matches
        and fonts_verified
        and score <= tokens["visual_test"]["max_changed_static_pixels_fraction"]
        and mae <= tokens["visual_test"]["max_channel_mae"]
    )
    output.mkdir(parents=True, exist_ok=True)
    diff.save(output / "raw-diff.png")
    structural.save(output / "structural-diff.png")
    canvas = Image.new("RGB", (1672 * 2, 941 * 2 + 90), "#111313")
    canvas.paste(expected, (0, 45))
    canvas.paste(screenshot, (1672, 45))
    labels = ImageDraw.Draw(canvas)
    labels.text(
        (15, 15),
        "REFERENCE" + (" — SCALED DIAGNOSTIC; NATIVE ASSET MISSING" if not native else ""),
        fill="white",
    )
    labels.text((1687, 15), "CURRENT APP — CAPTURED VIEW", fill="white")
    canvas.paste(diff, (0, 1031))
    canvas.paste(structural, (1672, 1031))
    labels.text((15, 1001), "RAW DIFF (INCLUDES INTENTIONAL REAL-DATA DIFFERENCES)", fill="white")
    labels.text(
        (1687, 1001),
        f"STATIC DIFF: {score:.2%} changed / 0.50% limit — {'PASS' if passed else 'FAIL'}",
        fill="white",
    )
    canvas.save(output / "CommandCenter-comparison.png")
    result = {
        "reference_size": list(original.size),
        "actual_size": list(screenshot.size),
        "native_reference": native,
        "reference_matches_recorded_asset": reference_matches,
        "font_assets_verified": fonts_verified,
        "static_changed_fraction": score,
        "static_channel_mae": mae,
        "raw_channel_mae": raw_mae,
        "threshold": tokens["visual_test"],
        "passed": passed,
        "blocking_reason": None
        if passed
        else (
            "Native 1672×941 reference missing; scaled scores are diagnostic only"
            if not native
            else "Visual difference exceeds threshold"
        ),
    }
    (output / "metrics.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("reference", type=Path)
    p.add_argument("actual", type=Path)
    p.add_argument("output", type=Path)
    a = p.parse_args()
    r = compare(a.reference, a.actual, a.output)
    print(json.dumps(r))
    raise SystemExit(0 if r["passed"] else 1)
