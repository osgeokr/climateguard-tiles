# climateguard-tiles

Offline map packs for the [ClimateGuard RD](https://github.com/osgeokr/climateguard-rd) app.
Published with GitHub Pages at `https://osgeokr.github.io/climateguard-tiles/`.

## Packs

One PMTiles file (raster WebP tiles) per area and layer, listed in `packs.json`.

| Area | Satellite (z8-14) | Map (z8-15) |
|---|---|---|
| ITESMARENA, Recinto Jimenoa | yes | yes, z16-17 within 1.5 km of the campus |
| PN Valle Nuevo | yes | yes |
| PN Los Haitises | yes | yes |
| PN Cotubanamá | yes | yes |

Areas: `aoi/aoi_5km.geojson` (protected area boundary from WDPA, or campus point, plus a 5 km buffer).

## Sources and licences

- Map: OpenStreetMap via the Geofabrik extract `haiti-and-domrep`, vector tiles by Planetiler (OpenMapTiles schema), rendered by tileserver-gl. © OpenStreetMap contributors (ODbL), © OpenMapTiles.
- Satellite: Copernicus Sentinel-2 L2A (Earth Search, `sentinel-2-c1-l2a`), cloud-masked median of up to 20 of the clearest scenes in the last two years. "Contains modified Copernicus Sentinel data".

## Build

Actions → **Build offline map packs** → Run workflow.

- `packs`: `all`, or for example `jimenoa,valle-nuevo`
- `layers`: `both`, `mapa` or `sat`

Packs that are not rebuilt are kept from the published site.

Settings → Pages → Source must be set to **GitHub Actions**.

## Adding an area

Add a feature to `aoi/aoi_5km.geojson` with `id`, `es`, `en`, `bbox`, `sat_zoom`, `mapa_zoom`, then run the workflow with that id. The app reads the new pack from `packs.json`, no app update needed.

## Local test packs

```
pip install -r requirements.txt
python scripts/make_test_packs.py --out test-site/packs
python scripts/make_packs.py --site test-site
```
