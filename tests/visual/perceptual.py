"""Native, antialias-tolerant image comparison with local defect sensitivity."""

from __future__ import annotations

from typing import Any

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageStat

BLUR_RADIUS = 0.8
TILE_SIZE = 32
TILE_STRIDE = 16


def comparison_mask(size: tuple[int, int], tokens: dict[str, Any]) -> Image.Image:
    mask = Image.new("L", size, 255)
    draw = ImageDraw.Draw(mask)
    for box in tokens["visual_masks"].values():
        x0, y0, x1, y1 = box
        draw.rectangle((x0, y0, x1 - 1, y1 - 1), fill=0)
    for box in tokens["map_control_boxes"]:
        x0, y0, x1, y1 = box
        draw.rectangle((x0, y0, x1 - 1, y1 - 1), fill=255)
    for x, y in tokens["map_marker_centers"]:
        draw.ellipse((x - 16, y - 16, x + 16, y + 16), fill=255)
    return mask


def region_scores(
    expected: Image.Image, actual: Image.Image, tokens: dict[str, Any]
) -> dict[str, dict[str, float | int]]:
    if actual.size != expected.size or list(expected.size) != tokens["reference_viewport"]:
        raise ValueError("Comparison requires both images at the recorded native resolution")
    mask = comparison_mask(expected.size, tokens)
    # Blur both images before measuring, not the binary error mask. This suppresses
    # raster edge differences without allowing alignment or scale correction.
    diff = ImageChops.difference(
        expected.convert("RGB").filter(ImageFilter.GaussianBlur(BLUR_RADIUS)),
        actual.convert("RGB").filter(ImageFilter.GaussianBlur(BLUR_RADIUS)),
    )
    result: dict[str, dict[str, float | int]] = {}
    for name, box in tokens["boxes"].items():
        region, included = diff.crop(box), mask.crop(box)
        count = included.histogram()[255]
        if not count:
            raise ValueError(f"Region {name} has no unmasked pixels")
        mean = sum(ImageStat.Stat(region, included).mean) / 3
        peak = 0.0
        for y in range(0, region.height, TILE_STRIDE):
            for x in range(0, region.width, TILE_STRIDE):
                tile = (x, y, min(x + TILE_SIZE, region.width), min(y + TILE_SIZE, region.height))
                tile_mask = included.crop(tile)
                # Avoid tiny slivers on mask/region edges dominating the result.
                if tile_mask.histogram()[255] < 64:
                    continue
                error = sum(ImageStat.Stat(region.crop(tile), tile_mask).mean) / 3
                peak = max(peak, error)
        result[name] = {
            "compared_pixels": count,
            "mean_rgb_error": mean,
            "local_peak_rgb_error": peak,
            "score": peak,
        }
    return result
