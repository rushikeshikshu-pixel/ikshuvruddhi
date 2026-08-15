"""
IkshuVruddhi Production Geospatial & Satellite Segmentation Engine
1. Strict Parcel-Intersecting Cell Filtering (using Shapely intersection / point-in-polygon).
2. Exact Raw Area Geometry Summation: A_raw = sum(Area(Cell_i ∩ Gat)) in projected UTM metric square meters.
3. Correct GeoJSON standard [lon, lat] coordinate ordering in zero-cane / fallback paths.
4. Neutral Morphological Closing (±3.0m in metric UTM) with complete MultiPolygon and hole preservation.
"""

import os
import sys
import json
import math
import numpy as np
from typing import List, Dict, Tuple, Any

try:
    from shapely.geometry import Polygon, MultiPolygon, Point, shape, mapping
    from shapely.ops import unary_union
    HAS_SHAPELY = True
except ImportError:
    HAS_SHAPELY = False

def get_utm_zone_epsg(lon: float) -> Tuple[int, float]:
    zone = int(math.floor((lon + 180.0) / 6.0)) + 1
    lon0 = (zone - 1) * 6.0 - 180.0 + 3.0
    return zone, lon0

def project_wgs84_to_utm(lon: float, lat: float, lon0: float = 75.0) -> Tuple[float, float]:
    a = 6378137.0
    f = 1.0 / 298.257223563
    e2 = 2 * f - f * f
    e_prime2 = e2 / (1.0 - e2)
    k0 = 0.9996

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

def project_utm_to_wgs84(easting: float, northing: float, lon0: float = 75.0) -> Tuple[float, float]:
    a = 6378137.0
    f = 1.0 / 298.257223563
    e2 = 2 * f - f * f
    e_prime2 = e2 / (1.0 - e2)
    k0 = 0.9996

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

def geometry_to_geojson_wgs84(geom, lon0: float) -> Dict[str, Any]:
    """Converts UTM Shapely geometry into GeoJSON format with [lon, lat] coordinates."""
    if geom.is_empty:
        return {"type": "Polygon", "coordinates": []}
    
    if isinstance(geom, Polygon):
        rings = []
        ext = [[round(project_utm_to_wgs84(pt[0], pt[1], lon0)[0], 7),
                round(project_utm_to_wgs84(pt[0], pt[1], lon0)[1], 7)] for pt in list(geom.exterior.coords)]
        rings.append(ext)
        for interior in geom.interiors:
            hole = [[round(project_utm_to_wgs84(pt[0], pt[1], lon0)[0], 7),
                     round(project_utm_to_wgs84(pt[0], pt[1], lon0)[1], 7)] for pt in list(interior.coords)]
            rings.append(hole)
        return {"type": "Polygon", "coordinates": rings}
        
    elif isinstance(geom, MultiPolygon):
        poly_list = []
        for poly in geom.geoms:
            rings = []
            ext = [[round(project_utm_to_wgs84(pt[0], pt[1], lon0)[0], 7),
                    round(project_utm_to_wgs84(pt[0], pt[1], lon0)[1], 7)] for pt in list(poly.exterior.coords)]
            rings.append(ext)
            for interior in poly.interiors:
                hole = [[round(project_utm_to_wgs84(pt[0], pt[1], lon0)[0], 7),
                         round(project_utm_to_wgs84(pt[0], pt[1], lon0)[1], 7)] for pt in list(interior.coords)]
                rings.append(hole)
            poly_list.append(rings)
        return {"type": "MultiPolygon", "coordinates": poly_list}

    return {"type": "Polygon", "coordinates": []}

def format_wgs84_geojson_coords(lat_lon_list: List[List[float]]) -> List[List[float]]:
    """Converts internal [lat, lon] polygon to GeoJSON standard [lon, lat]."""
    return [[p[1], p[0]] for p in lat_lon_list]

