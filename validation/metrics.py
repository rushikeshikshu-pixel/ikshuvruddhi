"""
validation/metrics.py
Exact Sub-Pixel Geometric Metric Calculations for Field-Scale Remote Sensing
"""

import math
import numpy as np
from shapely.geometry import Polygon, box
from typing import Dict, Any, List, Tuple

def compute_exact_subpixel_intersection_area(
    cell_bounds_list: List[Tuple[float, float, float, float]], # List of (minx, miny, maxx, maxy) in metric UTM
    cane_mask_flat: List[bool],
    parcel_utm_polygon: Polygon
) -> Tuple[float, float, float]:
    """
    Computes exact geometric sub-pixel intersection area in square meters.
    Returns:
      1. total_parcel_utm_area_m2: Exact area of walked parcel
      2. sat_cane_intersection_m2: Exact sum of Area(Cell_i ∩ Parcel) for cane cells
      3. all_cells_intersection_m2: Exact sum of Area(Cell_i ∩ Parcel) for all raster cells
    """
    if not parcel_utm_polygon.is_valid:
        parcel_utm_polygon = parcel_utm_polygon.buffer(0)
        
    total_parcel_utm_area_m2 = parcel_utm_polygon.area
    sat_cane_intersection_m2 = 0.0
    all_cells_intersection_m2 = 0.0
    
    for (minx, miny, maxx, maxy), is_cane in zip(cell_bounds_list, cane_mask_flat):
        cell_geom = box(minx, miny, maxx, maxy)
        if cell_geom.intersects(parcel_utm_polygon):
            inter = cell_geom.intersection(parcel_utm_polygon)
            inter_area = inter.area
            all_cells_intersection_m2 += inter_area
            if is_cane:
                sat_cane_intersection_m2 += inter_area
                
    return total_parcel_utm_area_m2, sat_cane_intersection_m2, all_cells_intersection_m2

def compute_boundary_pixel_exposure(parcel_utm_polygon: Polygon) -> float:
    """
    Computes estimated percentage of parcel area within a 5m boundary buffer (half of a 10m pixel).
    """
    perimeter_m = parcel_utm_polygon.length
    area_m2 = parcel_utm_polygon.area
    est_edge_pixels = perimeter_m / 10.0
    return min(100.0, ((est_edge_pixels * 50.0) / max(1.0, area_m2)) * 100.0)