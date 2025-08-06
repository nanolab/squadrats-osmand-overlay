#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Download MVT tiles (z-fetch) that intersect a region (west_flanders.geojson) and
append the chosen layer into a local GeoPackage.

> Run from **OSGeo4W Shell** (ogr2ogr must be in PATH).

Example:
python fetch_tiles_west_flanders.py ^
  --base-url "https://tiles1.squadrats.com/fiwoOW0G6oZ5Hn0eeR1TeHgc7lU2/trophies/1754233411401/{z}/{x}/{y}.pbf" ^
  --region-geojson west_flanders.geojson ^
  --z-fetch 12 ^
  --layer squadratinhos ^
  --out squadratinhos.gpkg
"""
import argparse, json, math, os, subprocess, sys

def lonlat_to_tilexy(lon, lat, z):
    # clamp latitude for WebMercator
    lat = max(min(lat, 85.05112878), -85.05112878)
    n = 2.0 ** z
    xtile = int((lon + 180.0) / 360.0 * n)
    lat_rad = math.radians(lat)
    ytile = int((1.0 - math.log(math.tan(lat_rad) + 1.0 / math.cos(lat_rad)) / math.pi) / 2.0 * n)
    xtile = max(0, min(int(n) - 1, xtile))
    ytile = max(0, min(int(n) - 1, ytile))
    return xtile, ytile

def bbox_from_geojson(path):
    with open(path, "r", encoding="utf-8") as f:
        gj = json.load(f)
    xs, ys = [], []
    def it(g):
        if isinstance(g, dict):
            if "coordinates" in g:
                for c in it(g["coordinates"]): yield c
            elif "geometries" in g:
                for gg in g["geometries"]:
                    for c in it(gg): yield c
            elif "features" in g:
                for feat in g.get("features", []):
                    for c in it(feat.get("geometry", {})): yield c
        elif isinstance(g, (list, tuple)):
            if len(g) == 2 and all(isinstance(v, (int, float)) for v in g):
                yield g
            else:
                for x in g:
                    for c in it(x): yield c
    for lon, lat in it(gj):
        xs.append(lon); ys.append(lat)
    return min(xs), min(ys), max(xs), max(ys)

def main():
    ap = argparse.ArgumentParser(description="Fetch z=12 MVT tiles over a region into a local GPKG (single layer).")
    ap.add_argument("--base-url", required=True, help="Template like .../{z}/{x}/{y}.pbf")
    ap.add_argument("--region-geojson", required=True, help="Region boundary (WGS84) e.g., west_flanders.geojson")
    ap.add_argument("--z-fetch", type=int, default=12, help="Server max zoom to fetch (e.g., 12)")
    ap.add_argument("--layer", default="squadratinhos", help="Layer name to extract from MVT")
    ap.add_argument("--out", default="squadratinhos.gpkg", help="Output GeoPackage path")
    ap.add_argument("--promote-multi", action="store_true", help="Use -nlt PROMOTE_TO_MULTI")
    args = ap.parse_args()

    # Reproject region to 3857 for clipping
    region_3857 = os.path.splitext(args.region_geojson)[0] + "_3857.geojson"
    if not os.path.exists(region_3857):
        r = subprocess.run(["ogr2ogr", "-t_srs", "EPSG:3857", region_3857, args.region_geojson])
        if r.returncode != 0:
            print("Failed to reproject region to EPSG:3857", file=sys.stderr)
            sys.exit(1)

    # Compute tile range from region bbox at z-fetch
    minlon, minlat, maxlon, maxlat = bbox_from_geojson(args.region_geojson)
    x0, y1 = lonlat_to_tilexy(minlon, maxlat, args.z_fetch)
    x1, y0 = lonlat_to_tilexy(maxlon, minlat, args.z_fetch)
    xmin, xmax = min(x0, x1), max(x0, x1)
    ymin, ymax = min(y0, y1), max(y0, y1)

    total = (xmax - xmin + 1) * (ymax - ymin + 1)
    print(f"Fetching z={args.z_fetch} tiles in x[{xmin}..{xmax}] y[{ymin}..{ymax}]  (~{total} tiles)")

    # Prepare output GPKG: first write nothing (ogr2ogr will create on first append)
    if os.path.exists(args.out):
        print(f"Appending into existing {args.out}")
    else:
        print(f"Creating {args.out}")

    appended = 0
    for x in range(xmin, xmax + 1):
        for y in range(ymin, ymax + 1):
            url = args.base_url.format(z=args.z_fetch, x=x, y=y)
            cmd = [
                "ogr2ogr", "-f", "GPKG", args.out, f"MVT:{url}",
                "-update", "-append",
                "-nln", args.layer,
                "-dialect", "OGRSQL", "-sql", f"SELECT * FROM {args.layer}",
                "-oo", f"Z={args.z_fetch}", "-oo", f"X={x}", "-oo", f"Y={y}",
                "-t_srs", "EPSG:3857",
                "-clipsrc", region_3857
            ]
            if args.promote_multi:
                cmd += ["-nlt", "PROMOTE_TO_MULTI"]

            r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if r.returncode != 0:
                # Likely empty/404; print short notice and continue
                msg = r.stderr.decode(errors="ignore").strip().splitlines()[-1:] or ["error"]
                print(f"skip z={args.z_fetch} x={x} y={y}: {msg[0]}")
                continue
            appended += 1
            if appended % 50 == 0:
                print(f"  appended from {appended} tiles...")

    print(f"Done. Output: {args.out}")
    print(f"Region (3857) used for clip: {region_3857}")

if __name__ == "__main__":
    main()
