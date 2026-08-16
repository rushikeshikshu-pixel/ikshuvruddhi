"""
validation/sentinel_canopy_validation.py
Permanent Reproducible Empirical Sentinel-2 Canopy Validation Suite
Evaluates all ground truth sugarcane plots against real Sentinel-2 L2A COG imagery (B02, B03, B04, B05, B08, B11, SCL).
Calculates exact sub-pixel geometric intersection area, strict parcel IoU, boundary exposure, and stratified cohorts.
"""

import os
import sys
import json
import math
import requests
import numpy as np
import pandas as pd
from shapely.geometry import Polygon, box
from shapely.ops import transform
import pyproj
import rasterio
from rasterio.windows import from_bounds
from rasterio.warp import reproject, Resampling

sys.stdout.reconfigure(encoding='utf-8')

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from ml.canopy_classifier import compute_spectral_indices, classify_sugarcane_raster
from validation.metrics import compute_exact_subpixel_intersection_area, compute_boundary_pixel_exposure

wgs84_to_utm43n = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:32643", always_xy=True).transform

def run_empirical_validation(
    limit: int = 320,
    output_csv: str = "data/output/refined_empirical_sentinel_analysis_320plots.csv"
):
    print("==================================================================")
    print(" IKSHU EMPIRICAL SENTINEL-2 CANOPY VALIDATION PIPELINE")
    print(f" Target: All {limit} Ground Truth Parcels | Output: {output_csv}")
    print("==================================================================")

    src_csv = os.path.join(REPO_ROOT, "data", "sugarcane_adsali_season_2627.csv")
    df_raw = pd.read_csv(src_csv)
    print(f"Loaded ground-truth dataset with {len(df_raw)} total plot records.")

    # Query Cloud-Free Sentinel-2 L2A Scenes (Jan 2026)
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
        print(f"  [Tile {tile}] -> {f['id']} (Acquisition: {f['properties']['datetime'][:10]}, Cloud: {f['properties']['eo:cloud_cover']:.4f}%)")
        tile_readers[tile] = {
            "scene_id": f["id"],
            "date": f["properties"]["datetime"][:10],
            "blue": rasterio.open(f["assets"]["blue"]["href"]),
            "green": rasterio.open(f["assets"]["green"]["href"]),
            "red": rasterio.open(f["assets"]["red"]["href"]),
            "nir": rasterio.open(f["assets"]["nir"]["href"]),
            "re": rasterio.open(f["assets"]["rededge1"]["href"]),
            "swir": rasterio.open(f["assets"]["swir16"]["href"]),
            "scl": rasterio.open(f["assets"]["scl"]["href"])
        }

    results = []
    processed_count = 0

    for idx, r in df_raw.iterrows():
        if processed_count >= limit:
            break
        
        pno = str(r["Plot No"]).strip()
        poly_str = str(r["Plot Area Lat Long"]).strip()
        pts = []
        for pair in poly_str.split("#"):
            parts = pair.strip().split(",")
            if len(parts) >= 2:
                pts.append((float(parts[1].strip()), float(parts[0].strip()))) # (lon, lat)
                
        poly_wgs = Polygon(pts)
        poly_utm = transform(wgs84_to_utm43n, poly_wgs)
        ref_area_m2 = poly_utm.area
        ref_area_acres = ref_area_m2 / 4046.8564224
        minx, miny, maxx, maxy = poly_utm.bounds

        # Find target Sentinel-2 scene tile
        target_reader = None
        target_tile = None
        for tile_name, rdr in tile_readers.items():
            tb = rdr["red"].bounds
            if tb.left <= minx and maxx <= tb.right and tb.bottom <= miny and maxy <= tb.top:
                target_tile = tile_name
                target_reader = rdr
                break
                
        if not target_reader:
            continue

        src_blue = target_reader["blue"]
        src_green = target_reader["green"]
        src_red = target_reader["red"]
        src_nir = target_reader["nir"]
        src_re = target_reader["re"]
        src_swir = target_reader["swir"]
        src_scl = target_reader["scl"]

        # Read 10m bands directly
        win_10m = from_bounds(minx, miny, maxx, maxy, src_red.transform)
        win_10m_transform = rasterio.windows.transform(win_10m, src_red.transform)

        blue_10m = src_blue.read(1, window=win_10m).astype(np.float32) / 10000.0
        green_10m = src_green.read(1, window=win_10m).astype(np.float32) / 10000.0
        red_10m = src_red.read(1, window=win_10m).astype(np.float32) / 10000.0
        nir_10m = src_nir.read(1, window=win_10m).astype(np.float32) / 10000.0
        out_shape_10m = red_10m.shape

        # Reproject 20m bands (B05 RedEdge, B11 SWIR, SCL) to 10m grid
        re_10m = np.zeros(out_shape_10m, dtype=np.float32)
        reproject(source=rasterio.band(src_re, 1), destination=re_10m, src_transform=src_re.transform, src_crs=src_re.crs, dst_transform=win_10m_transform, dst_crs=src_red.crs, resampling=Resampling.bilinear)
        re_10m = re_10m / 10000.0

        swir_10m = np.zeros(out_shape_10m, dtype=np.float32)
        reproject(source=rasterio.band(src_swir, 1), destination=swir_10m, src_transform=src_swir.transform, src_crs=src_swir.crs, dst_transform=win_10m_transform, dst_crs=src_red.crs, resampling=Resampling.bilinear)
        swir_10m = swir_10m / 10000.0

        scl_10m = np.zeros(out_shape_10m, dtype=np.uint8)
        reproject(source=rasterio.band(src_scl, 1), destination=scl_10m, src_transform=src_scl.transform, src_crs=src_scl.crs, dst_transform=win_10m_transform, dst_crs=src_red.crs, resampling=Resampling.nearest)

        # Single source of truth multi-spectral indices & classification
        indices = compute_spectral_indices(blue_10m, green_10m, red_10m, re_10m, nir_10m, swir_10m)
        cane_mask = classify_sugarcane_raster(indices["ndvi"], indices["ndre"], indices["lswi"], scl_10m, indices["ndwi"], indices["bsi"])

        # Construct sub-pixel bounding boxes for exact geometric intersection
        cell_boxes = []
        cane_flat = []
        rows, cols = out_shape_10m
        for r_idx in range(rows):
            for c_idx in range(cols):
                px_minx, px_maxy = win_10m_transform * (c_idx, r_idx)
                px_maxx, px_miny = win_10m_transform * (c_idx + 1, r_idx + 1)
                cell_boxes.append((min(px_minx, px_maxx), min(px_miny, px_maxy), max(px_minx, px_maxx), max(px_miny, px_maxy)))
                cane_flat.append(bool(cane_mask[r_idx, c_idx]))

        tot_ref_m2, sat_cane_inside_m2, intersecting_cells = compute_exact_subpixel_intersection_area(cell_boxes, cane_flat, poly_utm)
        boundary_exp_pct = compute_boundary_pixel_exposure(poly_utm)

        sat_detected_acres = sat_cane_inside_m2 / 4046.8564224
        occupancy_pct = (sat_cane_inside_m2 / max(1.0, tot_ref_m2)) * 100.0

        # Exact Union = Parcel Area + (Detected Cane Pixels outside Parcel * 100m2)
        total_detected_cane_m2 = np.sum(cane_mask) * 100.0
        union_m2 = tot_ref_m2 + max(0.0, total_detected_cane_m2 - sat_cane_inside_m2)
        strict_iou_pct = (sat_cane_inside_m2 / max(1.0, union_m2)) * 100.0
        area_error_pct = abs(sat_detected_acres - ref_area_acres) / max(0.01, ref_area_acres) * 100.0

        mean_ndvi = float(np.mean(indices["ndvi"]))
        mean_ndre = float(np.mean(indices["ndre"]))
        mean_lswi = float(np.mean(indices["lswi"]))

        # Primary error attribution
        if mean_ndvi < 0.35:
            attr = "NO_STANDING_VEGETATION_OR_FALLOW"
        elif mean_ndvi < 0.55:
            attr = "LOW_VIGOR_OR_STRESSED_OR_MIXED_CROP"
        elif boundary_exp_pct > 40.0:
            attr = "BOUNDARY_PIXEL_EXPOSURE_AND_GRID_DISCRETIZATION"
        else:
            attr = "CANOPY_HIGH_CONGRUENCE"

        rec = {
            "plot_no": pno,
            "farmer_name": str(r.get("Farmer", r.get("farmer_name", ""))).strip(),
            "village": str(r.get("Village", "")).strip(),
            "source_reference_acres": round(ref_area_acres, 2),
            "sentinel_scene_id": target_reader["scene_id"],
            "scene_acquisition_date": target_reader["date"],
            "tile": target_tile,
            "mean_field_ndvi": round(mean_ndvi, 3),
            "mean_field_ndre": round(mean_ndre, 3),
            "mean_field_lswi": round(mean_lswi, 3),
            "sat_detected_inside_acres": round(sat_detected_acres, 2),
            "parcel_cane_occupancy_pct": round(occupancy_pct, 1),
            "strict_parcel_iou_pct": round(strict_iou_pct, 1),
            "empirical_area_error_pct": round(area_error_pct, 1),
            "estimated_boundary_pixel_exposure_pct": round(boundary_exp_pct, 1),
            "primary_error_attribution": attr
        }
        results.append(rec)
        processed_count += 1
        
        if processed_count % 25 == 0 or processed_count == limit or processed_count <= 5:
            print(f"[{processed_count:3d}/{limit}] Plot #{pno:4s} ({rec['farmer_name'][:18]:18s}) | Ref: {ref_area_acres:.2f} ac | Sat: {sat_detected_acres:.2f} ac | Occ: {occupancy_pct:5.1f}% | IoU: {strict_iou_pct:5.1f}% | NDVI: {mean_ndvi:.3f}")

    df_out = pd.DataFrame(results)
    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    df_out.to_csv(output_csv, index=False)
    print(f"\nSuccessfully wrote {len(df_out)} empirical plot evaluations to {output_csv}\n")
    return df_out

if __name__ == "__main__":
    lim = int(sys.argv[1]) if len(sys.argv) > 1 else 320
    run_empirical_validation(limit=lim)