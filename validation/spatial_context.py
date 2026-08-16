"""
validation/spatial_context.py
Concentric Spatial Context Ring Analyzer & Neighborhood Discrepancy Diagnostics
Extracts multi-ring context buffers (25m, 50m, 100m, 250m) to distinguish:
  1. BOUNDARY_OR_POLYGON_SHIFT_SUSPECT (High canopy immediately outside polygon in 25-50m)
  2. FIELD_SPECIFIC_DISCREPANCY_CLUSTER_ACTIVE (Low inside, but active standing cane parcel within 150m)
  3. REGIONAL_FALLOW_OR_DRY_LOCALITY (Low inside and low across 100-250m neighborhood)
"""

import math
from typing import Dict, Any, List, Tuple, Optional
import numpy as np
from shapely.geometry import Polygon, MultiPolygon
from shapely.ops import transform
import pyproj
from rasterio.features import geometry_mask
import rasterio

# EPSG:4326 to UTM Zone 43N (EPSG:32643) for meter-accurate buffers
WGS84_TO_UTM43N = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:32643", always_xy=True).transform
UTM43N_TO_WGS84 = pyproj.Transformer.from_crs("EPSG:32643", "EPSG:4326", always_xy=True).transform

def build_concentric_rings(
    polygon_wgs84: Polygon,
    ring_distances_m: List[float] = [25.0, 50.0, 100.0, 250.0]
) -> Dict[str, Polygon]:
    """
    Creates disjoint concentric buffer rings around a WGS84 polygon.
    Returns dict mapping 'ring_25m', 'ring_50m', 'ring_100m', 'ring_250m' to disjoint WGS84 geometries.
    """
    # Transform to UTM 43N meters
    poly_utm = transform(WGS84_TO_UTM43N, polygon_wgs84)
    if not poly_utm.is_valid:
        poly_utm = poly_utm.buffer(0)

    rings_wgs84 = {}
    prev_geom_utm = poly_utm

    for dist in ring_distances_m:
        buf_utm = poly_utm.buffer(dist)
        # Disjoint ring is current buffer minus previous buffer
        ring_geom_utm = buf_utm.difference(prev_geom_utm)
        if not ring_geom_utm.is_valid:
            ring_geom_utm = ring_geom_utm.buffer(0)

        ring_wgs84 = transform(UTM43N_TO_WGS84, ring_geom_utm)
        rings_wgs84[f"ring_{int(dist)}m"] = ring_wgs84
        prev_geom_utm = buf_utm

    return rings_wgs84

def extract_ring_raster_stats(
    ring_geom_wgs84: Any,
    red_raster: np.ndarray,
    nir_raster: np.ndarray,
    scl_raster: np.ndarray,
    affine_transform: rasterio.Affine,
    raster_crs: Any,
    min_usability_scl: Tuple[int, ...] = (4, 5) # Vegetation & Bare soil
) -> Dict[str, Optional[float]]:
    """
    Extracts mean NDVI, usable pixel coverage, and canopy fraction inside a ring geometry.
    """
    if ring_geom_wgs84 is None or ring_geom_wgs84.is_empty:
        return {"mean_ndvi": None, "canopy_pct": None, "usable_pixels": 0}

    # Transform geometry to raster CRS if needed
    if str(raster_crs) not in ["EPSG:4326", "WGS84", "+init=epsg:4326"]:
        to_raster_crs = pyproj.Transformer.from_crs("EPSG:4326", raster_crs, always_xy=True).transform
        geom_in_raster = transform(to_raster_crs, ring_geom_wgs84)
    else:
        geom_in_raster = ring_geom_wgs84

    try:
        # Create boolean mask (False inside geometry, True outside)
        mask = geometry_mask(
            [geom_in_raster],
            out_shape=red_raster.shape,
            transform=affine_transform,
            invert=True
        )
    except Exception:
        return {"mean_ndvi": None, "canopy_pct": None, "usable_pixels": 0}

    # Extract pixels inside ring
    ring_red = red_raster[mask].astype(np.float64)
    ring_nir = nir_raster[mask].astype(np.float64)
    ring_scl = scl_raster[mask]

    total_ring_pixels = len(ring_red)
    if total_ring_pixels == 0:
        return {"mean_ndvi": None, "canopy_pct": None, "usable_pixels": 0}

    # Filter usable pixels (SCL 4 or 5)
    valid_scl_mask = np.isin(ring_scl, min_usability_scl)
    valid_count = int(np.sum(valid_scl_mask))
    if valid_count < 3:
        return {"mean_ndvi": None, "canopy_pct": None, "usable_pixels": valid_count}

    valid_red = ring_red[valid_scl_mask]
    valid_nir = ring_nir[valid_scl_mask]

    denom = valid_nir + valid_red
    valid_denom_mask = denom > 1e-4
    if np.sum(valid_denom_mask) < 3:
        return {"mean_ndvi": None, "canopy_pct": None, "usable_pixels": valid_count}

    v_red = valid_red[valid_denom_mask]
    v_nir = valid_nir[valid_denom_mask]
    ndvis = (v_nir - v_red) / (v_nir + v_red)

    # Canopy pixels: NDVI >= 0.50
    canopy_pixels = np.sum(ndvis >= 0.50)
    canopy_pct = round((canopy_pixels / float(len(ndvis))) * 100.0, 1)
    mean_ndvi = round(float(np.mean(ndvis)), 3)

    return {
        "mean_ndvi": mean_ndvi,
        "canopy_pct": canopy_pct,
        "usable_pixels": valid_count
    }

