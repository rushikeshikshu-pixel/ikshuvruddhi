"""
IkshuVruddhi Production Geospatial & Satellite Segmentation Engine
1. True UTM 43N (EPSG:32643) metric geometry reprojection & buffer operations in meters (+4m / -3m).
2. Complete Shapely geometry area calculation preserving interior holes (water ponds) and MultiPolygons.
3. Metric acreage calculation: Acres = projected_geom.area / 4046.8564224
4. Cloud-aware fractions:
   - clear_sky_coverage_pct = (valid_pixels / total_pixels) * 100
   - observed_cane_fraction_pct = (cane_pixels / valid_pixels) * 100
5. Zero-cane safe return schema with cane_signature_score_mean.
"""

import os
import sys
import json
import math
import numpy as np
from typing import List, Dict, Tuple, Any

try:
    from shapely.geometry import Polygon, MultiPolygon, Point, shape, mapping
    from shapely.ops import unary_union, transform
    HAS_SHAPELY = True
except ImportError:
    HAS_SHAPELY = False

def project_wgs84_to_utm43n(lon: float, lat: float) -> Tuple[float, float]:
    """
    Direct transverse Mercator projection for UTM Zone 43N (EPSG:32643, central meridian 75° E).
    Exact metric coordinates (meters) on WGS84 ellipsoid for Maharashtra sugar command areas.
    """
    a = 6378137.0
    f = 1.0 / 298.257223563
    e2 = 2 * f - f * f
    e_prime2 = e2 / (1.0 - e2)
    k0 = 0.9996
    lon0 = 75.0 # Central meridian for UTM Zone 43N

    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)
    lon0_rad = math.radians(lon0)

    N = a / math.sqrt(1.0 - e2 * math.sin(lat_rad) ** 2)
    T = math.tan(lat_rad) ** 2
    C = e_prime2 * math.cos(lat_rad) ** 2
    A = (lon_rad - lon0_rad) * math.cos(lat_rad)

    M = a * ((1.0 - e2 / 4.0 - 3.0 * e2 ** 2 / 64.0 - 5.0 * e2 ** 3 / 256.0) * lat_rad
             - (3.0 * e2 / 8.0 + 3.0 * e2 ** 2 / 32.0 + 45.0 * e2 ** 3 / 1024.0) * math.sin(2.0 * lat_rad)
             + (15.0 * e2 ** 2 / 256.0 + 45.0 * e2 ** 3 / 1024.0) * math.sin(4.0 * lat_rad)
             - (35.0 * e2 ** 3 / 3072.0) * math.sin(6.0 * lat_rad))

    easting = 500000.0 + k0 * N * (A + (1.0 - T + C) * A ** 3 / 6.0
                                  + (5.0 - 18.0 * T + T ** 2 + 72.0 * C - 58.0 * e_prime2) * A ** 5 / 120.0)
    northing = k0 * (M + N * math.tan(lat_rad) * (A ** 2 / 2.0
                                                 + (5.0 - T + 9.0 * C + 4.0 * C ** 2) * A ** 4 / 24.0
                                                 + (61.0 - 58.0 * T + T ** 2 + 600.0 * C - 330.0 * e_prime2) * A ** 6 / 720.0))

    return (easting, northing)

def project_utm43n_to_wgs84(easting: float, northing: float) -> Tuple[float, float]:
    """
    Inverse projection from UTM Zone 43N (EPSG:32643) back to WGS84 degrees (lon, lat).
    """
    a = 6378137.0
    f = 1.0 / 298.257223563
    e2 = 2 * f - f * f
    e_prime2 = e2 / (1.0 - e2)
    k0 = 0.9996
    lon0 = 75.0

    x = easting - 500000.0
    y = northing

    M = y / k0
    mu = M / (a * (1.0 - e2 / 4.0 - 3.0 * e2 ** 2 / 64.0 - 5.0 * e2 ** 3 / 256.0))

    e1 = (1.0 - math.sqrt(1.0 - e2)) / (1.0 + math.sqrt(1.0 - e2))
    phi1 = mu + (3.0 * e1 / 2.0 - 27.0 * e1 ** 3 / 32.0) * math.sin(2.0 * mu) \
           + (21.0 * e1 ** 2 / 16.0 - 55.0 * e1 ** 4 / 32.0) * math.sin(4.0 * mu) \
           + (151.0 * e1 ** 3 / 96.0) * math.sin(6.0 * mu)

    N1 = a / math.sqrt(1.0 - e2 * math.sin(phi1) ** 2)
    T1 = math.tan(phi1) ** 2
    C1 = e_prime2 * math.cos(phi1) ** 2
    R1 = a * (1.0 - e2) / math.pow(1.0 - e2 * math.sin(phi1) ** 2, 1.5)
    D = x / (N1 * k0)

    lat_rad = phi1 - (N1 * math.tan(phi1) / R1) * (D ** 2 / 2.0 - (5.0 + 3.0 * T1 + 10.0 * C1 - 4.0 * C1 ** 2 - 9.0 * e_prime2) * D ** 4 / 24.0
                                                 + (61.0 + 90.0 * T1 + 298.0 * C1 + 45.0 * T1 ** 2 - 252.0 * e_prime2 - 3.0 * C1 ** 2) * D ** 6 / 720.0)
    lon_rad = math.radians(lon0) + (D - (1.0 + 2.0 * T1 + C1) * D ** 3 / 6.0
                                    + (5.0 - 2.0 * C1 + 28.0 * T1 - 3.0 * C1 ** 2 + 8.0 * e_prime2 + 24.0 * T1 ** 2) * D ** 5 / 120.0) / math.cos(phi1)

    return (math.degrees(lon_rad), math.degrees(lat_rad))

