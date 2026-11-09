"""Shared helpers for the ClimateGuard offline map packs.

- AOI loading (aoi/aoi_5km.geojson)
- Tile lists that follow the AOI shape (not just its bounding box)
- PMTiles writing (tiles sorted by tile id, clustered)
"""
import io
import json
import math
from pathlib import Path

import mercantile
from PIL import Image
from shapely.geometry import box, shape

from pmtiles.tile import Compression, TileType, zxy_to_tileid
from pmtiles.writer import Writer

ROOT = Path(__file__).resolve().parents[1]
AOI_FILE = ROOT / "aoi" / "aoi_5km.geojson"
TILE = 256


def load_aoi(pack_id):
    """Return (main_feature, detail_feature_or_None)."""
    fc = json.loads(AOI_FILE.read_text(encoding="utf-8"))
    main = next(f for f in fc["features"] if f["properties"]["id"] == pack_id)
    det = next((f for f in fc["features"] if f["properties"].get("parent") == pack_id), None)
    return main, det


def all_pack_ids():
    fc = json.loads(AOI_FILE.read_text(encoding="utf-8"))
    return [f["properties"]["id"] for f in fc["features"] if "parent" not in f["properties"]]


def tiles_for(geom, zmin, zmax):
    """(z, x, y) tiles that intersect the geometry, for each zoom."""
    poly = shape(geom) if isinstance(geom, dict) else geom
    out = []
    for z in range(zmin, zmax + 1):
        for t in mercantile.tiles(*poly.bounds, zooms=z):
            if poly.intersects(box(*mercantile.bounds(t))):
                out.append((t.z, t.x, t.y))
    return out


def encode_webp(img, quality):
    buf = io.BytesIO()
    if img.mode == "RGBA" and img.getextrema()[3] == (255, 255):
        img = img.convert("RGB")
    img.save(buf, "WEBP", quality=quality, method=6)
    return buf.getvalue()


def write_pmtiles(path, tiles, bounds, metadata, tile_type=TileType.WEBP):
    """tiles: dict {(z, x, y): bytes}. bounds: (w, s, e, n) in degrees."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    ids = sorted((zxy_to_tileid(z, x, y), (z, x, y)) for (z, x, y) in tiles)
    zooms = [k[0] for k in tiles]
    w, s, e, n = bounds
    with path.open("wb") as f:
        wr = Writer(f)
        for tid, k in ids:
            wr.write_tile(tid, tiles[k])
        wr.finalize(
            {
                "tile_type": tile_type,
                "tile_compression": Compression.NONE,
                "min_lon_e7": int(w * 1e7), "min_lat_e7": int(s * 1e7),
                "max_lon_e7": int(e * 1e7), "max_lat_e7": int(n * 1e7),
                "center_zoom": max(min(zooms), min(max(zooms) - 3, 14)),
                "center_lon_e7": int((w + e) / 2 * 1e7), "center_lat_e7": int((s + n) / 2 * 1e7),
            },
            metadata,
        )
    return path.stat().st_size


def merc_res(z):
    """Web Mercator metres per pixel at the equator for a zoom level."""
    return 2 * math.pi * 6378137 / (TILE * 2 ** z)


def build_pyramid(base_tiles, zmax, zmin):
    """base_tiles: {(x, y): RGBA Image} at zmax. Returns {(z, x, y): Image} for zmin..zmax.
    Parents are built from their four children; missing children stay transparent."""
    levels = {zmax: dict(base_tiles)}
    for z in range(zmax - 1, zmin - 1, -1):
        child = levels[z + 1]
        parents = {}
        for (x, y) in {(cx // 2, cy // 2) for (cx, cy) in child}:
            canvas = Image.new("RGBA", (TILE * 2, TILE * 2), (0, 0, 0, 0))
            for dx in (0, 1):
                for dy in (0, 1):
                    im = child.get((2 * x + dx, 2 * y + dy))
                    if im is not None:
                        canvas.paste(im, (dx * TILE, dy * TILE))
            parents[(x, y)] = canvas.resize((TILE, TILE), Image.LANCZOS)
        levels[z] = parents
    return {(z, x, y): im for z, lv in levels.items() for (x, y), im in lv.items()}
