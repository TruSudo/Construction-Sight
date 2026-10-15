"""Locate native-view visual mismatches without altering the established scoring gate."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageStat

from perceptual import BLUR_RADIUS, TILE_SIZE, TILE_STRIDE, comparison_mask

ROOT = Path(__file__).parents[2]


def hotspots(reference: Path, actual: Path, output: Path) -> dict[str, Any]:
    tokens = json.loads((ROOT / "src/constructionsight/command_center/design_tokens.json").read_text())
    calibration = json.loads((ROOT / "tests/visual/calibration.json").read_text())
    expected = Image.open(reference).convert("RGB")
    screenshot = Image.open(actual).convert("RGB")
    native = tuple(tokens["reference_viewport"])
    if expected.size != native or screenshot.size != native:
        raise ValueError("Refuse hot spot analysis if either image is resampled")
    mask = comparison_mask(native, tokens)
    diff = ImageChops.difference(
        expected.filter(ImageFilter.GaussianBlur(BLUR_RADIUS)),
        screenshot.filter(ImageFilter.GaussianBlur(BLUR_RADIUS)),
    )
    annotated = screenshot.copy()
    pen = ImageDraw.Draw(annotated)
    report: dict[str, Any] = {"viewport": list(native), "regions": {}, "purpose": "Diagnostic only; no thresholds or imagery masks modified"}
    for name, (x0, y0, x1, y1) in tokens["boxes"].items():
        region, included = diff.crop((x0, y0, x1, y1)), mask.crop((x0, y0, x1, y1))
        ranked = []
        for y in range(0, region.height, TILE_STRIDE):
            for x in range(0, region.width, TILE_STRIDE):
                bounds = (x, y, min(x + TILE_SIZE, region.width), min(y + TILE_SIZE, region.height))
                subset = included.crop(bounds)
                if subset.histogram()[255] < 64:
                    continue
                error = sum(ImageStat.Stat(region.crop(bounds), subset).mean) / 3
                ranked.append((error, (x+x0, y+y0, min(x+TILE_SIZE, region.width)+x0, min(y+TILE_SIZE, region.height)+y0)))
        ranked.sort(reverse=True, key=lambda item: item[0])
        selected = []
        for error, box in ranked:
            cx, cy = (box[0]+box[2])/2, (box[1]+box[3])/2
            if any(math.hypot(cx-(prev["box"][0]+prev["box"][2])/2,cy-(prev["box"][1]+prev["box"][3])/2)<TILE_SIZE for prev in selected):
                continue
            selected.append({"score": round(error,3), "box": list(box)})
            if len(selected) == 5:
                break
        report["regions"][name] = {"threshold": calibration["thresholds"][name], "hotspots": selected}
        for index, found in enumerate(selected[:3], 1):
            pen.rectangle(tuple(found["box"]), outline="#ffbc35", width=2)
            pen.text((found["box"][0]+2, found["box"][1]+1), f"{name[:3]}{index}", fill="#ffffff", stroke_width=2, stroke_fill="#000000")
    output.mkdir(parents=True, exist_ok=True)
    annotated.save(output / "native-hotspots.png")
    (output / "native-hotspots.json").write_text(json.dumps(report, indent=2) + "\n")
    lines = ["| Region | Worst 32px tile (x, y) | Error | Calibrated ceiling |", "|---|---|---:|---:|"]
    for name, detail in report["regions"].items():
        first = detail["hotspots"][0]
        lines.append(f'| {name} | ({first["box"][0]}, {first["box"][1]}) | {first["score"]:.3f} | {detail["threshold"]:.3f} |')
    (output / "native-hotspots.md").write_text("\n".join(lines) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("actual", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = hotspots(args.reference, args.actual, args.output)
    print(json.dumps({name: info["hotspots"][0] for name, info in result["regions"].items()}))
