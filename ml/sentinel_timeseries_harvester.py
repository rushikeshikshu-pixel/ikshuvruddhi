"""
ml/sentinel_timeseries_harvester.py
Multi-Temporal Sentinel-2 L2A Time-Series Harvester & Quality-Ranked Scene Selector
Fetches, ranks, and streams real polygon-masked pixel observations across 12-18 month multi-season windows.
"""

import os
import requests
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional
import numpy as np
from shapely.geometry import Polygon
from shapely.ops import transform
import pyproj
import rasterio
from rasterio.windows import from_bounds
from rasterio.features import geometry_mask
from rasterio.warp import reproject, Resampling

STAC_ENDPOINT = "https://earth-search.aws.element84.com/v1/search"

def rank_scene_quality(
    parcel_valid_coverage_pct: float,
    cloud_cover_pct: float,
    acquisition_datetime: str,
    target_reference_datetime: Optional[str] = None,
    usability_weight: float = 0.60,
    cloud_weight: float = 0.20,
    recency_weight: float = 0.20
) -> float:
    """
    Ranks observation quality using multi-criteria weighted scoring:
      - Parcel Valid Usability (0-100)
      - Scene Cloud Cleanliness (100 - cloud_cover)
      - Temporal Recency / Proximity to Target Date
    """
    usability_score = min(100.0, max(0.0, parcel_valid_coverage_pct))
    cloud_score = max(0.0, 100.0 - (cloud_cover_pct * 2.0))

    if target_reference_datetime:
        target_dt = datetime.strptime(target_reference_datetime[:10], "%Y-%m-%d")
    else:
        target_dt = datetime.utcnow()
        
    try:
        scene_dt = datetime.strptime(acquisition_datetime[:10], "%Y-%m-%d")
        days_diff = abs((target_dt - scene_dt).days)
        recency_score = max(0.0, 100.0 - (days_diff * 1.5))
    except Exception:
        recency_score = 50.0

    total_score = (
        usability_score * usability_weight +
        cloud_score * cloud_weight +
        recency_score * recency_weight
    )
    return round(total_score, 2)

