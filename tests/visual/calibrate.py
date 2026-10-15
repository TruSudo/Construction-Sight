"""Calibrate and challenge native visual thresholds against the retained reference."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from perceptual import BLUR_RADIUS, TILE_SIZE, TILE_STRIDE, region_scores
from PIL import Image, ImageChops, ImageDraw

TOKENS = Path(__file__).parents[2] / "src/constructionsight/command_center/design_tokens.json"
REFERENCE = Path(__file__).with_name("reference_native_1672x941.png")
CALIBRATION = Path(__file__).with_name("calibration.json")


def challenges(reference: Image.Image, tokens: dict[str, Any]) -> dict[str, Image.Image]:
    resampled = reference.resize(
        (round(reference.width * 0.75), round(reference.height * 0.75)), Image.Resampling.LANCZOS
    ).resize(reference.size, Image.Resampling.LANCZOS)
    shifted = Image.new("RGB", reference.size, "#181818")
    shifted.paste(reference, (3, 0))
    wrong_color = reference.copy()
    # A single design color family is replaced, including its raster edge shades.
    pixels = wrong_color.load()
    for y in range(reference.height):
        for x in range(reference.width):
            r, g, b = pixels[x, y]
            if r > 100 and r > 1.2 * g and g > 1.5 * b:
                pixels[x, y] = (b, g, r)
    missing = reference.copy()
    draw = ImageDraw.Draw(missing)
    for box in tokens["calibration_element_boxes"].values():
        draw.rectangle((box[0], box[1], box[2] - 1, box[3] - 1), fill="#181818")
    fixtures = {
        "identity": reference,
        "resampled_75_percent": resampled,
        "shifted_3px": shifted,
        "wrong_amber_color": wrong_color,
        "missing_element_per_region": missing,
    }
    for name, box in tokens["calibration_element_boxes"].items():
        single = reference.copy()
        ImageDraw.Draw(single).rectangle((box[0], box[1], box[2] - 1, box[3] - 1), fill="#181818")
        fixtures["missing_" + name] = single
    return fixtures


def calibrate(output: Path, *, write: bool = False) -> dict[str, Any]:
    tokens = json.loads(TOKENS.read_text())
    reference = Image.open(REFERENCE).convert("RGB")
    digest = hashlib.sha256(REFERENCE.read_bytes()).hexdigest()
    if digest != tokens["reference_sha256"]:
        raise ValueError("Reference hash mismatch")
    fixtures = challenges(reference, tokens)
    scores = {name: region_scores(reference, im, tokens) for name, im in fixtures.items()}
    thresholds: dict[str, float] = {}
    for region in tokens["boxes"]:
        positive = float(scores["resampled_75_percent"][region]["score"])
        negative = min(
            float(scores[name][region]["score"])
            for name in ("shifted_3px", "wrong_amber_color", "missing_element_per_region")
        )
        if negative <= positive:
            raise ValueError(
                f"Calibration cannot separate defects from resampling in {region}: "
                f"positive={positive:.4f}, negative={negative:.4f}"
            )
        thresholds[region] = (positive + negative) / 2
    settings = {
        "reference_sha256": digest,
        "viewport": tokens["reference_viewport"],
        "blur_radius": BLUR_RADIUS,
        "tile_size": TILE_SIZE,
        "tile_stride": TILE_STRIDE,
        "metric": "maximum masked mean RGB error in overlapping 32px tiles after 0.8px blur",
        "thresholds": thresholds,
    }
    if write:
        CALIBRATION.write_text(json.dumps(settings, indent=2) + "\n")
    else:
        recorded = json.loads(CALIBRATION.read_text())
        if recorded != settings:
            raise ValueError("Calibration settings changed; explicitly recalibrate for review")
    output.mkdir(parents=True, exist_ok=True)
    table = "| Challenge | Expected | Actual | Regions |\n|---|---|---|---|\n"
    rows = []
    for name, im in fixtures.items():
        region_pass = {r: float(scores[name][r]["score"]) <= thresholds[r] for r in thresholds}
        passed = all(region_pass.values())
        expected_pass = name in ("identity", "resampled_75_percent")
        rows.append(
            {
                "challenge": name,
                "expected_pass": expected_pass,
                "passed": passed,
                "calibration_passed": passed == expected_pass,
                "regions": region_pass,
                "scores": scores[name],
            }
        )
        table += f"| {name} | {'PASS' if expected_pass else 'FAIL'} | "
        table += f"{'PASS' if passed else 'FAIL'} | {sum(region_pass.values())}/8 pass |\n"
        if name != "identity":
            ImageChops.difference(reference, im).save(output / f"{name}-diff.png")
    result = {
        "settings": settings,
        "challenges": rows,
        "passed": all(row["calibration_passed"] for row in rows),
    }
    (output / "calibration-results.json").write_text(json.dumps(result, indent=2) + "\n")
    (output / "calibration.md").write_text(table)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    result = calibrate(args.output, write=args.write)
    print((args.output / "calibration.md").read_text())
    raise SystemExit(0 if result["passed"] else 1)
