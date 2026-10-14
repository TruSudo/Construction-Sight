"""Calibrated native perceptual scores, retained masks and four-panel comparison."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from perceptual import BLUR_RADIUS, comparison_mask, region_scores
from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = Path(__file__).parents[2]
TOKENS = ROOT / "src/constructionsight/command_center/design_tokens.json"
CALIBRATION = Path(__file__).with_name("calibration.json")
RATCHET = Path(__file__).with_name("perceptual_ratchet.json")


def compare(reference: Path, actual: Path, output: Path) -> dict[str, Any]:
    tokens = json.loads(TOKENS.read_text())
    calibrated = json.loads(CALIBRATION.read_text())
    expected = Image.open(reference).convert("RGB")
    screenshot = Image.open(actual).convert("RGB")
    size = tuple(tokens["reference_viewport"])
    if expected.size != size or screenshot.size != size:
        raise ValueError(
            "Both images must match the recorded native size; no alignment or resampling"
        )
    digest = hashlib.sha256(reference.read_bytes()).hexdigest()
    reference_matches = digest == tokens["reference_sha256"] == calibrated["reference_sha256"]
    calibration_matches = (
        calibrated["viewport"] == list(size)
        and calibrated["blur_radius"] == BLUR_RADIUS
        and set(calibrated["thresholds"]) == set(tokens["boxes"])
    )
    mask = comparison_mask(expected.size, tokens)
    diff = ImageChops.difference(expected, screenshot)
    perceptual_diff = ImageChops.difference(
        expected.filter(ImageFilter.GaussianBlur(BLUR_RADIUS)),
        screenshot.filter(ImageFilter.GaussianBlur(BLUR_RADIUS)),
    )
    masked = ImageChops.multiply(perceptual_diff, Image.merge("RGB", (mask, mask, mask)))
    regions = region_scores(expected, screenshot, tokens)
    for name, region in regions.items():
        region["threshold"] = calibrated["thresholds"][name]
        region["passed"] = region["score"] <= region["threshold"]
    pixels_pass = (
        reference_matches and calibration_matches and all(r["passed"] for r in regions.values())
    )
    output.mkdir(parents=True, exist_ok=True)
    structure_path = output / "structure.json"
    structure = (
        json.loads(structure_path.read_text()) if structure_path.exists() else {"passed": False}
    )
    ratchet = json.loads(RATCHET.read_text()) if RATCHET.exists() else None
    ratchet_valid = bool(ratchet and ratchet["reference_sha256"] == digest)
    ratchet_pass = ratchet_valid and all(
        r["score"] <= ratchet["regions"][name] + 0.1 for name, r in regions.items()
    )
    diff.save(output / "raw-diff.png")
    masked.save(output / "masked-perceptual-diff.png")
    mask.save(output / "comparison-mask.png")
    canvas = Image.new("RGB", (size[0] * 2, size[1] * 2 + 90), "#111313")
    labels = ImageDraw.Draw(canvas)
    for i, (im, label) in enumerate(
        [
            (expected, f"REFERENCE — NATIVE {size[0]}×{size[1]}"),
            (screenshot, "CURRENT APP — DEMO PARITY"),
            (diff, "RAW DIFF — DIAGNOSTIC ONLY"),
            (masked, "BLURRED DIFF — ALLOWED IMAGERY MASKED; CRANE AND LOGO MEASURED"),
        ]
    ):
        x, y = (i % 2) * size[0], (i // 2) * (size[1] + 45)
        labels.text((x + 15, y + 15), label, fill="white")
        canvas.paste(im, (x, y + 45))
    canvas.save(output / "CommandCenter-comparison.png")
    result = {
        "reference_size": list(size),
        "native_scale_factor": 1,
        "reference_matches_recorded_asset": reference_matches,
        "calibration_matches": calibration_matches,
        "structure_and_fonts_passed": structure["passed"],
        "pixels_passed": pixels_pass,
        "reported_ratchet_passed": ratchet_pass,
        "regions": regions,
        "metric": calibrated["metric"],
        "passed": pixels_pass and structure["passed"],
    }
    (output / "metrics.json").write_text(json.dumps(result, indent=2) + "\n")
    table = "| Region | Mean RGB error | Local score | Threshold | Fidelity |\n"
    table += "|---|---:|---:|---:|---|\n"
    table += "".join(
        f"| {name} | {r['mean_rgb_error']:.3f} | {r['score']:.3f} | "
        f"{r['threshold']:.3f} | {'PASS' if r['passed'] else 'FAIL'} |\n"
        for name, r in regions.items()
    )
    (output / "regions.md").write_text(table)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("actual", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args()
    result = compare(args.reference, args.actual, args.output)
    print(json.dumps(result))
    blocking_pass = (
        result["reference_matches_recorded_asset"]
        and result["calibration_matches"]
        and result["structure_and_fonts_passed"]
    )
    raise SystemExit(0 if (blocking_pass if args.report_only else result["passed"]) else 1)
