"""
validation/spatial_context.py
Concentric Spatial Context Ring Analyzer & Neighborhood Discrepancy Diagnostics
Extracts multi-ring context buffers (25m, 50m, 100m, 250m) to distinguish:
  1. BOUNDARY_OR_POLYGON_SHIFT_SUSPECT (High canopy immediately outside polygon in 25-50m)
  2. FIELD_SPECIFIC_DISCREPANCY_CLUSTER_ACTIVE (Low inside, but active standing cane parcel within 150m)
  3. REGIONAL_FALLOW_OR_DRY_LOCALITY (Low inside and verified low across 100-250m neighborhood)
  4. INSUFFICIENT_NEIGHBORHOOD_OBSERVATION (Fails closed if rings lack sufficient valid SCL pixels)
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
    poly_utm = transform(WGS84_TO_UTM43N, polygon_wgs84)
    if not poly_utm.is_valid:
        poly_utm = poly_utm.buffer(0)

    rings_wgs84 = {}
    prev_geom_utm = poly_utm

    for dist in ring_distances_m:
        buf_utm = poly_utm.buffer(dist)
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
    min_usability_scl: Tuple[int, ...] = (4, 5),
    min_valid_pixels: int = 5
) -> Dict[str, Optional[float]]:
    """
    Extracts mean NDVI, usable pixel coverage, and canopy fraction inside a ring geometry.
    """
    if ring_geom_wgs84 is None or ring_geom_wgs84.is_empty:
        return {"mean_ndvi": None, "canopy_pct": None, "usable_pixels": 0}

    if str(raster_crs) not in ["EPSG:4326", "WGS84", "+init=epsg:4326"]:
        to_raster_crs = pyproj.Transformer.from_crs("EPSG:4326", raster_crs, always_xy=True).transform
        geom_in_raster = transform(to_raster_crs, ring_geom_wgs84)
    else:
        geom_in_raster = ring_geom_wgs84

    try:
        mask = geometry_mask(
            [geom_in_raster],
            out_shape=red_raster.shape,
            transform=affine_transform,
            invert=True
        )
    except Exception:
        return {"mean_ndvi": None, "canopy_pct": None, "usable_pixels": 0}

    ring_red = red_raster[mask].astype(np.float64)
    ring_nir = nir_raster[mask].astype(np.float64)
    ring_scl = scl_raster[mask]

    total_ring_pixels = len(ring_red)
    if total_ring_pixels == 0:
        return {"mean_ndvi": None, "canopy_pct": None, "usable_pixels": 0}

    valid_scl_mask = np.isin(ring_scl, min_usability_scl)
    valid_count = int(np.sum(valid_scl_mask))
    if valid_count < min_valid_pixels:
        return {"mean_ndvi": None, "canopy_pct": None, "usable_pixels": valid_count}

    valid_red = ring_red[valid_scl_mask]
    valid_nir = ring_nir[valid_scl_mask]

    denom = valid_nir + valid_red
    valid_denom_mask = denom > 1e-4
    if np.sum(valid_denom_mask) < min_valid_pixels:
        return {"mean_ndvi": None, "canopy_pct": None, "usable_pixels": valid_count}

    v_red = valid_red[valid_denom_mask]
    v_nir = valid_nir[valid_denom_mask]
    ndvis = (v_nir - v_red) / (v_nir + v_red)

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
    nearest_high_canopy_dist_m: Optional[float],
    min_pixels_context: int = 5
) -> Dict[str, Any]:
    """
    Diagnoses the spatial cause of low canopy occupancy.
    Fails closed to INSUFFICIENT_NEIGHBORHOOD_OBSERVATION if rings lack valid data.
    """
    can_in = inside_canopy_occupancy_pct

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

    # Extract ring canopy percentages without manufacturing false zeros
    r25_dict = ring_stats.get("ring_25m", {})
    r50_dict = ring_stats.get("ring_50m", {})
    r100_dict = ring_stats.get("ring_100m", {})
    r250_dict = ring_stats.get("ring_250m", {})

    r25_can = r25_dict.get("canopy_pct")
    r50_can = r50_dict.get("canopy_pct")
    r100_can = r100_dict.get("canopy_pct")
    r250_can = r250_dict.get("canopy_pct")

    # LOW CANOPY INSIDE POLYGON (< 20%): Diagnose neighborhood

    # Case A: Boundary / Polygon Shift Suspect
    # Only triggers if 25m or 50m ring has valid data AND canopy >= 45%
    if (r25_can is not None and r25_can >= 45.0) or (r50_can is not None and r50_can >= 45.0):
        r25_str = f"{r25_can}%" if r25_can is not None else "N/A"
        r50_str = f"{r50_can}%" if r50_can is not None else "N/A"
        return {
            "spatial_discrepancy_stratum": "BOUNDARY_OR_POLYGON_SHIFT_SUSPECT",
            "diagnostic_rationale": (
                f"Low inside ({can_in:.1f}%), but strong standing canopy immediately outside "
                f"(25m ring: {r25_str}, 50m ring: {r50_str}). Likely GPS coordinate shift or clipped boundary."
            )
        }

    # Case B: Field-Specific Harvest in Active Cluster
    if nearest_high_canopy_dist_m is not None and nearest_high_canopy_dist_m <= 150.0:
        return {
            "spatial_discrepancy_stratum": "FIELD_SPECIFIC_DISCREPANCY_CLUSTER_ACTIVE",
            "diagnostic_rationale": (
                f"Low inside ({can_in:.1f}%), but confirmed standing cane parcel exists "
                f"{nearest_high_canopy_dist_m:.0f}m away. Field-specific harvest/fallow, not regional absence."
            )
        }

    # FAIL-CLOSED CHECK: If 100m or 250m context is missing / invalid, DO NOT claim regional fallow!
    r100_valid = (r100_can is not None and r100_dict.get("usable_pixels", 0) >= min_pixels_context)
    r250_valid = (r250_can is not None and r250_dict.get("usable_pixels", 0) >= min_pixels_context)

    if not r100_valid and not r250_valid:
        return {
            "spatial_discrepancy_stratum": "INSUFFICIENT_NEIGHBORHOOD_OBSERVATION",
            "diagnostic_rationale": "Insufficient valid Sentinel pixels in 100-250m context rings to determine regional status."
        }

    # Case C: Verified Regional Fallow or Dry Locality
    if r100_valid and r250_valid and r100_can < 15.0 and r250_can < 15.0:
        return {
            "spatial_discrepancy_stratum": "REGIONAL_FALLOW_OR_DRY_LOCALITY",
            "diagnostic_rationale": (
                f"Low inside ({can_in:.1f}%) and verified low canopy throughout 100-250m surroundings "
                f"(100m ring: {r100_can}%, 250m ring: {r250_can}%). Broad fallow/unirrigated sector."
            )
        }

    # Case D: Mixed / Heterogeneous Neighborhood
    r25_str = f"{r25_can}%" if r25_can is not None else "N/A"
    r100_str = f"{r100_can}%" if r100_can is not None else "N/A"
    r250_str = f"{r250_can}%" if r250_can is not None else "N/A"
    return {
        "spatial_discrepancy_stratum": "ISOLATED_LOW_CANOPY_DISCREPANCY",
        "diagnostic_rationale": (
            f"Low inside ({can_in:.1f}%) with mixed neighborhood canopy "
            f"(25m: {r25_str}, 100m: {r100_str}, 250m: {r250_str})."
        )
    }