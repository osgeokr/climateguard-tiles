"""Street map pack: OpenStreetMap rendered to raster tiles, zoom 8..15 (17 around the
training campus), WebP, PMTiles.

Rendering is done by a local tileserver-gl (see the workflow) serving vector tiles that
Planetiler built from the Geofabrik extract of the Dominican Republic.

Usage:  python scripts/build_mapa.py --id jimenoa --server http://localhost:8080 --out site/packs
"""
import argparse
import datetime as dt
import io
import time
from concurrent.futures import ThreadPoolExecutor

import requests
from PIL import Image
from shapely.geometry import shape

from common import encode_webp, load_aoi, tiles_for, write_pmtiles

ZMIN, ZMAX = 8, 15


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True)
    ap.add_argument("--server", default="http://localhost:8080")
    ap.add_argument("--style", default="")
    ap.add_argument("--out", default="site/packs")
    ap.add_argument("--quality", type=int, default=82)
    a = ap.parse_args()

    style = a.style or requests.get(f"{a.server}/styles.json", timeout=30).json()[0]["id"]
    feat, det = load_aoi(a.id)
    poly = shape(feat["geometry"])
    z = feat["properties"].get("mapa_zoom", [ZMIN, ZMAX])
    want = tiles_for(poly, z[0], min(z[1], ZMAX))
    if det:
        dz = det["properties"]["mapa_zoom"]
        want += tiles_for(shape(det["geometry"]), dz[0], dz[1])
    want = sorted(set(want))
    print(f"{a.id}: {len(want)} tiles, style '{style}'")

    s = requests.Session()

    def fetch(k):
        zz, x, y = k
        url = f"{a.server}/styles/{style}/256/{zz}/{x}/{y}.png"
        for i in range(4):
            try:
                r = s.get(url, timeout=60)
                if r.status_code == 200:
                    return k, encode_webp(Image.open(io.BytesIO(r.content)).convert("RGB"), a.quality)
            except requests.RequestException:
                pass
            time.sleep(1 + i)
        raise RuntimeError(f"render failed: {url}")

    with ThreadPoolExecutor(8) as ex:
        tiles = dict(ex.map(fetch, want))

    size = write_pmtiles(f"{a.out}/{a.id}-mapa.pmtiles", tiles, poly.bounds, {
        "name": f"{a.id} map", "format": "webp", "type": "baselayer",
        "attribution": "© OpenStreetMap contributors, © OpenMapTiles",
        "built": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")})
    print(f"{a.id}-mapa.pmtiles: {len(tiles)} tiles, {size / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
