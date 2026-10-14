"""Local dark OSM raster PMTiles; public extract, never hosted tile scraping."""

from __future__ import annotations

import argparse
import gzip
import importlib
import io
import json
import math
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from constructionsight.data_folder import digest, resolve_folder

BOUNDS = (-118.0, 33.55, -116.75, 34.5)
ATTRIBUTION = "© OpenStreetMap contributors · ODbL 1.0"
SOURCE = "https://download.geofabrik.de/north-america/us/california/socal-latest.osm.pbf"
TERMS = "https://www.geofabrik.de/data/download.html"
BACKGROUND = "#202323"


def world(lon: float, lat: float, zoom: int) -> tuple[float, float]:
    lat = min(85.0511, max(-85.0511, lat))
    scale = 256 * 2**zoom
    return (
        (lon + 180) / 360 * scale,
        (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * scale,
    )


def metadata(path: Path) -> dict[str, Any]:
    reader = importlib.import_module("pmtiles.reader").Reader
    with path.open("rb") as stream:
        if stream.read(8) != b"PMTiles\x03":
            raise ValueError("Invalid PMTiles v3 header")

        def read(offset: int, length: int) -> bytes:
            stream.seek(offset)
            return stream.read(length)

        header = reader(read).header()
        if header["metadata_length"] > 4_000_000 or header["tile_type"].value != 2:
            raise ValueError("Unsupported local map metadata or format")
        compressed = read(header["metadata_offset"], header["metadata_length"])
        if header["internal_compression"].value == 2:
            with gzip.GzipFile(fileobj=io.BytesIO(compressed)) as zipped:
                raw = zipped.read(4_000_001)
        else:
            raw = compressed
        if len(raw) > 4_000_000:
            raise ValueError("Local map metadata exceeds size limit")
        result: Any = json.loads(raw)
        if not isinstance(result, dict):
            raise ValueError("Local map metadata must be an object")
        return dict(result)


def tile(path: Path, z: int, x: int, y: int) -> bytes | None:
    if not 0 <= z <= 18 or not 0 <= x < 2**z or not 0 <= y < 2**z:
        raise ValueError("Invalid tile coordinate")
    reader = importlib.import_module("pmtiles.reader").Reader
    with path.open("rb") as stream:

        def read(offset: int, length: int) -> bytes:
            stream.seek(offset)
            return stream.read(length)

        archive = reader(read)
        header = archive.header()
        native = min(z, header["max_zoom"])
        delta = z - native
        body: bytes | None = archive.get(native, x >> delta, y >> delta)
    if body is None or not delta:
        return body
    image: Image.Image = Image.open(io.BytesIO(body))
    size = 256 / 2**delta
    left, top = (x % 2**delta) * size, (y % 2**delta) * size
    image = image.crop((left, top, left + size, top + size)).resize(
        (256, 256), Image.Resampling.LANCZOS
    )
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def build(
    extract: Path,
    output: Path,
    *,
    expected_sha256: str,
    bounds: tuple[float, float, float, float] = BOUNDS,
    max_zoom: int = 13,
    source_url: str = SOURCE,
) -> dict[str, Any]:
    if digest(extract) != expected_sha256:
        raise ValueError("OSM extract hash mismatch")
    if not 6 <= max_zoom <= 13:
        raise ValueError("Build zoom must be 6–13")
    osmium = importlib.import_module("osmium")
    writer_module = importlib.import_module("pmtiles.writer")
    tile_module = importlib.import_module("pmtiles.tile")
    features: list[dict[str, Any]] = []
    labels: list[dict[str, Any]] = []
    shields: dict[str, dict[str, Any]] = {}
    west, south, east, north = bounds

    handler_base = osmium.SimpleHandler

    class ExtractHandler(handler_base):  # type: ignore[misc, valid-type]
        def node(self, node: Any) -> None:
            if (
                node.tags.get("place") in ("city", "town", "village")
                and west <= node.location.lon <= east
                and south <= node.location.lat <= north
            ):
                labels.append(
                    {
                        "name": node.tags.get("name", "—"),
                        "lon": node.location.lon,
                        "lat": node.location.lat,
                    }
                )

        def way(self, way: Any) -> None:
            highway = way.tags.get("highway")
            area = way.tags.get("landuse") or way.tags.get("natural")
            if not highway and area not in (
                "water",
                "wood",
                "industrial",
                "residential",
                "commercial",
                "grass",
            ):
                return
            points = [(n.lon, n.lat) for n in way.nodes if n.location.valid()]
            if len(points) < 2 or not any(
                west <= lon <= east and south <= lat <= north for lon, lat in points
            ):
                return
            kind = (
                "motorway"
                if highway in ("motorway", "trunk")
                else "major"
                if highway in ("primary", "secondary", "tertiary")
                else "road"
                if highway
                else area
            )
            features.append({"kind": kind, "points": points})
            ref = way.tags.get("ref")
            if kind == "motorway" and ref and len(ref) <= 20:
                lon, lat = points[len(points) // 2]
                if west <= lon <= east and south <= lat <= north:
                    shields.setdefault(
                        ref,
                        {
                            "ref": ref,
                            "lon": lon,
                            "lat": lat,
                            "asset": "interstate" if ref.startswith("I ") else "state",
                        },
                    )

    with tempfile.TemporaryDirectory(prefix="cs-osmium-") as temporary:
        handler = ExtractHandler()
        processor = osmium.FileProcessor(str(extract)).with_locations(
            "sparse_file_array," + temporary + "/index"
        )
        for entity_index, entity in enumerate(processor):
            if entity_index and entity_index % 2_000_000 == 0:
                print(
                    f"Read {entity_index} OSM entities; regional features {len(features)}",
                    flush=True,
                )
            if isinstance(entity, osmium.osm.Node):
                handler.node(entity)
            elif isinstance(entity, osmium.osm.Way):
                handler.way(entity)
    if not features:
        raise ValueError("Extract contains no map geometry in the requested region")
    font_path = Path(__file__).parent / "command_center/fonts/roboto-400.ttf"
    font: Any
    try:
        font = ImageFont.truetype(str(font_path), 12)
    except OSError:
        font = ImageFont.load_default()
    output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with (
        tempfile.TemporaryDirectory(prefix=".basemap-build-", dir=output.parent) as temporary,
        (Path(temporary) / "archive.pmtiles").open("wb") as stream,
    ):
        writer = writer_module.Writer(stream)
        for zoom in range(6, max_zoom + 1):
            bins: dict[tuple[int, int], list[tuple[str, list[tuple[float, float]]]]] = defaultdict(
                list
            )
            x0, y0 = world(west, north, zoom)
            x1, y1 = world(east, south, zoom)
            for feature in features:
                kind = feature["kind"]
                if zoom < 10 and kind == "road":
                    continue
                points = [world(lon, lat, zoom) for lon, lat in feature["points"]]
                xmin, xmax = min(p[0] for p in points), max(p[0] for p in points)
                ymin, ymax = min(p[1] for p in points), max(p[1] for p in points)
                for x in range(
                    max(int(x0 // 256), int(xmin // 256)), min(int(x1 // 256), int(xmax // 256)) + 1
                ):
                    for y in range(
                        max(int(y0 // 256), int(ymin // 256)),
                        min(int(y1 // 256), int(ymax // 256)) + 1,
                    ):
                        bins[(x, y)].append((kind, points))
            for x in range(int(x0 // 256), int(x1 // 256) + 1):
                for y in range(int(y0 // 256), int(y1 // 256) + 1):
                    image = Image.new("RGB", (256, 256), BACKGROUND)
                    draw = ImageDraw.Draw(image)
                    order = {
                        "water": 0,
                        "wood": 0,
                        "grass": 0,
                        "industrial": 1,
                        "commercial": 1,
                        "residential": 1,
                        "road": 2,
                        "major": 3,
                        "motorway": 4,
                    }
                    for kind, points in sorted(
                        bins[(x, y)], key=lambda item: order.get(item[0], 1)
                    ):
                        local = [(px - x * 256, py - y * 256) for px, py in points]
                        if kind in ("road", "major", "motorway"):
                            width = 1 if kind == "road" else 2 if kind == "major" else 3
                            draw.line(
                                local,
                                fill={"road": "#393d3b", "major": "#77715b", "motorway": "#a18647"}[
                                    kind
                                ],
                                width=width,
                            )
                        elif len(local) >= 3 and points[0] == points[-1]:
                            draw.polygon(
                                local,
                                fill={
                                    "water": "#182c35",
                                    "wood": "#23302a",
                                    "grass": "#29322b",
                                    "industrial": "#2d2c29",
                                    "commercial": "#30302d",
                                    "residential": "#282b2b",
                                }[kind],
                            )
                    if zoom >= 8:
                        for label in labels:
                            px, py = world(label["lon"], label["lat"], zoom)
                            if x * 256 <= px < (x + 1) * 256 and y * 256 <= py < (y + 1) * 256:
                                draw.text(
                                    (px - x * 256, py - y * 256),
                                    label["name"],
                                    font=font,
                                    fill="#d5d5cc",
                                    stroke_width=1,
                                    stroke_fill="#202323",
                                )
                    out = io.BytesIO()
                    image.save(out, format="PNG", optimize=True)
                    writer.write_tile(tile_module.zxy_to_tileid(zoom, x, y), out.getvalue())
                    count += 1
            print(f"OSM tiles through zoom {zoom}: {count}", flush=True)
        info = {
            "name": "ConstructionSight Inland Empire dark OSM",
            "format": "png",
            "bounds": list(bounds),
            "attribution": ATTRIBUTION,
            "license": "https://opendatacommons.org/licenses/odbl/1-0/",
            "source_url": source_url,
            "demo": source_url == "Demo fixture",
            "source_sha256": expected_sha256,
            "provider_terms": TERMS,
            "features": len(features),
            "labels": len(labels),
            "tiles": count,
            "shields": list(shields.values()),
            "detail": (
                "Raster OSM context; maximum native zoom 13. Higher zooms enlarge these tiles. "
                "Outside bounds uses coordinate grid."
            ),
        }
        writer.finalize(
            {
                "tile_compression": tile_module.Compression.NONE,
                "tile_type": tile_module.TileType.PNG,
                "min_lon_e7": int(west * 1e7),
                "min_lat_e7": int(south * 1e7),
                "max_lon_e7": int(east * 1e7),
                "max_lat_e7": int(north * 1e7),
            },
            info,
        )
        stream.flush()
        Path(stream.name).replace(output)
    return {**info, "archive_sha256": digest(output), "bytes": output.stat().st_size}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extract", type=Path, required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    folder = resolve_folder(args.data_dir)
    info = build(args.extract, folder / "basemap.pmtiles", expected_sha256=args.sha256)
    (folder / "basemap-source.json").write_text(json.dumps(info, indent=2) + "\n")
    print(json.dumps(info, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