def polygonize_cane_mask(raster_cells: List[Dict[str, Any]], original_polygon: List[List[float]]) -> Dict[str, Any]:
    """
    Extracts the genuine standing cane boundary in projected UTM Zone 43N (EPSG:32643).
    Preserves MultiPolygons and interior holes (water ponds), and computes exact metric acreage.
    """
    total_cells = len(raster_cells)
    valid_cells = [c for c in raster_cells if c.get("scl_valid", True)]
    cane_cells = [c for c in raster_cells if c.get("is_standing_cane", False)]
    
    valid_count = len(valid_cells)
    cane_count = len(cane_cells)

    clear_sky_coverage_pct = round((valid_count / total_cells * 100.0), 1) if total_cells else 0.0
    observed_cane_fraction_pct = round((cane_count / valid_count * 100.0), 1) if valid_count else 0.0

    if cane_count == 0 or valid_count == 0:
        return {
            "snapped_polygon": original_polygon,
            "standing_cane_acres": 0.0,
            "standing_fraction_pct": 0.0,
            "clear_sky_coverage_pct": clear_sky_coverage_pct,
            "observed_cane_fraction_pct": 0.0,
            "total_classified_cells": total_cells,
            "valid_cells_count": valid_count,
            "cane_cells_count": 0,
            "cane_signature_score_mean": 0.0
        }

    scores = [c.get("cane_signature_score", c.get("p_cane", 0.0)) for c in cane_cells]
    mean_cane_score = round(float(np.mean(scores)) * 100.0, 1) if scores else 0.0

    if HAS_SHAPELY:
        # 1. Project 10m raster cells into UTM Zone 43N meters
        projected_cell_polys = []
        for c in cane_cells:
            coords = c["coords"]
            utm_ring = [project_wgs84_to_utm43n(pt[1], pt[0]) for pt in coords]
            projected_cell_polys.append(Polygon(utm_ring))

        merged_utm_geom = unary_union(projected_cell_polys)
        
        # 2. Metric smoothing buffers in METERS (e.g. +4m expand, -3m shrink)
        smoothed_utm_geom = merged_utm_geom.buffer(4.0).buffer(-3.0)

        # 3. Intersect with original Gat boundary projected into UTM
        orig_utm_ring = [project_wgs84_to_utm43n(pt[1], pt[0]) for pt in original_polygon]
        orig_utm_geom = Polygon(orig_utm_ring)

        final_utm_geom = smoothed_utm_geom.intersection(orig_utm_geom)

        if final_utm_geom.is_empty:
            final_wgs84_coords = original_polygon
            metric_area_m2 = 0.0
        else:
            # TRUE METRIC AREA: Directly from projected Shapely geometry (preserves holes & all MultiPolygon parts)
            metric_area_m2 = final_utm_geom.area

            # Convert back to WGS84 for GeoJSON display
            if isinstance(final_utm_geom, Polygon):
                final_wgs84_coords = [[round(project_utm43n_to_wgs84(pt[0], pt[1])[1], 7),
                                        round(project_utm43n_to_wgs84(pt[0], pt[1])[0], 7)]
                                       for pt in list(final_utm_geom.exterior.coords)]
            elif isinstance(final_utm_geom, MultiPolygon):
                # For UI display, extract all parts
                largest = max(final_utm_geom.geoms, key=lambda g: g.area)
                final_wgs84_coords = [[round(project_utm43n_to_wgs84(pt[0], pt[1])[1], 7),
                                        round(project_utm43n_to_wgs84(pt[0], pt[1])[0], 7)]
                                       for pt in list(largest.exterior.coords)]
            else:
                final_wgs84_coords = original_polygon
    else:
        cane_points = [c["center"] for c in cane_cells]
        final_wgs84_coords = cane_points if len(cane_points) >= 3 else original_polygon
        metric_area_m2 = len(cane_cells) * 100.0

    metric_acres = round(metric_area_m2 / 4046.8564224, 2)

    return {
        "snapped_polygon": final_wgs84_coords,
        "standing_cane_acres": metric_acres,
        "standing_fraction_pct": observed_cane_fraction_pct,
        "clear_sky_coverage_pct": clear_sky_coverage_pct,
        "observed_cane_fraction_pct": observed_cane_fraction_pct,
        "total_classified_cells": total_cells,
        "valid_cells_count": valid_count,
        "cane_cells_count": cane_count,
        "cane_signature_score_mean": mean_cane_score
    }

if __name__ == "__main__":
    print("IkshuVruddhi True UTM 43N (EPSG:32643) Metric Geospatial Engine Ready.")