def polygonize_cane_mask(raster_cells: List[Dict[str, Any]], original_polygon: List[List[float]]) -> Dict[str, Any]:
    """
    Extracts the genuine standing cane boundary with strict parcel-intersection filtering
    and exact geometry-derived raw / smoothed metric acreage.
    """
    geojson_fallback = {
        "type": "Polygon",
        "coordinates": [format_wgs84_geojson_coords(original_polygon)]
    }

    if not original_polygon or len(original_polygon) < 3:
        return {
            "geojson": geojson_fallback,
            "snapped_polygon": original_polygon,
            "standing_cane_acres": 0.0,
            "raw_classified_acres": 0.0,
            "smoothed_canopy_acres": 0.0,
            "standing_fraction_pct": 0.0,
            "clear_sky_coverage_pct": 0.0,
            "observed_cane_fraction_pct": 0.0,
            "total_parcel_cells": 0,
            "valid_cells_count": 0,
            "cane_cells_count": 0,
            "cane_signature_score_mean": 0.0
        }

    center_lon = sum([p[1] for p in original_polygon]) / len(original_polygon)
    utm_zone, lon0 = get_utm_zone_epsg(center_lon)

    # 1. Project original Gat boundary into UTM
    orig_utm_ring = [project_wgs84_to_utm(pt[1], pt[0], lon0) for pt in original_polygon]
    orig_utm_geom = Polygon(orig_utm_ring) if HAS_SHAPELY else None

    # 2. STRICT PARCEL-INTERSECTING CELL FILTERING
    parcel_cells = []
    for c in raster_cells:
        coords = c.get("coords", [])
        if HAS_SHAPELY and orig_utm_geom and coords:
            cell_utm_ring = [project_wgs84_to_utm(pt[1], pt[0], lon0) for pt in coords]
            cell_geom = Polygon(cell_utm_ring)
            if cell_geom.intersects(orig_utm_geom):
                c_copy = dict(c)
                c_copy["utm_geom"] = cell_geom
                c_copy["intersection_area_m2"] = cell_geom.intersection(orig_utm_geom).area
                parcel_cells.append(c_copy)
        else:
            parcel_cells.append(c)

    total_parcel_cells = len(parcel_cells)
    valid_cells = [c for c in parcel_cells if c.get("scl_valid", True)]
    cane_cells = [c for c in parcel_cells if c.get("is_standing_cane", False)]
    
    valid_count = len(valid_cells)
    cane_count = len(cane_cells)

    clear_sky_coverage_pct = round((valid_count / total_parcel_cells * 100.0), 1) if total_parcel_cells else 0.0
    observed_cane_fraction_pct = round((cane_count / valid_count * 100.0), 1) if valid_count else 0.0

    # 3. EXACT RAW AREA: Sum(Area(Cell_i ∩ Gat))
    if HAS_SHAPELY and orig_utm_geom:
        raw_area_m2 = sum([c.get("intersection_area_m2", 100.0) for c in cane_cells])
    else:
        raw_area_m2 = cane_count * 100.0
    raw_classified_acres = round(raw_area_m2 / 4046.8564224, 2)

    if cane_count == 0 or valid_count == 0:
        return {
            "geojson": geojson_fallback,
            "snapped_polygon": original_polygon,
            "standing_cane_acres": 0.0,
            "raw_classified_acres": 0.0,
            "smoothed_canopy_acres": 0.0,
            "standing_fraction_pct": 0.0,
            "clear_sky_coverage_pct": clear_sky_coverage_pct,
            "observed_cane_fraction_pct": 0.0,
            "total_parcel_cells": total_parcel_cells,
            "valid_cells_count": valid_count,
            "cane_cells_count": 0,
            "cane_signature_score_mean": 0.0
        }

    scores = [c.get("cane_signature_score", c.get("p_cane", 0.0)) for c in cane_cells]
    mean_cane_score = round(float(np.mean(scores)) * 100.0, 1) if scores else 0.0

    if HAS_SHAPELY and orig_utm_geom:
        projected_cell_polys = [c["utm_geom"] for c in cane_cells if "utm_geom" in c]
        if not projected_cell_polys:
            projected_cell_polys = [Polygon([project_wgs84_to_utm(pt[1], pt[0], lon0) for pt in c["coords"]]) for c in cane_cells]

        merged_utm_geom = unary_union(projected_cell_polys)
        
        # NEUTRAL MORPHOLOGICAL CLOSING (+3.0m expand, -3.0m shrink)
        smoothed_utm_geom = merged_utm_geom.buffer(3.0).buffer(-3.0)

        # Exact intersection with registered Gat boundary
        final_utm_geom = smoothed_utm_geom.intersection(orig_utm_geom)

        if final_utm_geom.is_empty:
            geojson_geom = geojson_fallback
            final_wgs84_coords = original_polygon
            smoothed_canopy_acres = 0.0
        else:
            metric_area_m2 = final_utm_geom.area
            smoothed_canopy_acres = round(metric_area_m2 / 4046.8564224, 2)
            geojson_geom = geometry_to_geojson_wgs84(final_utm_geom, lon0)
            
            if isinstance(final_utm_geom, Polygon):
                final_wgs84_coords = [[round(project_utm_to_wgs84(pt[0], pt[1], lon0)[1], 7),
                                        round(project_utm_to_wgs84(pt[0], pt[1], lon0)[0], 7)]
                                       for pt in list(final_utm_geom.exterior.coords)]
            else:
                largest = max(final_utm_geom.geoms, key=lambda g: g.area)
                final_wgs84_coords = [[round(project_utm_to_wgs84(pt[0], pt[1], lon0)[1], 7),
                                        round(project_utm_to_wgs84(pt[0], pt[1], lon0)[0], 7)]
                                       for pt in list(largest.exterior.coords)]
    else:
        cane_points = [c["center"] for c in cane_cells]
        final_wgs84_coords = cane_points if len(cane_points) >= 3 else original_polygon
        geojson_geom = {"type": "Polygon", "coordinates": [format_wgs84_geojson_coords(final_wgs84_coords)]}
        smoothed_canopy_acres = raw_classified_acres

    # Clean unneeded geometry objects from cells return
    for c in parcel_cells:
        c.pop("utm_geom", None)
        c.pop("intersection_area_m2", None)

    return {
        "geojson": geojson_geom,
        "snapped_polygon": final_wgs84_coords,
        "standing_cane_acres": smoothed_canopy_acres,
        "raw_classified_acres": raw_classified_acres,
        "smoothed_canopy_acres": smoothed_canopy_acres,
        "standing_fraction_pct": observed_cane_fraction_pct,
        "clear_sky_coverage_pct": clear_sky_coverage_pct,
        "observed_cane_fraction_pct": observed_cane_fraction_pct,
        "total_parcel_cells": total_parcel_cells,
        "valid_cells_count": valid_count,
        "cane_cells_count": cane_count,
        "cane_signature_score_mean": mean_cane_score,
        "utm_zone": f"Zone {utm_zone}N (EPSG:326{utm_zone:02d})"
    }

if __name__ == "__main__":
    print("IkshuVruddhi Production Parcel-Intersecting Geospatial Engine Ready.")
