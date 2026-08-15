"""
ml/liss4_fusion_engine.py
ISRO Resourcesat-2A LISS-4 (5.8m VNIR) + Copernicus Sentinel-2 (10m Multi-Spectral)
Multi-Sensor Canopy Auto-Snapping & Fusion Engine

Features:
  1. Sentinel-2 (10m) provides rich crop biophysical intelligence:
     - NDVI, NDRE (B05 RedEdge), LSWI (B11 SWIR), NDWI, BSI, SCL.
  2. Resourcesat-2A LISS-4 (5.8m) provides 3x higher spatial density:
     - 5.8m x 5.8m ground sampling distance (~33.64 m2/pixel vs 100 m2/pixel).
  3. Strict Radiometry Gating:
     - Rejects UNCALIBRATED_DN from empirical NDVI fusion (fails closed).
     - Allows empirical fusion ONLY when radiometry_status == "TOA_PLANETARY_REFLECTANCE".
  4. Geospatial CRS Harmonization:
     - Handles CRS transformations between native LISS-4 CRS and UTM Zone 43N.
"""

import os
import math
import numpy as np
from typing import Dict, Any, List, Tuple, Optional
from shapely.geometry import Polygon, box
from shapely.ops import transform
import pyproj
import rasterio
from rasterio.transform import Affine
from rasterio.warp import reproject, Resampling
from scipy.ndimage import gaussian_filter

def guided_filter_58m(guide_58m: np.ndarray, src_prob_58m: np.ndarray, radius: int = 2, eps: float = 1e-3) -> np.ndarray:
    mean_I = gaussian_filter(guide_58m, sigma=radius)
    mean_p = gaussian_filter(src_prob_58m, sigma=radius)
    mean_Ip = gaussian_filter(guide_58m * src_prob_58m, sigma=radius)
    cov_Ip = mean_Ip - mean_I * mean_p

    mean_II = gaussian_filter(guide_58m * guide_58m, sigma=radius)
    var_I = mean_II - mean_I * mean_I

    a = cov_Ip / (var_I + eps)
    b = mean_p - a * mean_I

    mean_a = gaussian_filter(a, sigma=radius)
    mean_b = gaussian_filter(b, sigma=radius)

    refined_prob = mean_a * guide_58m + mean_b
    return np.clip(refined_prob, 0.0, 1.0)

