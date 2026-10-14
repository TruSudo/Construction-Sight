from __future__ import annotations

import json
import threading
from pathlib import Path

import httpx
import pytest

from constructionsight import offline_map
from constructionsight.data_folder import digest
from constructionsight.live_command_center import ASSETS, make_server


def test_real_osm_geometry_local_pmtiles_hash_and_tile_route(tmp_path: Path) -> None:
    extract = tmp_path / "region.osm"
    extract.write_text("""<?xml version="1.0"?><osm version="0.6">
    <node id="1" lat="34.00" lon="-117.30" version="1">
    <tag k="place" v="city"/><tag k="name" v="Fixture City"/></node>
    <node id="2" lat="34.01" lon="-117.29" version="1"/>
    <way id="1" version="1"><nd ref="1"/><nd ref="2"/><tag k="highway" v="motorway"/>
    <tag k="ref" v="I 215"/></way></osm>""")
    archive = tmp_path / "map.pmtiles"
    with pytest.raises(ValueError, match="hash mismatch"):
        offline_map.build(extract, archive, expected_sha256="bad")
    info = offline_map.build(
        extract, archive, expected_sha256=digest(extract), max_zoom=8, source_url="Demo fixture"
    )
    assert info["features"] == 1 and info["labels"] == 1 and info["tiles"] > 0
    assert info["archive_sha256"] == digest(archive)
    assert offline_map.metadata(archive)["shields"][0]["ref"] == "I 215"
    px, py = offline_map.world(-117.3, 34, 8)
    body = offline_map.tile(archive, 8, int(px // 256), int(py // 256))
    assert body and body.startswith(b"\x89PNG")
    with pytest.raises(ValueError):
        offline_map.tile(archive, 19, 0, 0)
    directory = tmp_path / "data"
    server = make_server(json.loads((ASSETS / "demo.json").read_text()), 0, directory)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with httpx.Client(base_url=base, headers={"Origin": base}) as client:
            assert (
                client.post(
                    "/api/offline-map-install",
                    content=archive.read_bytes(),
                    headers={"X-Archive-SHA256": "bad"},
                ).status_code
                == 400
            )
            installed = client.post(
                "/api/offline-map-install",
                content=archive.read_bytes(),
                headers={"X-Archive-SHA256": digest(archive)},
            )
            assert installed.status_code == 200, installed.text
            assert client.get("/api/leads").json()["local_map"]["features"] == 1
            response = client.get(f"/api/offline-map/8/{int(px // 256)}/{int(py // 256)}.png")
            assert response.status_code == 200 and response.content == body
            assert client.get("/shield-interstate.svg").status_code == 200
            assert client.get("/api/offline-map/8/0/0.png").status_code == 404
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