def extract_parcel_spectral_observation(
    poly_wgs84: Polygon,
    red_reader: rasterio.io.DatasetReader,
    nir_reader: rasterio.io.DatasetReader,
    scl_reader: rasterio.io.DatasetReader,
    re_reader: Optional[rasterio.io.DatasetReader] = None,
    swir_reader: Optional[rasterio.io.DatasetReader] = None,
    min_usability_scl: Tuple[int, ...] = (4, 5) # Vegetation & Bare Soil
) -> Dict[str, Any]:
    """
    Extracts exact polygon-masked spectral indices (NDVI, NDRE, LSWI) and usable pixel fraction
    from remote COG readers for a single date.
    """
    if poly_wgs84 is None or poly_wgs84.is_empty:
        return {"ndvi": None, "ndre": None, "lswi": None, "usability_pct": 0.0, "usable_pixels": 0}

    # Transform to raster CRS
    if str(red_reader.crs) not in ["EPSG:4326", "WGS84", "+init=epsg:4326"]:
        to_raster = pyproj.Transformer.from_crs("EPSG:4326", red_reader.crs, always_xy=True).transform
        poly_raster = transform(to_raster, poly_wgs84)
    else:
        poly_raster = poly_wgs84

    minx, miny, maxx, maxy = poly_raster.bounds
    tb = red_reader.bounds
    if not (tb.left <= minx and maxx <= tb.right and tb.bottom <= miny and maxy <= tb.top):
        return {"ndvi": None, "ndre": None, "lswi": None, "usability_pct": 0.0, "usable_pixels": 0}

    # Read 10m window
    win_10m = from_bounds(minx, miny, maxx, maxy, transform=red_reader.transform)
    win_trans_10m = red_reader.window_transform(win_10m)

    red_arr = red_reader.read(1, window=win_10m)
    nir_arr = nir_reader.read(1, window=win_10m)

    if red_arr.size == 0 or nir_arr.size == 0:
        return {"ndvi": None, "ndre": None, "lswi": None, "usability_pct": 0.0, "usable_pixels": 0}

    # Read and reproject SCL (20m -> 10m)
    win_scl = from_bounds(minx, miny, maxx, maxy, transform=scl_reader.transform)
    scl_raw = scl_reader.read(1, window=win_scl)
    scl_10m = np.zeros_like(red_arr, dtype=np.uint8)

    reproject(
        source=scl_raw,
        destination=scl_10m,
        src_transform=scl_reader.window_transform(win_scl),
        src_crs=scl_reader.crs,
        dst_transform=win_trans_10m,
        dst_crs=red_reader.crs,
        resampling=Resampling.nearest
    )

    # Apply polygon geometry mask
    try:
        mask = geometry_mask(
            [poly_raster],
            out_shape=red_arr.shape,
            transform=win_trans_10m,
            invert=True
        )
    except Exception:
        return {"ndvi": None, "ndre": None, "lswi": None, "usability_pct": 0.0, "usable_pixels": 0}

    parcel_red = red_arr[mask].astype(np.float64)
    parcel_nir = nir_arr[mask].astype(np.float64)
    parcel_scl = scl_10m[mask]

    total_pixels = len(parcel_red)
    if total_pixels == 0:
        return {"ndvi": None, "ndre": None, "lswi": None, "usability_pct": 0.0, "usable_pixels": 0}

    valid_mask = np.isin(parcel_scl, min_usability_scl)
    valid_count = int(np.sum(valid_mask))
    usability_pct = round((valid_count / float(total_pixels)) * 100.0, 1)

    if valid_count < 3 or usability_pct < 50.0:
        return {"ndvi": None, "ndre": None, "lswi": None, "usability_pct": usability_pct, "usable_pixels": valid_count}

    v_red = parcel_red[valid_mask]
    v_nir = parcel_nir[valid_mask]

    denom_ndvi = v_nir + v_red
    valid_denom = denom_ndvi > 1e-4
    if np.sum(valid_denom) < 3:
        return {"ndvi": None, "ndre": None, "lswi": None, "usability_pct": usability_pct, "usable_pixels": valid_count}

    ndvis = (v_nir[valid_denom] - v_red[valid_denom]) / denom_ndvi[valid_denom]
    mean_ndvi = round(float(np.mean(ndvis)), 3)

    # NDRE & LSWI optional reads if readers supplied
    mean_ndre = None
    mean_lswi = None

    if re_reader is not None:
        try:
            win_re = from_bounds(minx, miny, maxx, maxy, transform=re_reader.transform)
            re_raw = re_reader.read(1, window=win_re)
            re_10m = np.zeros_like(red_arr, dtype=np.float64)
            reproject(
                source=re_raw.astype(np.float64),
                destination=re_10m,
                src_transform=re_reader.window_transform(win_re),
                src_crs=re_reader.crs,
                dst_transform=win_trans_10m,
                dst_crs=red_reader.crs,
                resampling=Resampling.bilinear
            )
            v_re = re_10m[mask][valid_mask][valid_denom]
            denom_ndre = v_nir[valid_denom] + v_re
            ndres = (v_nir[valid_denom] - v_re) / np.maximum(1e-4, denom_ndre)
            mean_ndre = round(float(np.mean(ndres)), 3)
        except Exception:
            pass

    if swir_reader is not None:
        try:
            win_swir = from_bounds(minx, miny, maxx, maxy, transform=swir_reader.transform)
            swir_raw = swir_reader.read(1, window=win_swir)
            swir_10m = np.zeros_like(red_arr, dtype=np.float64)
            reproject(
                source=swir_raw.astype(np.float64),
                destination=swir_10m,
                src_transform=swir_reader.window_transform(win_swir),
                src_crs=swir_reader.crs,
                dst_transform=win_trans_10m,
                dst_crs=red_reader.crs,
                resampling=Resampling.bilinear
            )
            v_swir = swir_10m[mask][valid_mask][valid_denom]
            denom_lswi = v_nir[valid_denom] + v_swir
            lswis = (v_nir[valid_denom] - v_swir) / np.maximum(1e-4, denom_lswi)
            mean_lswi = round(float(np.mean(lswis)), 3)
        except Exception:
            pass

    return {
        "ndvi": mean_ndvi,
        "ndre": mean_ndre,
        "lswi": mean_lswi,
        "usability_pct": usability_pct,
        "usable_pixels": valid_count
    }