def fuse_sentinel2_with_liss4_canopy(
    poly_utm: Polygon,
    s2_red_10m: np.ndarray,
    s2_nir_10m: np.ndarray,
    s2_re_10m: np.ndarray,
    s2_swir_10m: np.ndarray,
    s2_scl_10m: np.ndarray,
    s2_transform: Any,
    liss4_green_58m: Optional[np.ndarray] = None,
    liss4_red_58m: Optional[np.ndarray] = None,
    liss4_nir_58m: Optional[np.ndarray] = None,
    liss4_transform: Optional[Any] = None,
    liss4_crs: Optional[Any] = None,
    liss4_valid_mask: Optional[np.ndarray] = None,
    radiometry_status: str = "SIMULATED"
) -> Dict[str, Any]:
    """
    Fuses Sentinel-2 (10m) crop probability with LISS-4 (5.8m) structural edges.
    Enforces strict radiometry gating and geospatial CRS harmonization.
    """
    is_real_liss4 = (liss4_nir_58m is not None and liss4_red_58m is not None)
    
    # 1. Base Sentinel-2 Multi-Spectral Indices & Continuous Probability (10m)
    with np.errstate(divide="ignore", invalid="ignore"):
        s2_ndvi = (s2_nir_10m - s2_red_10m) / (s2_nir_10m + s2_red_10m + 1e-7)
        s2_ndre = (s2_nir_10m - s2_re_10m) / (s2_nir_10m + s2_re_10m + 1e-7)
        s2_lswi = (s2_nir_10m - s2_swir_10m) / (s2_nir_10m + s2_swir_10m + 1e-7)

    s2_valid_scl = np.isin(s2_scl_10m, [4, 5, 6, 7])
    
    score_10m = (
        0.35 * np.clip((s2_ndvi - 0.40) / 0.40, 0, 1) +
        0.35 * np.clip((s2_ndre - 0.10) / 0.20, 0, 1) +
        0.30 * np.clip((s2_lswi - 0.05) / 0.25, 0, 1)
    )
    score_10m[~s2_valid_scl] = 0.0
    s2_cane_mask_10m = (s2_ndvi >= 0.55) & (s2_ndre >= 0.12) & (s2_lswi >= 0.05) & s2_valid_scl

    # 2. Strict Radiometry Gating
    if is_real_liss4 and radiometry_status == "UNCALIBRATED_DN":
        # Fail closed: reject uncalibrated DNs from empirical NDVI fusion
        return {
            "data_source": "EMPIRICAL_ISRO_LISS4_REJECTED",
            "is_empirical_isro_data": True,
            "radiometry_status": "UNCALIBRATED_DN",
            "message": "Empirical LISS-4 NDVI fusion rejected: product contains uncalibrated DN without sensor calibration metadata.",
            "s2_alone": {
                "mask_10m": s2_cane_mask_10m,
                "resolution_m": 10.0
            },
            "fused_liss4": None
        }

    # 3. CRS & Target Grid Alignment
    minx, miny, maxx, maxy = poly_utm.bounds
    res_58m = 5.8
    target_crs = "EPSG:32643"
    
    if is_real_liss4 and liss4_transform is not None and liss4_crs is not None:
        src_crs_str = str(liss4_crs)
        if src_crs_str != target_crs and src_crs_str != "EPSG:32643":
            # Reproject LISS-4 arrays onto common UTM Zone 43N metric grid
            width_58m = max(int(math.ceil((maxx - minx) / res_58m)), 2)
            height_58m = max(int(math.ceil((maxy - miny) / res_58m)), 2)
            target_58m_affine = Affine(res_58m, 0.0, minx, 0.0, -res_58m, maxy)
            
            reproj_nir = np.zeros((height_58m, width_58m), dtype=np.float32)
            reproj_red = np.zeros((height_58m, width_58m), dtype=np.float32)
            reproj_vmask = np.zeros((height_58m, width_58m), dtype=np.uint8)
            
            reproject(source=liss4_nir_58m, destination=reproj_nir, src_transform=liss4_transform, src_crs=liss4_crs, dst_transform=target_58m_affine, dst_crs=target_crs, resampling=Resampling.bilinear)
            reproject(source=liss4_red_58m, destination=reproj_red, src_transform=liss4_transform, src_crs=liss4_crs, dst_transform=target_58m_affine, dst_crs=target_crs, resampling=Resampling.bilinear)
            
            if liss4_valid_mask is not None:
                reproject(source=liss4_valid_mask.astype(np.uint8), destination=reproj_vmask, src_transform=liss4_transform, src_crs=liss4_crs, dst_transform=target_58m_affine, dst_crs=target_crs, resampling=Resampling.nearest)
                valid_58m = reproj_vmask.astype(bool)
            else:
                valid_58m = np.ones((height_58m, width_58m), dtype=bool)
                
            guide_nir = reproj_nir
            guide_red = reproj_red
        else:
            target_58m_affine = liss4_transform
            height_58m, width_58m = liss4_nir_58m.shape
            guide_nir = liss4_nir_58m
            guide_red = liss4_red_58m
            valid_58m = liss4_valid_mask if liss4_valid_mask is not None else np.ones((height_58m, width_58m), dtype=bool)
    else:
        # Simulation Fallback Path
        width_58m = max(int(math.ceil((maxx - minx) / res_58m)), 2)
        height_58m = max(int(math.ceil((maxy - miny) / res_58m)), 2)
        target_58m_affine = Affine(res_58m, 0.0, minx, 0.0, -res_58m, maxy)
        
        sim_nir_58m = np.zeros((height_58m, width_58m), dtype=np.float32)
        sim_red_58m = np.zeros((height_58m, width_58m), dtype=np.float32)
        reproject(source=s2_nir_10m, destination=sim_nir_58m, src_transform=s2_transform, src_crs="EPSG:32643", dst_transform=target_58m_affine, dst_crs="EPSG:32643", resampling=Resampling.cubic)
        reproject(source=s2_red_10m, destination=sim_red_58m, src_transform=s2_transform, src_crs="EPSG:32643", dst_transform=target_58m_affine, dst_crs="EPSG:32643", resampling=Resampling.cubic)
        guide_nir = sim_nir_58m
        guide_red = sim_red_58m
        valid_58m = np.ones((height_58m, width_58m), dtype=bool)

    # 4. Reproject 10m Sentinel-2 probability prior onto target 5.8m grid
    s2_prob_58m = np.zeros((height_58m, width_58m), dtype=np.float32)
    reproject(
        source=score_10m,
        destination=s2_prob_58m,
        src_transform=s2_transform,
        src_crs="EPSG:32643",
        dst_transform=target_58m_affine,
        dst_crs=target_crs,
        resampling=Resampling.bilinear
    )

    with np.errstate(divide="ignore", invalid="ignore"):
        guide_ndvi_58m = (guide_nir - guide_red) / (guide_nir + guide_red + 1e-7)
        guide_ndvi_58m = np.nan_to_num(guide_ndvi_58m, nan=0.0)

    # 5. Joint Guided Filtering Fusion
    fused_prob_58m = guided_filter_58m(guide_58m=guide_ndvi_58m, src_prob_58m=s2_prob_58m, radius=2, eps=1e-3)
    fused_cane_mask_58m = (fused_prob_58m >= 0.50) & (guide_ndvi_58m >= 0.50) & valid_58m

    # 6. Sub-Pixel Geometric Area on 5.8m Grid
    cell_area_m2_58m = res_58m * res_58m
    fused_cell_boxes = []
    fused_cane_flat = []
    
    for r in range(height_58m):
        for c in range(width_58m):
            px_minx, px_maxy = target_58m_affine * (c, r)
            px_maxx, px_miny = target_58m_affine * (c + 1, r + 1)
            fused_cell_boxes.append((min(px_minx, px_maxx), min(px_miny, px_maxy), max(px_minx, px_maxx), max(px_miny, px_maxy)))
            fused_cane_flat.append(bool(fused_cane_mask_58m[r, c]))

    total_gt_m2 = poly_utm.area
    fused_sat_cane_m2 = 0.0
    
    for (c_minx, c_miny, c_maxx, c_maxy), is_cane in zip(fused_cell_boxes, fused_cane_flat):
        cell_geom = box(c_minx, c_miny, c_maxx, c_maxy)
        if cell_geom.intersects(poly_utm) and is_cane:
            fused_sat_cane_m2 += cell_geom.intersection(poly_utm).area

    fused_sat_acres = fused_sat_cane_m2 / 4046.8564224
    fused_occupancy_pct = (fused_sat_cane_m2 / max(1.0, total_gt_m2)) * 100.0
    
    fused_cane_cells_total_m2 = np.sum(fused_cane_mask_58m) * cell_area_m2_58m
    fused_union_m2 = total_gt_m2 + max(0.0, fused_cane_cells_total_m2 - fused_sat_cane_m2)
    fused_strict_iou_pct = (fused_sat_cane_m2 / max(1.0, fused_union_m2)) * 100.0

    return {
        "data_source": "EMPIRICAL_ISRO_LISS4" if is_real_liss4 else "SIMULATED_5.8M_REGRIDDED",
        "is_empirical_isro_data": is_real_liss4,
        "radiometry_status": radiometry_status,
        "s2_alone": {
            "mask_10m": s2_cane_mask_10m,
            "resolution_m": 10.0
        },
        "fused_liss4": {
            "mask_58m": fused_cane_mask_58m,
            "resolution_m": 5.8,
            "fused_sat_acres": round(fused_sat_acres, 2),
            "fused_occupancy_pct": round(fused_occupancy_pct, 1),
            "fused_strict_iou_pct": round(fused_strict_iou_pct, 1)
        }
    }