"""
validation/run_spatial_context_audit.py
Runs Geometry Deduplication & Concentric Spatial Buffer (25m, 50m, 100m, 250m) Analysis across the 320 Plots.
"""

import os
import sys
import json
import math
import requests
import numpy as np
import pandas as pd
from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import transform
import pyproj
import rasterio
from rasterio.windows import from_bounds
from rasterio.warp import reproject, Resampling

sys.stdout.reconfigure(encoding='utf-8')

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from validation.geometry_dedup import find_duplicate_and_overlapping_polygons
from validation.spatial_context import build_concentric_rings, extract_ring_raster_stats, diagnose_spatial_discrepancy

wgs84_to_utm43n = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:32643", always_xy=True).transform

def run_spatial_context_audit(
    empirical_csv: str = "data/output/refined_empirical_sentinel_analysis_320plots.csv",
    output_csv: str = "data/output/spatial_context_audit_320plots.csv"
):
    print("==================================================================")
    print(" IKSHU CONCENTRIC SPATIAL CONTEXT & GEOMETRY DEDUP AUDIT")
    print(f" Source: {empirical_csv} | Output: {output_csv}")
    print(" Concentric Rings: 25m, 50m, 100m, 250m Buffers")
    print("==================================================================")

    df_emp = pd.read_csv(os.path.join(REPO_ROOT, empirical_csv))
    print(f"Loaded {len(df_emp)} evaluated plot records.")

    # 1. Parse Polygons & Load Metadata
    src_csv = os.path.join(REPO_ROOT, "data", "sugarcane_adsali_season_2627.csv")
    df_raw = pd.read_csv(src_csv)
    poly_dict = {}
    for _, raw_r in df_raw.iterrows():
        p_no = str(raw_r["Plot No"]).strip()
        pts = []
        for pair in str(raw_r["Plot Area Lat Long"]).strip().split("#"):
            parts = pair.strip().split(",")
            if len(parts) >= 2:
                pts.append((float(parts[1].strip()), float(parts[0].strip())))
        if len(pts) >= 3:
            poly_dict[p_no] = Polygon(pts)

    parcels_meta = []
    for idx, r in df_emp.iterrows():
        pno = str(r["plot_no"]).strip()
        occ = float(r.get("parcel_cane_occupancy_pct", 0.0))
        ndvi_val = float(r.get("mean_field_ndvi", 0.0))
        parcels_meta.append({
            "plot_no": pno,
            "farmer_name": r.get("farmer_name", ""),
            "village": r.get("village", ""),
            "polygon": poly_dict.get(pno),
            "canopy_occupancy_pct": occ,
            "mean_field_ndvi": ndvi_val,
            "diagnostic_stratum": r.get("diagnostic_stratum", "")
        })

    # Run Geometry Deduplication
    dedup_res = find_duplicate_and_overlapping_polygons(parcels_meta, iou_exact_threshold=0.98)
    print(f"\n[Geometry Deduplication]")
    print(f"  Total Records: {dedup_res['total_records_count']}")
    print(f"  Unique Physical Land Units: {dedup_res['unique_physical_plots_count']}")
    print(f"  Duplicate Polygon Entries: {dedup_res['duplicate_plots_count']}")
    if dedup_res["duplicate_groups"]:
        print(f"  Duplicate Groups: {dedup_res['duplicate_groups']}")

    # 2. Identify High-Canopy Cane Parcels (for Nearest Distance Calculation)
    high_canopy_parcels = [
        p for p in parcels_meta 
        if p["canopy_occupancy_pct"] >= 50.0 and p["polygon"] is not None
    ]
    print(f"\n[Spatial Cluster Reference]")
    print(f"  Confirmed High-Canopy Parcels in Network: {len(high_canopy_parcels)}")

    # 3. Connect to Sentinel-2 COG Archive for Buffer Extraction
    STAC_ENDPOINT = "https://earth-search.aws.element84.com/v1/search"
    payload = {
        "collections": ["sentinel-2-l2a"],
        "bbox": [74.85, 19.15, 76.25, 19.70],
        "datetime": "2026-01-20T00:00:00Z/2026-01-26T23:59:59Z",
        "query": {"eo:cloud_cover": {"lt": 5}},
        "limit": 30
    }
    resp = requests.post(STAC_ENDPOINT, json=payload, timeout=15).json()
    features = resp.get("features", [])

    tiles_features = {}
    for f in features:
        tile = f["id"].split("_")[1]
        if tile in ["43QDB", "43QEB", "43QFB"] and tile not in tiles_features:
            tiles_features[tile] = f

    tile_readers = {}
    for tile, f in tiles_features.items():
        print(f"  Connected [Tile {tile}] -> {f['id']}")
        tile_readers[tile] = {
            "red": rasterio.open(f["assets"]["red"]["href"]),
            "nir": rasterio.open(f["assets"]["nir"]["href"]),
            "scl": rasterio.open(f["assets"]["scl"]["href"])
        }

    # 4. Process Multi-Ring Spatial Context for Each Parcel
    audit_rows = []
    print("\nExtracting Concentric Spatial Buffers (25m, 50m, 100m, 250m)...")

    for idx, p in enumerate(parcels_meta):
        if idx % 40 == 0:
            print(f"  Processed {idx}/{len(parcels_meta)} parcels...")

        poly_wgs = p["polygon"]
        if poly_wgs is None:
            continue

        pno = p["plot_no"]
        group_id = dedup_res["plot_to_group_id"].get(pno, idx)
        is_duplicate = (pno in [item for sublist in dedup_res["duplicate_groups"] for item in sublist])

        # Find Nearest High-Canopy Parcel & Geodesic Distance
        poly_utm = transform(wgs84_to_utm43n, poly_wgs)
        nearest_dist_m = None
        nearest_high_pno = None

        for hc_p in high_canopy_parcels:
            if hc_p["plot_no"] == pno:
                continue
            hc_utm = transform(wgs84_to_utm43n, hc_p["polygon"])
            d = poly_utm.distance(hc_utm)
            if nearest_dist_m is None or d < nearest_dist_m:
                nearest_dist_m = d
                nearest_high_pno = hc_p["plot_no"]

        # Build 25m, 50m, 100m, 250m Concentric Rings
        rings = build_concentric_rings(poly_wgs, [25.0, 50.0, 100.0, 250.0])

        # Determine target tile
        target_reader = None
        minx, miny, maxx, maxy = poly_utm.bounds
        for tile_name, rdr in tile_readers.items():
            tb = rdr["red"].bounds
            if tb.left <= (minx - 300) and (maxx + 300) <= tb.right and tb.bottom <= (miny - 300) and (maxy + 300) <= tb.top:
                target_reader = rdr
                break

        ring_stats = {}
        if target_reader:
            src_red = target_reader["red"]
            src_nir = target_reader["nir"]
            src_scl = target_reader["scl"]
            
            # Read window covering 250m buffer
            buf_250_utm = poly_utm.buffer(270.0)
            b_minx, b_miny, b_maxx, b_maxy = buf_250_utm.bounds
            
            win_10m = from_bounds(b_minx, b_miny, b_maxx, b_maxy, transform=src_red.transform)
            win_trans_10m = src_red.window_transform(win_10m)

            red_arr = src_red.read(1, window=win_10m)
            nir_arr = src_nir.read(1, window=win_10m)

            # SCL is 20m, read window in SCL CRS and reproject to 10m grid
            win_scl = from_bounds(b_minx, b_miny, b_maxx, b_maxy, transform=src_scl.transform)
            scl_raw = src_scl.read(1, window=win_scl)
            
            scl_10m = np.zeros_like(red_arr, dtype=np.uint8)
            reproject(
                source=scl_raw,
                destination=scl_10m,
                src_transform=src_scl.window_transform(win_scl),
                src_crs=src_scl.crs,
                dst_transform=win_trans_10m,
                dst_crs=src_red.crs,
                resampling=Resampling.nearest
            )

            for ring_name, ring_geom in rings.items():
                stats = extract_ring_raster_stats(
                    ring_geom_wgs84=ring_geom,
                    red_raster=red_arr,
                    nir_raster=nir_arr,
                    scl_raster=scl_10m,
                    affine_transform=win_trans_10m,
                    raster_crs=src_red.crs
                )
                ring_stats[ring_name] = stats

        # Diagnose Spatial Discrepancy Cause
        diag = diagnose_spatial_discrepancy(
            inside_canopy_occupancy_pct=p["canopy_occupancy_pct"],
            ring_stats=ring_stats,
            nearest_high_canopy_dist_m=nearest_dist_m
        )

        audit_rows.append({
            "plot_no": pno,
            "farmer_name": p["farmer_name"],
            "village": p["village"],
            "geometry_group_id": group_id,
            "is_duplicate_geometry": is_duplicate,
            "inside_canopy_occupancy_pct": p["canopy_occupancy_pct"],
            "inside_mean_ndvi": p["mean_field_ndvi"],
            "diagnostic_stratum": p["diagnostic_stratum"],
            "nearest_high_canopy_plot_no": nearest_high_pno,
            "nearest_high_canopy_dist_m": round(nearest_dist_m, 1) if nearest_dist_m is not None else None,
            "ring_25m_ndvi": ring_stats.get("ring_25m", {}).get("mean_ndvi"),
            "ring_25m_canopy_pct": ring_stats.get("ring_25m", {}).get("canopy_pct"),
            "ring_50m_ndvi": ring_stats.get("ring_50m", {}).get("mean_ndvi"),
            "ring_50m_canopy_pct": ring_stats.get("ring_50m", {}).get("canopy_pct"),
            "ring_100m_ndvi": ring_stats.get("ring_100m", {}).get("mean_ndvi"),
            "ring_100m_canopy_pct": ring_stats.get("ring_100m", {}).get("canopy_pct"),
            "ring_250m_ndvi": ring_stats.get("ring_250m", {}).get("mean_ndvi"),
            "ring_250m_canopy_pct": ring_stats.get("ring_250m", {}).get("canopy_pct"),
            "spatial_discrepancy_stratum": diag["spatial_discrepancy_stratum"],
            "spatial_diagnostic_rationale": diag["diagnostic_rationale"]
        })

    # Close readers
    for rdr in tile_readers.values():
        rdr["red"].close()
        rdr["nir"].close()
        rdr["scl"].close()

    df_out = pd.DataFrame(audit_rows)
    out_path = os.path.join(REPO_ROOT, output_csv)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    df_out.to_csv(out_path, index=False)
    print(f"\nSaved spatial context audit dataset to: {out_path}")

    # Summary Statistics
    print("\n==================================================================")
    print(" SPATIAL DISCREPANCY AUDIT SUMMARY (320 PLOTS)")
    print("==================================================================")
    for stratum, grp in df_out.groupby("spatial_discrepancy_stratum"):
        print(f"  • {stratum:<45}: {len(grp):>3} plots ({len(grp)/len(df_out)*100.0:>5.1f}%) | Mean Dist to High Cane: {grp['nearest_high_canopy_dist_m'].mean():.1f}m")

if __name__ == "__main__":
    run_spatial_context_audit()