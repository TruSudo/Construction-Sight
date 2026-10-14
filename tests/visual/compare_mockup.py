"""Native parity comparison: imagery masks preserve controls, markers and text."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter


def compare(reference: Path, actual: Path, output: Path) -> dict:
    tokens = json.loads(
        (
            Path(__file__).parents[2] / "src/constructionsight/command_center/design_tokens.json"
        ).read_text()
    )
    expected = Image.open(reference).convert("RGB")
    screenshot = Image.open(actual).convert("RGB")
    size = tuple(tokens["reference_viewport"])
    if expected.size != size or screenshot.size != size:
        raise ValueError(
            "Reference and parity screenshot must both be native 1536×864; no resampling"
        )
    reference_matches = (
        hashlib.sha256(reference.read_bytes()).hexdigest() == tokens["reference_sha256"]
    )
    mask = Image.new("L", size, 255)
    draw = ImageDraw.Draw(mask)
    for name, box in tokens["visual_masks"].items():
        if name != "brand_antialiasing":
            draw.rectangle(box, fill=0)
    # Only the logo's edge antialiasing is excluded, not its whole rectangle.
    logo_box = tuple(tokens["visual_masks"]["brand_antialiasing"])
    logo_edges = expected.crop(logo_box).convert("L").filter(ImageFilter.FIND_EDGES)
    logo_edges = logo_edges.point(lambda p: 255 if p > 90 else 0).filter(ImageFilter.MaxFilter(3))
    mask.paste(ImageChops.invert(logo_edges), logo_box)
    # Restore all controls/text over imagery, including source markers in the reference.
    for box in [(322, 310, 358, 417), (323, 536, 478, 614), (681, 449, 858, 498)]:
        draw.rectangle(box, fill=255)
    for x, y in [
        (504, 357),
        (621, 339),
        (800, 359),
        (558, 410),
        (633, 417),
        (711, 414),
        (792, 415),
        (419, 470),
        (489, 503),
        (671, 507),
        (790, 518),
        (701, 557),
        (861, 548),
    ]:
        draw.ellipse((x - 16, y - 16, x + 16, y + 16), fill=255)
    diff = ImageChops.difference(expected, screenshot)
    masked = ImageChops.multiply(diff, Image.merge("RGB", (mask, mask, mask)))
    tolerance = tokens["visual_test"]["channel_tolerance"]

    def score(box: tuple[int, ...]) -> dict:
        pixels = list(diff.crop(box).get_flattened_data())
        included = list(mask.crop(box).get_flattened_data())
        selected = [p for p, m in zip(pixels, included, strict=True) if m]
        changed = sum(max(p) > tolerance for p in selected)
        return {
            "changed_pixels": changed,
            "compared_pixels": len(selected),
            "changed_fraction": changed / len(selected) if selected else 0,
            "channel_mae": sum(sum(p) for p in selected) / (3 * len(selected)) if selected else 0,
        }

    regions = {name: score(tuple(box)) for name, box in tokens["boxes"].items()}
    overall = score((0, 0, *size))
    output.mkdir(parents=True, exist_ok=True)
    structure_path = output / "structure.json"
    structure = (
        json.loads(structure_path.read_text()) if structure_path.exists() else {"passed": False}
    )
    pixels_pass = (
        reference_matches
        and overall["changed_fraction"]
        <= tokens["visual_test"]["max_changed_static_pixels_fraction"]
    )
    passed = pixels_pass and structure["passed"]
    diff.save(output / "raw-diff.png")
    masked.save(output / "masked-diff.png")
    mask.save(output / "comparison-mask.png")
    canvas = Image.new("RGB", (size[0] * 2, size[1] * 2 + 90), "#111313")
    labels = ImageDraw.Draw(canvas)
    for i, (im, label) in enumerate(
        [
            (expected, "REFERENCE — NATIVE 1536×864"),
            (screenshot, "CURRENT APP — DEMO PARITY"),
            (diff, "RAW DIFF"),
            (
                masked,
                f"OUTSIDE IMAGERY MASKS: {overall['changed_fraction']:.2%} changed; target 1%",
            ),
        ]
    ):
        x = (i % 2) * size[0]
        y = (i // 2) * (size[1] + 45)
        labels.text((x + 15, y + 15), label, fill="white")
        canvas.paste(im, (x, y + 45))
    canvas.save(output / "CommandCenter-comparison.png")
    result = {
        "reference_size": list(size),
        "reference_matches_recorded_asset": reference_matches,
        "structure_and_fonts_passed": structure["passed"],
        "pixels_passed": pixels_pass,
        "static_changed_fraction": overall["changed_fraction"],
        "reported_ratchet_passed": overall["changed_fraction"]
        <= tokens["visual_test"]["reported_ratchet_baseline"],
        "regions": regions,
        "threshold": tokens["visual_test"],
        "passed": passed,
    }
    (output / "metrics.json").write_text(json.dumps(result, indent=2) + "\n")
    table = "| Region | Changed pixels outside masks | Pixels compared |\n|---|---:|---:|\n"
    table += "".join(
        f"| {name} | {r['changed_fraction']:.2%} | {r['compared_pixels']:,} |\n"
        for name, r in regions.items()
    )
    (output / "regions.md").write_text(table)
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("reference", type=Path)
    p.add_argument("actual", type=Path)
    p.add_argument("output", type=Path)
    p.add_argument(
        "--report-only",
        action="store_true",
        help="Report pixel differences without blocking; structure and fonts still block",
    )
    a = p.parse_args()
    r = compare(a.reference, a.actual, a.output)
    print(json.dumps(r))
    gate_passed = (
        r["structure_and_fonts_passed"] and r["reference_matches_recorded_asset"]
        if a.report_only
        else r["passed"]
    )
    raise SystemExit(0 if gate_passed else 1)
