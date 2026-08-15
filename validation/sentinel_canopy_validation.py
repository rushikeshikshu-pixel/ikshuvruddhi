from rasterio.features import rasterize
"""
validation/sentinel_canopy_validation.py
Permanent, Reproducible Sentinel-2 Ground-Truth Validation Pipeline

Features:
  1. Exact EPSG:32643 UTM Zone 43N metric projection.
  2. Single Source of Truth Canopy Classifier (ml.canopy_classifier).
  3. Strict 20m -> 10m band reprojection (B05/B11 Bilinear, SCL Nearest) using rasterio.warp.reproject.
  4. Exact Geometric Sub-Pixel Intersection Area: Sum(Area(Cell_i ∩ Parcel)).
  5. Multi-Tile Auto-Discovery (43QDB, 43QEB, 43QFB).
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

# Ensure repo root is on sys.path
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from ml.canopy_classifier import classify_sugarcane_raster
from validation.metrics import compute_exact_subpixel_intersection_area, compute_boundary_pixel_exposure

wgs84_to_utm43n = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:32643", always_xy=True).transform

def run_validation(limit_plots=88, output_csv="data/output/refined_empirical_sentinel_analysis_88plots.csv"):
    print("==================================================================")
    print(" IKSHU REPRODUCIBLE EMPIRICAL SENTINEL-2 CANOPY VALIDATION")
    print(f" Target Plots: {limit_plots} | Output CSV: {output_csv}")
    print("==================================================================")

    # 1. Load Ground-Truth Dataset
    src_csv = os.path.join(REPO_ROOT, "data", "sugarcane_adsali_season_2627.csv")
    if not os.path.exists(src_csv):
        src_csv = os.path.join(REPO_ROOT, "data", "sample", "farmer_sample_input.csv")
    
    df = pd.read_csv(src_csv)
    print(f"Loaded ground-truth dataset with {len(df)} total plot records.")

    # 2. Query Copernicus Sentinel-2 STAC for clear overpasses
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
            print(f"  [Tile {tile}] -> {f['id']} (Acquisition: {f['properties']['datetime'][:10]}, Cloud: {f['properties'].get('eo:cloud_cover'):.4f}%)")

    # Open COG Readers
    tile_readers = {}
    for tile, f in tiles_features.items():
        tile_readers[tile] = {
            "scene_id": f["id"],
            "date": f["properties"]["datetime"][:10],
            "red": rasterio.open(f["assets"]["red"]["href"]),
            "nir": rasterio.open(f["assets"]["nir"]["href"]),
            "re": rasterio.open(f["assets"]["rededge1"]["href"]),
            "swir": rasterio.open(f["assets"]["swir16"]["href"]),
            "scl": rasterio.open(f["assets"]["scl"]["href"])
        }

    results = []
    n_eval = min(limit_plots, len(df))

    for i in range(n_eval):
        row = df.iloc[i]
        pno = str(row["Plot No"]).strip()
        farmer = str(row["Farmer"]).strip()
        variety = str(row["Variety Name"]).strip()
        village = str(row["Village"]).strip()
        
        poly_str = str(row["Plot Area Lat Long"]).strip()
        pts = []
        for pair in poly_str.split("#"):
            parts = pair.strip().split(",")
            if len(parts) >= 2:
                pts.append((float(parts[1].strip()), float(parts[0].strip()))) # (lon, lat)
                
        poly_wgs = Polygon(pts)
        poly_utm = transform(wgs84_to_utm43n, poly_wgs)
        gt_area_m2 = poly_utm.area
        gt_area_acres = gt_area_m2 / 4046.8564224
        
        minx, miny, maxx, maxy = poly_utm.bounds
        
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
            
        src_red = target_reader["red"]
        src_nir = target_reader["nir"]
        src_re = target_reader["re"]
        src_swir = target_reader["swir"]
        src_scl = target_reader["scl"]
        
        # 10m grid window & affine transform
        win_10m = from_bounds(minx, miny, maxx, maxy, src_red.transform)
        win_10m_transform = rasterio.windows.transform(win_10m, src_red.transform)
        
        red_10m = src_red.read(1, window=win_10m).astype(np.float32)
        nir_10m = src_nir.read(1, window=win_10m).astype(np.float32)
        out_shape_10m = red_10m.shape
        
        # Exact Bilinear / Nearest Reprojection
        re_10m = np.zeros(out_shape_10m, dtype=np.float32)
        reproject(
            source=rasterio.band(src_re, 1),
            destination=re_10m,
            src_transform=src_re.transform,
            src_crs=src_re.crs,
            dst_transform=win_10m_transform,
            dst_crs=src_red.crs,
            resampling=Resampling.bilinear
        )
        
        swir_10m = np.zeros(out_shape_10m, dtype=np.float32)
        reproject(
            source=rasterio.band(src_swir, 1),
            destination=swir_10m,
            src_transform=src_swir.transform,
            src_crs=src_swir.crs,
            dst_transform=win_10m_transform,
            dst_crs=src_red.crs,
            resampling=Resampling.bilinear
        )
        
        scl_10m = np.zeros(out_shape_10m, dtype=np.uint8)
        reproject(
            source=rasterio.band(src_scl, 1),
            destination=scl_10m,
            src_transform=src_scl.transform,
            src_crs=src_scl.crs,
            dst_transform=win_10m_transform,
            dst_crs=src_red.crs,
            resampling=Resampling.nearest
        )
        
        # Multi-Spectral Indices
        with np.errstate(divide="ignore", invalid="ignore"):
            ndvi = (nir_10m - red_10m) / (nir_10m + red_10m + 1e-7)
            ndre = (nir_10m - re_10m) / (nir_10m + re_10m + 1e-7)
            lswi = (nir_10m - swir_10m) / (nir_10m + swir_10m + 1e-7)
            
        # Unified Classifier Call
        cane_mask_2d = classify_sugarcane_raster(ndvi, ndre, lswi, scl_10m)
        
        # Build cell bounding boxes for exact sub-pixel intersection
        cell_boxes = []
        cane_flat = []
        rows, cols = out_shape_10m
        for r in range(rows):
            for c in range(cols):
                # Calculate pixel corners in UTM
                px_minx, px_maxy = win_10m_transform * (c, r)
                px_maxx, px_miny = win_10m_transform * (c + 1, r + 1)
                cell_boxes.append((min(px_minx, px_maxx), min(px_miny, px_maxy), max(px_minx, px_maxx), max(px_miny, px_maxy)))
                cane_flat.append(bool(cane_mask_2d[r, c]))
                
        # Compute exact sub-pixel intersection area
        total_gt_m2, sat_cane_m2, all_cells_inter_m2 = compute_exact_subpixel_intersection_area(
            cell_boxes, cane_flat, poly_utm
        )
        
        sat_detected_inside_acres = sat_cane_m2 / 4046.8564224
        parcel_occupancy_pct = (sat_cane_m2 / max(1.0, total_gt_m2)) * 100.0
        
        # Strict IoU: Intersection / Union
        # Union = Total Parcel Area + any cane outside parcel in this tight bbox
        cane_cells_m2_total = np.sum(cane_mask_2d) * 100.0
        union_m2 = total_gt_m2 + max(0.0, cane_cells_m2_total - sat_cane_m2)
        strict_parcel_iou_pct = (sat_cane_m2 / max(1.0, union_m2)) * 100.0
        
        edge_exposure_pct = compute_boundary_pixel_exposure(poly_utm)
        
        # Mean field spectral metrics inside parcel
        gt_mask_binary = rasterize([(poly_utm, 1)], out_shape=out_shape_10m, transform=win_10m_transform, fill=0, dtype=np.uint8)
        mean_field_ndvi = float(np.nanmean(ndvi[gt_mask_binary == 1])) if np.sum(gt_mask_binary == 1) > 0 else 0.0
        mean_field_ndre = float(np.nanmean(ndre[gt_mask_binary == 1])) if np.sum(gt_mask_binary == 1) > 0 else 0.0
        mean_field_lswi = float(np.nanmean(lswi[gt_mask_binary == 1])) if np.sum(gt_mask_binary == 1) > 0 else 0.0
        
        if mean_field_ndvi < 0.35:
            attr = "NO_VEGETATION_DETECTED (NDVI < 0.35 on 2026-01-23; fallow/harvest/rotation)"
        elif gt_area_acres < 0.60:
            attr = "SUB_ACRE_PIXELIZATION (10m grid edge quantization dominates small parcel boundary)"
        elif parcel_occupancy_pct >= 75.0:
            attr = "HIGH_CANOPY_OCCUPANCY (Strong agreement; minor boundary trimming)"
        elif parcel_occupancy_pct >= 40.0:
            attr = "PARTIAL_CANOPY_OR_COORDINATE_OFFSET (Mixed standing crop or partial plot coverage)"
        else:
            attr = "BELOW_SPECTRAL_THRESHOLD (Vegetated field below sugarcane vigor threshold)"

        rec = {
            "plot_no": pno,
            "farmer_name": farmer,
            "village": village,
            "variety": variety,
            "tile": target_tile,
            "scene_date": target_reader["date"],
            "ground_truth_acres": round(gt_area_acres, 2),
            "sat_detected_inside_acres": round(sat_detected_inside_acres, 2),
            "parcel_cane_occupancy_pct": round(parcel_occupancy_pct, 1),
            "strict_parcel_iou_pct": round(strict_parcel_iou_pct, 1),
            "mean_field_ndvi": round(mean_field_ndvi, 3),
            "mean_field_ndre": round(mean_field_ndre, 3),
            "mean_field_lswi": round(mean_field_lswi, 3),
            "estimated_boundary_pixel_exposure_pct": round(edge_exposure_pct, 1),
            "primary_error_attribution": attr
        }
        results.append(rec)
        print(f"[{i+1:2d}/{n_eval}] Plot #{pno:5s} ({farmer[:20]:20s}) | GT: {gt_area_acres:.2f} ac | Sat: {sat_detected_inside_acres:.2f} ac | Occ: {parcel_occupancy_pct:5.1f}% | IoU: {strict_parcel_iou_pct:5.1f}% | NDVI: {mean_field_ndvi:.3f}")

    df_out = pd.DataFrame(results)
    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    df_out.to_csv(output_csv, index=False)
    print(f"\nSuccessfully wrote validation results to {output_csv}")
    return df_out

if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 88
    run_validation(limit_plots=n)