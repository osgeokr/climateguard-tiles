"""Write site/packs.json (the catalogue the app reads).

Packs that were not rebuilt in this run are copied from the currently published site
(--keep-from), so a partial run does not remove anything.

Usage:  python scripts/make_packs.py --site site --keep-from https://osgeokr.github.io/climateguard-tiles
"""
import argparse
import datetime as dt
import gzip
import json
from pathlib import Path

import requests

from pmtiles.tile import deserialize_header
from common import AOI_FILE, all_pack_ids, load_aoi

LAYERS = ("mapa", "sat")


def header_of(p):
    with open(p, "rb") as f:
        h = deserialize_header(f.read(127))
        f.seek(h["metadata_offset"])
        meta = json.loads(gzip.decompress(f.read(h["metadata_length"])))
    return h, meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="site")
    ap.add_argument("--keep-from", default="")
    a = ap.parse_args()
    site = Path(a.site)
    packs_dir = site / "packs"
    packs_dir.mkdir(parents=True, exist_ok=True)

    if a.keep_from:
        try:
            old = requests.get(a.keep_from.rstrip("/") + "/packs.json", timeout=30).json()
            for p in old.get("packs", []):
                for lay, info in p.get("layers", {}).items():
                    dst = site / info["url"]
                    if not dst.exists():
                        print("keep", info["url"])
                        with requests.get(a.keep_from.rstrip("/") + "/" + info["url"], stream=True, timeout=300) as r:
                            r.raise_for_status()
                            with dst.open("wb") as f:
                                for ch in r.iter_content(1 << 20):
                                    f.write(ch)
        except Exception as e:  # first publication: nothing to keep
            print("keep-from skipped:", e)

    out = {"version": 1, "updated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "packs": []}
    for pid in all_pack_ids():
        feat, _ = load_aoi(pid)
        pr = feat["properties"]
        layers = {}
        for lay in LAYERS:
            f = packs_dir / f"{pid}-{lay}.pmtiles"
            if not f.exists():
                continue
            h, meta = header_of(f)
            layers[lay] = {"url": f"packs/{f.name}", "bytes": f.stat().st_size,
                           "minzoom": h["min_zoom"], "maxzoom": h["max_zoom"],
                           "attribution": meta.get("attribution", ""), "built": meta.get("built", "")}
        if not layers:
            continue
        w, s, e, n = pr["bbox"]
        out["packs"].append({"id": pid, "name": {"es": pr["es"], "en": pr["en"]},
                             "bounds": [w, s, e, n], "center": [round((s + n) / 2, 5), round((w + e) / 2, 5)],
                             "layers": layers})
    (site / "packs.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    (site / "aoi_5km.geojson").write_text(AOI_FILE.read_text(encoding="utf-8"), encoding="utf-8")
    tot = sum(l["bytes"] for p in out["packs"] for l in p["layers"].values())
    print(f"packs.json: {len(out['packs'])} packs, {tot / 1e6:.1f} MB in total")


if __name__ == "__main__":
    main()
