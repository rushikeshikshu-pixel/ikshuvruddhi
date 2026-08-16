"""
ml/sentinel_timeseries_harvester.py
High-Performance Multi-Temporal Sentinel-2 Harvester & In-Memory Sub-Region Extractor
Features:
  - Exact Per-Tile Geographic Intersection Windowing (Loads in ~0.5s per scene)
  - In-Memory Polygon Masking & Index Computation (Zero repetitive network I/O)
  - Direct Pixel-Measured Canopy Occupancy Fractions (NDVI >= 0.50)
  - Multi-Criteria Quality Ranking via rank_scene_quality()
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
      - Temporal Recency / Proximity to Target Reference Date
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

class TileSceneMemoryCache:
    """
    Loads and caches a continuous sub-region encompassing all parcels for a single Sentinel-2 scene.
    Enables instant in-memory extraction for hundreds of parcels with zero repetitive network round-trips.
    """
    def __init__(self, scene_dict: Dict[str, Any], all_parcels_bounds_utm: Tuple[float, float, float, float]):
        self.scene_id = scene_dict["id"]
        self.date = scene_dict["properties"]["datetime"][:10]
        self.cloud_pct = scene_dict["properties"]["eo:cloud_cover"]
        self.assets = scene_dict["assets"]
        self.req_minx, self.req_miny, self.req_maxx, self.req_maxy = all_parcels_bounds_utm
        self.is_valid = False

        self._load_memory_arrays()

    def _load_memory_arrays(self):
        try:
            with rasterio.open(self.assets["red"]["href"]) as red_src:
                self.crs = red_src.crs
                self.transform = red_src.transform
                tb = red_src.bounds

                # Intersect requested bounds with scene actual bounds
                minx = max(self.req_minx, tb.left + 100.0)
                miny = max(self.req_miny, tb.bottom + 100.0)
                maxx = min(self.req_maxx, tb.right - 100.0)
                maxy = min(self.req_maxy, tb.top - 100.0)

                if minx >= maxx or miny >= maxy:
                    return # No intersection with this tile

                self.minx, self.miny, self.maxx, self.maxy = minx, miny, maxx, maxy
                win_10m = from_bounds(minx, miny, maxx, maxy, transform=self.transform)
                self.red_arr = red_src.read(1, window=win_10m).astype(np.float32)
                self.win_transform = red_src.window_transform(win_10m)

            with rasterio.open(self.assets["nir"]["href"]) as nir_src:
                win_10m = from_bounds(self.minx, self.miny, self.maxx, self.maxy, transform=nir_src.transform)
                self.nir_arr = nir_src.read(1, window=win_10m).astype(np.float32)

            with rasterio.open(self.assets["scl"]["href"]) as scl_src:
                win_scl = from_bounds(self.minx, self.miny, self.maxx, self.maxy, transform=scl_src.transform)
                scl_raw = scl_src.read(1, window=win_scl)
                self.scl_arr = np.zeros_like(self.red_arr, dtype=np.uint8)
                reproject(
                    source=scl_raw,
                    destination=self.scl_arr,
                    src_transform=scl_src.window_transform(win_scl),
                    src_crs=scl_src.crs,
                    dst_transform=self.win_transform,
                    dst_crs=self.crs,
                    resampling=Resampling.nearest
                )

            self.is_valid = True
        except Exception as e:
            self.is_valid = False

    def extract_parcel(self, poly_wgs84: Polygon) -> Dict[str, Any]:
        """
        Fast in-memory parcel extraction via direct NumPy sub-slicing and geometric masking.
        """
        if not self.is_valid:
            return {"ndvi": None, "canopy_fraction_pct": 0.0, "usability_pct": 0.0}

        to_raster = pyproj.Transformer.from_crs("EPSG:4326", self.crs, always_xy=True).transform
        poly_utm = transform(to_raster, poly_wgs84)
        p_minx, p_miny, p_maxx, p_maxy = poly_utm.bounds

        # Check bounds
        if not (self.minx <= p_minx and p_maxx <= self.maxx and self.miny <= p_miny and p_maxy <= self.maxy):
            return {"ndvi": None, "canopy_fraction_pct": 0.0, "usability_pct": 0.0}

        try:
            mask = geometry_mask(
                [poly_utm],
                out_shape=self.red_arr.shape,
                transform=self.win_transform,
                invert=True
            )
        except Exception:
            return {"ndvi": None, "canopy_fraction_pct": 0.0, "usability_pct": 0.0}

        parcel_red = self.red_arr[mask]
        parcel_nir = self.nir_arr[mask]
        parcel_scl = self.scl_arr[mask]

        total_px = len(parcel_red)
        if total_px == 0:
            return {"ndvi": None, "canopy_fraction_pct": 0.0, "usability_pct": 0.0}

        valid_mask = np.isin(parcel_scl, [4, 5]) # Vegetation & Bare Soil
        valid_cnt = int(np.sum(valid_mask))
        usability_pct = round((valid_cnt / float(total_px)) * 100.0, 1)

        if valid_cnt < 3 or usability_pct < 50.0:
            return {"ndvi": None, "canopy_fraction_pct": 0.0, "usability_pct": usability_pct}

        v_red = parcel_red[valid_mask]
        v_nir = parcel_nir[valid_mask]

        denom = v_nir + v_red
        valid_denom = denom > 1e-4
        if np.sum(valid_denom) < 3:
            return {"ndvi": None, "canopy_fraction_pct": 0.0, "usability_pct": usability_pct}

        ndvis = (v_nir[valid_denom] - v_red[valid_denom]) / denom[valid_denom]
        mean_ndvi = round(float(np.mean(ndvis)), 3)
        canopy_fraction_pct = round(float(np.sum(ndvis >= 0.50)) / float(len(ndvis)) * 100.0, 1)

        return {
            "ndvi": mean_ndvi,
            "canopy_fraction_pct": canopy_fraction_pct,
            "usability_pct": usability_pct,
            "date": self.date,
            "scene_id": self.scene_id
        }