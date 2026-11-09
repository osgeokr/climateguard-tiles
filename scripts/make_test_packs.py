"""Synthetic packs for testing the app offline (no network needed).
Each tile shows its z/x/y so you can see which pack is drawn.

Usage:  python scripts/make_test_packs.py --out test-site/packs [--maxzoom 13]
"""
import argparse

from PIL import Image, ImageDraw
from shapely.geometry import shape

from common import TILE, all_pack_ids, build_pyramid, encode_webp, load_aoi, tiles_for, write_pmtiles


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="test-site/packs")
    ap.add_argument("--maxzoom", type=int, default=13)
    a = ap.parse_args()
    for pid in all_pack_ids():
        feat, _ = load_aoi(pid)
        poly = shape(feat["geometry"])
        for lay, col in (("sat", (40, 90, 50)), ("mapa", (238, 232, 214))):
            want = set(tiles_for(poly, 8, a.maxzoom))
            base = {}
            for (z, x, y) in want:
                if z != a.maxzoom:
                    continue
                im = Image.new("RGBA", (TILE, TILE), col + (255,))
                d = ImageDraw.Draw(im)
                d.rectangle([0, 0, TILE - 1, TILE - 1], outline=(200, 60, 40, 255), width=2)
                d.text((10, 10), f"{pid} {lay}\n{z}/{x}/{y}", fill=(255, 255, 255, 255) if lay == "sat" else (60, 60, 60, 255))
                base[(x, y)] = im
            pyr = build_pyramid(base, a.maxzoom, 8)
            tiles = {k: encode_webp(im, 70) for k, im in pyr.items() if k in want}
            n = write_pmtiles(f"{a.out}/{pid}-{lay}.pmtiles", tiles, poly.bounds,
                              {"name": f"{pid} {lay} TEST", "attribution": "TEST tiles", "built": "test"})
            print(pid, lay, len(tiles), "tiles", round(n / 1e6, 2), "MB")


if __name__ == "__main__":
    main()
