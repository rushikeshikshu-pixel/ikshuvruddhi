"""
validation/fuse_liss4_experiment.py
Multi-Resolution Feasibility Benchmark: Baseline Sentinel-2 (10m) vs. 5.8m Guided Fusion
Evaluated across the 36 High-NDVI / Strong-Vegetation Parcels (NDVI >= 0.55).

Supports both:
  1. Real ISRO Resourcesat-2A LISS-4 Product Ingestion (ZIP, HDF5, GeoTIFF)
  2. Algorithmic Guided Bilateral Simulation Fallback (explicitly annotated in metadata/output)
"""

import os
import sys
import json
import math
import argparse
import requests
import numpy as np
import pandas as pd
from shapely.geometry import Polygon, box
from shapely.ops import transform
import pyproj
import rasterio
from rasterio.windows import from_bounds
from rasterio.warp import reproject, Resampling
from rasterio.transform import Affine

sys.stdout.reconfigure(encoding='utf-8')

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from ml.canopy_classifier import compute_spectral_indices, classify_sugarcane_raster
from ml.liss4_fusion_engine import fuse_sentinel2_with_liss4_canopy
from ml.bhoonidhi_client import BhoonidhiClient, crop_and_reproject_liss4_product
from validation.metrics import compute_exact_subpixel_intersection_area, compute_boundary_pixel_exposure

wgs84_to_utm43n = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:32643", always_xy=True).transform