def diagnose_spatial_discrepancy(
    inside_canopy_occupancy_pct: float,
    ring_stats: Dict[str, Dict[str, Optional[float]]],
    nearest_high_canopy_dist_m: Optional[float]
) -> Dict[str, Any]:
    """
    Diagnoses the spatial cause of low canopy occupancy.
    
    Returns:
      - spatial_discrepancy_stratum
      - diagnostic_rationale
    """
    can_in = inside_canopy_occupancy_pct
    r25_can = ring_stats.get("ring_25m", {}).get("canopy_pct") or 0.0
    r50_can = ring_stats.get("ring_50m", {}).get("canopy_pct") or 0.0
    r100_can = ring_stats.get("ring_100m", {}).get("canopy_pct") or 0.0
    r250_can = ring_stats.get("ring_250m", {}).get("canopy_pct") or 0.0

    # 1. Congruent High Canopy
    if can_in >= 50.0:
        return {
            "spatial_discrepancy_stratum": "CONGRUENT_STANDING_CANOPY",
            "diagnostic_rationale": f"High standing canopy inside registered polygon ({can_in:.1f}%)."
        }

    # 2. Partial / Intermediate Canopy
    if can_in >= 20.0:
        return {
            "spatial_discrepancy_stratum": "PARTIAL_OR_MIXED_CANOPY",
            "diagnostic_rationale": f"Moderate canopy inside polygon ({can_in:.1f}%)."
        }

    # LOW CANOPY INSIDE POLYGON (< 20%): Diagnose neighborhood

    # Case A: Boundary / Polygon Shift Suspect
    # High canopy immediately outside in the 25m or 50m ring (>= 45%)
    if r25_can >= 45.0 or r50_can >= 45.0:
        return {
            "spatial_discrepancy_stratum": "BOUNDARY_OR_POLYGON_SHIFT_SUSPECT",
            "diagnostic_rationale": (
                f"Low inside ({can_in:.1f}%), but strong standing canopy immediately outside "
                f"(25m ring: {r25_can}%, 50m ring: {r50_can}%). Likely GPS coordinate shift or clipped boundary."
            )
        }

    # Case B: Field-Specific Harvest in Active Cluster
    # Known high-canopy parcel exists within 150m
    if nearest_high_canopy_dist_m is not None and nearest_high_canopy_dist_m <= 150.0:
        return {
            "spatial_discrepancy_stratum": "FIELD_SPECIFIC_DISCREPANCY_CLUSTER_ACTIVE",
            "diagnostic_rationale": (
                f"Low inside ({can_in:.1f}%), but confirmed standing cane parcel exists "
                f"{nearest_high_canopy_dist_m:.0f}m away. Field-specific harvest/fallow, not regional absence."
            )
        }

    # Case C: Regional Fallow or Dry Locality
    # Low canopy consistently across the 100m-250m surroundings (< 15%)
    if r100_can < 15.0 and r250_can < 15.0:
        return {
            "spatial_discrepancy_stratum": "REGIONAL_FALLOW_OR_DRY_LOCALITY",
            "diagnostic_rationale": (
                f"Low inside ({can_in:.1f}%) and low canopy throughout 100-250m surroundings "
                f"(100m ring: {r100_can}%, 250m ring: {r250_can}%). Broad fallow/unirrigated sector."
            )
        }

    # Case D: Mixed / Heterogeneous Neighborhood
    return {
        "spatial_discrepancy_stratum": "ISOLATED_LOW_CANOPY_DISCREPANCY",
        "diagnostic_rationale": (
            f"Low inside ({can_in:.1f}%) with mixed neighborhood canopy "
            f"(25m: {r25_can}%, 100m: {r100_can}%, 250m: {r250_can}%)."
        )
    }