"""Satellite pack: cloud-free Sentinel-2 true-colour mosaic, zoom 8..14, WebP, PMTiles.

Source: Earth Search (Element 84) STAC, collection sentinel-2-c1-l2a (Copernicus
Sentinel-2, free and open). Clouds and shadows are removed with the SCL band and a
per-pixel median of the clearest scenes.

Usage:  python scripts/build_sat.py --id valle-nuevo --out site/packs
"""
import argparse
import datetime as dt

import mercantile
import numpy as np
from PIL import Image
from shapely.geometry import shape

from common import TILE, build_pyramid, encode_webp, load_aoi, merc_res, tiles_for, write_pmtiles

STAC = "https://earth-search.aws.element84.com/v1"
COLLECTION = "sentinel-2-c1-l2a"
ZMAX, ZMIN = 14, 8
VALID_SCL = [2, 4, 5, 6, 7, 11]          # dark area, vegetation, bare, water, unclassified, snow


def to_rgb8(r, g, b):
    """L2A digital numbers (offset 1000, scale 1e-4) -> 8-bit true colour with a gentle gamma."""
    out = []
    for band in (r, g, b):
        refl = (band.astype("float32") - 1000.0) / 10000.0
        v = np.clip(refl / 0.30, 0, 1) ** (1 / 1.8)
        out.append(np.where(np.isnan(band), 0, v * 255).astype("uint8"))
    return np.dstack(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True)
    ap.add_argument("--out", default="site/packs")
    ap.add_argument("--start", default=(dt.date.today() - dt.timedelta(days=730)).isoformat())
    ap.add_argument("--end", default=dt.date.today().isoformat())
    ap.add_argument("--maxcloud", type=float, default=60)
    ap.add_argument("--maxitems", type=int, default=20)
    ap.add_argument("--quality", type=int, default=70)
    a = ap.parse_args()

    import pystac_client
    import odc.stac
    from odc.geo.geobox import GeoBox

    odc.stac.configure_rio(cloud_defaults=True)
    feat, _ = load_aoi(a.id)
    poly = shape(feat["geometry"])
    w, s, e, n = poly.bounds

    items = pystac_client.Client.open(STAC).search(
        collections=[COLLECTION], bbox=[w, s, e, n], datetime=f"{a.start}/{a.end}",
        query={"eo:cloud_cover": {"lt": a.maxcloud}}, max_items=400).item_collection()
    items = sorted(items, key=lambda it: it.properties.get("eo:cloud_cover", 100))[: a.maxitems]
    if not items:
        raise SystemExit(f"{a.id}: no Sentinel-2 scenes found")
    print(f"{a.id}: {len(items)} scenes, cloud cover {[round(i.properties['eo:cloud_cover']) for i in items]}")

    # Grid aligned with the zoom-14 tile grid, so each 256x256 block is exactly one tile.
    z14 = list(mercantile.tiles(w, s, e, n, zooms=ZMAX))
    x0, x1 = min(t.x for t in z14), max(t.x for t in z14)
    y0, y1 = min(t.y for t in z14), max(t.y for t in z14)
    ul = mercantile.xy_bounds(x0, y0, ZMAX)
    lr = mercantile.xy_bounds(x1, y1, ZMAX)
    res = merc_res(ZMAX)
    from affine import Affine
    gbox = GeoBox(((y1 - y0 + 1) * TILE, (x1 - x0 + 1) * TILE),
                  Affine(res, 0, ul.left, 0, -res, ul.top), "EPSG:3857")

    ds = odc.stac.load(items, bands=["red", "green", "blue", "scl"], geobox=gbox,
                       chunks={"x": 1024, "y": 1024}, groupby="solar_day",
                       resampling={"*": "bilinear", "scl": "nearest"})
    ok = ds.scl.isin(VALID_SCL)
    comp = ds[["red", "green", "blue"]].where(ok).where(ds.red > 0)
    med = comp.median(dim="time", skipna=True).compute()
    # Gaps that stayed cloudy in every scene: fall back to the clearest single scene.
    first = ds[["red", "green", "blue"]].isel(time=0).where(ds.red.isel(time=0) > 0).compute()
    med = med.fillna(first)

    r, g, b = (med[k].values for k in ("red", "green", "blue"))
    rgb = to_rgb8(r, g, b)
    alpha = np.where(np.isnan(r), 0, 255).astype("uint8")
    rgba = np.dstack([rgb, alpha])
    H, W = rgba.shape[:2]

    base = {}
    for t in z14:
        px, py = (t.x - x0) * TILE, (t.y - y0) * TILE
        block = rgba[py:py + TILE, px:px + TILE]
        if block.shape[0] == TILE and block.shape[1] == TILE:
            base[(t.x, t.y)] = Image.fromarray(block, "RGBA")
    pyr = build_pyramid(base, ZMAX, ZMIN)
    wanted = set(tiles_for(poly, ZMIN, ZMAX))
    tiles = {k: encode_webp(im, a.quality) for k, im in pyr.items() if k in wanted and im.getextrema()[3][1] > 0}

    years = sorted({i.datetime.year for i in items})
    size = write_pmtiles(f"{a.out}/{a.id}-sat.pmtiles", tiles, poly.bounds, {
        "name": f"{a.id} satellite", "format": "webp", "type": "baselayer",
        "attribution": f"Contains modified Copernicus Sentinel data {years[0]}-{years[-1]}",
        "scenes": len(items), "built": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
    print(f"{a.id}-sat.pmtiles: {len(tiles)} tiles, {size / 1e6:.1f} MB ({W}x{H} px mosaic)")


if __name__ == "__main__":
    main()