def run_fusion_experiment(output_csv="data/output/liss4_sentinel2_fusion_comparison.csv", liss4_product_path=None):
    is_real_liss4 = (liss4_product_path is not None and os.path.exists(liss4_product_path))
    data_source_mode = "EMPIRICAL_ISRO_LISS4" if is_real_liss4 else "ALGORITHMIC_SIMULATION_FALLBACK"

    print("==================================================================")
    print(" RESOURCESAT-2A LISS-4 (5.8m) + SENTINEL-2 (10m) FUSION EXPERIMENT")
    print(f" Data Source Mode: {data_source_mode}")
    print(" Target Cohort   : 36 High-NDVI / Strong-Vegetation Parcels (NDVI >= 0.55)")
    if not is_real_liss4:
        print(" Note: Running in algorithmic simulation mode (real Bhoonidhi package not supplied).")
    print("==================================================================")

    df_emp = pd.read_csv("data/output/refined_empirical_sentinel_analysis_88plots.csv")
    df_high_ndvi = df_emp[df_emp["mean_field_ndvi"] >= 0.55].copy()
    print(f"Loaded {len(df_high_ndvi)} high-NDVI parcels for benchmarking.")

    src_csv = os.path.join(REPO_ROOT, "data", "sugarcane_adsali_season_2627.csv")
    df_raw = pd.read_csv(src_csv)
    raw_map = {str(r["Plot No"]).strip(): r for _, r in df_raw.iterrows()}

    # Sentinel-2 COG Query
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

    for idx, erow in df_high_ndvi.iterrows():
        pno = str(erow["plot_no"]).strip()
        if pno not in raw_map:
            continue
        r = raw_map[pno]
        
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

        win_10m = from_bounds(minx, miny, maxx, maxy, src_red.transform)
        win_10m_transform = rasterio.windows.transform(win_10m, src_red.transform)

        blue_10m = src_blue.read(1, window=win_10m).astype(np.float32) / 10000.0
        green_10m = src_green.read(1, window=win_10m).astype(np.float32) / 10000.0
        red_10m = src_red.read(1, window=win_10m).astype(np.float32) / 10000.0
        nir_10m = src_nir.read(1, window=win_10m).astype(np.float32) / 10000.0
        out_shape_10m = red_10m.shape

        re_10m = np.zeros(out_shape_10m, dtype=np.float32)
        reproject(source=rasterio.band(src_re, 1), destination=re_10m, src_transform=src_re.transform, src_crs=src_re.crs, dst_transform=win_10m_transform, dst_crs=src_red.crs, resampling=Resampling.bilinear)
        re_10m = re_10m / 10000.0

        swir_10m = np.zeros(out_shape_10m, dtype=np.float32)
        reproject(source=rasterio.band(src_swir, 1), destination=swir_10m, src_transform=src_swir.transform, src_crs=src_swir.crs, dst_transform=win_10m_transform, dst_crs=src_red.crs, resampling=Resampling.bilinear)
        swir_10m = swir_10m / 10000.0

        scl_10m = np.zeros(out_shape_10m, dtype=np.uint8)
        reproject(source=rasterio.band(src_scl, 1), destination=scl_10m, src_transform=src_scl.transform, src_crs=src_scl.crs, dst_transform=win_10m_transform, dst_crs=src_red.crs, resampling=Resampling.nearest)

        # Baseline A: Empirical Sentinel-2 (10m)
        indices_10m = compute_spectral_indices(blue_10m, green_10m, red_10m, re_10m, nir_10m, swir_10m)
        s2_cane_mask = classify_sugarcane_raster(indices_10m["ndvi"], indices_10m["ndre"], indices_10m["lswi"], scl_10m, indices_10m["ndwi"], indices_10m["bsi"])

        cell_boxes_10m = []
        cane_flat_10m = []
        rows_10m, cols_10m = out_shape_10m
        for r_idx in range(rows_10m):
            for c_idx in range(cols_10m):
                px_minx, px_maxy = win_10m_transform * (c_idx, r_idx)
                px_maxx, px_miny = win_10m_transform * (c_idx + 1, r_idx + 1)
                cell_boxes_10m.append((min(px_minx, px_maxx), min(px_miny, px_maxy), max(px_minx, px_maxx), max(px_miny, px_maxy)))
                cane_flat_10m.append(bool(s2_cane_mask[r_idx, c_idx]))

        tot_ref_m2, s2_cane_m2, _ = compute_exact_subpixel_intersection_area(cell_boxes_10m, cane_flat_10m, poly_utm)
        s2_acres = s2_cane_m2 / 4046.8564224
        s2_occ_pct = (s2_cane_m2 / max(1.0, tot_ref_m2)) * 100.0
        s2_total_cane_m2 = np.sum(s2_cane_mask) * 100.0
        s2_union_m2 = tot_ref_m2 + max(0.0, s2_total_cane_m2 - s2_cane_m2)
        s2_strict_iou = (s2_cane_m2 / max(1.0, s2_union_m2)) * 100.0
        s2_area_error_pct = abs(s2_acres - ref_area_acres) / max(0.01, ref_area_acres) * 100.0

        # Method B: 5.8m Multi-Sensor Guided Fusion (Real or Simulated)
        liss4_green = None
        liss4_red = None
        liss4_nir = None
        liss4_trans = None
        
        if is_real_liss4:
            crop_res = crop_and_reproject_liss4_product(liss4_product_path, poly_wgs)
            if crop_res:
                liss4_green = crop_res["green_58m_toa"]
                liss4_red   = crop_res["red_58m_toa"]
                liss4_nir   = crop_res["nir_58m_toa"]
                liss4_trans = crop_res["affine_transform"]

        fusion_out = fuse_sentinel2_with_liss4_canopy(
            poly_utm=poly_utm,
            s2_red_10m=red_10m,
            s2_nir_10m=nir_10m,
            s2_re_10m=re_10m,
            s2_swir_10m=swir_10m,
            s2_scl_10m=scl_10m,
            s2_transform=win_10m_transform,
            liss4_green_58m=liss4_green,
            liss4_red_58m=liss4_red,
            liss4_nir_58m=liss4_nir,
            liss4_transform=liss4_trans
        )

        fused_res = fusion_out["fused_liss4"]
        fused_acres = fused_res["fused_sat_acres"]
        fused_occ_pct = fused_res["fused_occupancy_pct"]
        fused_strict_iou = fused_res["fused_strict_iou_pct"]
        fused_area_error_pct = abs(fused_acres - ref_area_acres) / max(0.01, ref_area_acres) * 100.0
        iou_gain = fused_strict_iou - s2_strict_iou

        rec = {
            "plot_no": pno,
            "farmer_name": erow["farmer_name"],
            "village": erow["village"],
            "source_reference_acres": round(ref_area_acres, 2),
            "mean_field_ndvi": erow["mean_field_ndvi"],
            "s2_empirical_detected_acres_10m": round(s2_acres, 2),
            "s2_empirical_occupancy_pct": round(s2_occ_pct, 1),
            "s2_empirical_strict_iou_pct": round(s2_strict_iou, 1),
            "s2_empirical_area_error_pct": round(s2_area_error_pct, 1),
            "fused_detected_acres_58m": round(fused_acres, 2),
            "fused_occupancy_pct": round(fused_occ_pct, 1),
            "fused_strict_iou_pct": round(fused_strict_iou, 1),
            "fused_area_error_pct": round(fused_area_error_pct, 1),
            "iou_delta_pct_points": round(iou_gain, 1),
            "data_source_mode": data_source_mode
        }
        results.append(rec)
        print(f"Plot #{pno:4s} ({erow['farmer_name'][:18]:18s}) | Ref: {ref_area_acres:.2f} ac | Empirical S2: {s2_strict_iou:4.1f}% IoU -> 5.8m Fused: {fused_strict_iou:4.1f}% IoU (Delta: {iou_gain:+4.1f}%)")

    df_comp = pd.DataFrame(results)
    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    df_comp.to_csv(output_csv, index=False)

    print("\n==================================================================")
    print(f" FUSION EXPERIMENT BENCHMARK SUMMARY (N={len(df_comp)} High-NDVI Parcels)")
    print(f" Pipeline Data Source Mode: {data_source_mode}")
    print("==================================================================")
    print(f" Empirical Sentinel-2 (10m)      : Mean IoU = {df_comp['s2_empirical_strict_iou_pct'].mean():.2f}% | Mean Occ = {df_comp['s2_empirical_occupancy_pct'].mean():.2f}% | Area Err = {df_comp['s2_empirical_area_error_pct'].mean():.2f}%")
    print(f" 5.8m Fused Pipeline             : Mean IoU = {df_comp['fused_strict_iou_pct'].mean():.2f}% | Mean Occ = {df_comp['fused_occupancy_pct'].mean():.2f}% | Area Err = {df_comp['fused_area_error_pct'].mean():.2f}%")
    print(f" Net Mean IoU Delta              : {df_comp['iou_delta_pct_points'].mean():+.2f} percentage points")
    print("==================================================================\n")
    return df_comp

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--liss4-product", type=str, default=None, help="Path to genuine Resourcesat-2A LISS-4 product (ZIP, HDF5, or GeoTIFF)")
    args = parser.parse_args()
    run_fusion_experiment(liss4_product_path=args.liss4_product)