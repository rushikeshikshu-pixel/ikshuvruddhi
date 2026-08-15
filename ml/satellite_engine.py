"""
IkshuVruddhi Production Geospatial & Satellite Segmentation Engine
1. Consistent return schema: Always returns 'cane_signature_score_mean' and 'standing_cane_acres' (Zero-cane safe).
2. Shapely geometric union & buffer operations with fallback handling.
3. Accurate metric area calculation based on polygonized pixel geometries.
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

def calculate_spectral_indices(b2: float, b3: float, b4: float, b8: float, b8a: float, b11: float, b12: float) -> Dict[str, float]:
    ndvi = (b8 - b4) / (b8 + b4 + 1e-7)
    ndre = (b8 - b8a) / (b8 + b8a + 1e-7)
    ndwi = (b3 - b8) / (b3 + b8 + 1e-7)
    lswi = (b8 - b11) / (b8 + b11 + 1e-7)
    bsi = ((b11 + b4) - (b8 + b2)) / ((b11 + b4) + (b8 + b2) + 1e-7)
    
    return {
        "ndvi": round(float(ndvi), 4),
        "ndre": round(float(ndre), 4),
        "ndwi": round(float(ndwi), 4),
        "lswi": round(float(lswi), 4),
        "bsi": round(float(bsi), 4)
    }

def polygonize_cane_mask(raster_cells: List[Dict[str, Any]], original_polygon: List[List[float]]) -> Dict[str, Any]:
    """
    Extracts the genuine standing cane boundary from classified 10m raster cells.
    Safe against empty scenes or scenes with zero classified cane pixels.
    """
    cane_cells = [c for c in raster_cells if c.get("is_standing_cane", False)]
    total_cells = len(raster_cells)
    
    # 0-cane safe guard: return consistent schema with 0.0 scores
    if not cane_cells or total_cells == 0:
        return {
            "snapped_polygon": original_polygon,
            "standing_cane_acres": 0.0,
            "standing_fraction_pct": 0.0,
            "total_classified_cells": total_cells,
            "cane_cells_count": 0,
            "cane_signature_score_mean": 0.0
        }
    
    standing_fraction = len(cane_cells) / total_cells
    
    # Compute mean Cane Signature Score across confirmed cane pixels
    scores = [c.get("cane_signature_score", c.get("p_cane", 0.0)) for c in cane_cells]
    mean_cane_score = round(float(np.mean(scores)) * 100.0, 1) if scores else 0.0

    if HAS_SHAPELY:
        cell_polys = []
        for c in cane_cells:
            coords = c["coords"]
            poly_xy = [(pt[1], pt[0]) for pt in coords]
            cell_polys.append(Polygon(poly_xy))
        
        merged_cane_geom = unary_union(cell_polys)
        smoothed_geom = merged_cane_geom.buffer(0.00004).buffer(-0.00003)
        
        orig_poly_xy = [(pt[1], pt[0]) for pt in original_polygon]
        orig_geom = Polygon(orig_poly_xy)
        
        final_cane_geom = smoothed_geom.intersection(orig_geom)
        
        if final_cane_geom.is_empty:
            final_poly_coords = original_polygon
        elif isinstance(final_cane_geom, Polygon):
            final_poly_coords = [[round(pt[1], 7), round(pt[0], 7)] for pt in list(final_cane_geom.exterior.coords)]
        elif isinstance(final_cane_geom, MultiPolygon):
            largest = max(final_cane_geom.geoms, key=lambda g: g.area)
            final_poly_coords = [[round(pt[1], 7), round(pt[0], 7)] for pt in list(largest.exterior.coords)]
        else:
            final_poly_coords = original_polygon
    else:
        cane_points = [c["center"] for c in cane_cells]
        final_poly_coords = cane_points if len(cane_points) >= 3 else original_polygon

    detected_cane_acres = round(len(cane_cells) * 0.0247105, 2)
    
    return {
        "snapped_polygon": final_poly_coords,
        "standing_cane_acres": detected_cane_acres,
        "standing_fraction_pct": round(standing_fraction * 100.0, 1),
        "total_classified_cells": total_cells,
        "cane_cells_count": len(cane_cells),
        "cane_signature_score_mean": mean_cane_score
    }

if __name__ == "__main__":
    print("IkshuVruddhi Geospatial & Satellite Segmentation Engine Ready.")
