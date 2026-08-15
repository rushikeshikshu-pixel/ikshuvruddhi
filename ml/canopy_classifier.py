"""
ml/canopy_classifier.py
Single Source of Truth Sugarcane Canopy Classification Engine
Used identically in:
  1. Production CDSE Real-Time Snapping (ml/copernicus_client.py)
  2. Production Geospatial Snapping Engine (ml/satellite_engine.py)
  3. Offline Empirical Ground-Truth Validation (validation/sentinel_canopy_validation.py)
"""

import numpy as np
from typing import Dict, Any, Union

# Valid Copernicus Sentinel-2 L2A Scene Classification Layer (SCL) classes:
# 4: Vegetation, 5: Bare Soil, 6: Water, 7: Unclassified (low-prob cloud/edge)
SCL_VALID_CLASSES = {4, 5, 6, 7}

def compute_cane_signature_score(ndvi: float, ndre: float, lswi: float) -> float:
    """Computes continuous sugarcane canopy vigor score (0.0 to 1.0)."""
    score = 0.35 * ((ndvi - 0.40) / 0.40) + 0.35 * ((ndre - 0.10) / 0.20) + 0.30 * ((lswi - 0.05) / 0.25)
    return float(np.clip(score, 0.01, 0.98))

def classify_sugarcane_pixel(
    ndvi: float,
    ndre: float,
    lswi: float,
    ndwi: float = 0.0,
    bsi: float = 0.0,
    scl: int = 4
) -> Dict[str, Any]:
    """
    Standardized single-pixel multi-spectral sugarcane classification.
    """
    # 1. Check Scene Classification Mask
    if scl not in SCL_VALID_CLASSES:
        return {
            "is_standing_cane": False,
            "land_class": "CLOUD_OR_INVALID_SCL",
            "cane_signature_score": 0.0,
            "scl_valid": False
        }

    # 2. Reject Water / Ponds
    if ndwi > 0.08:
        return {
            "is_standing_cane": False,
            "land_class": "WATER_POND",
            "cane_signature_score": 0.01,
            "scl_valid": True
        }

    # 3. Reject Bare Soil, Farm Roads, and Severely Degraded Land
    if bsi > 0.10 or ndvi < 0.35:
        return {
            "is_standing_cane": False,
            "land_class": "ROAD_OR_BARE_SOIL",
            "cane_signature_score": 0.04,
            "scl_valid": True
        }

    # 4. Continuous Cane Signature Score
    score = compute_cane_signature_score(ndvi, ndre, lswi)

    # 5. Standing Cane Classification Threshold:
    # High photosynthetic vigor, healthy red-edge chlorophyll, and canopy water thickness
    is_cane = bool((ndvi >= 0.55) and (ndre >= 0.12) and (lswi >= 0.05))
    land_class = "STANDING_SUGARCANE" if is_cane else "OTHER_VEGETATION"

    return {
        "is_standing_cane": is_cane,
        "land_class": land_class,
        "cane_signature_score": score,
        "scl_valid": True
    }

def classify_sugarcane_raster(
    ndvi_arr: np.ndarray,
    ndre_arr: np.ndarray,
    lswi_arr: np.ndarray,
    scl_arr: np.ndarray,
    ndwi_arr: np.ndarray = None,
    bsi_arr: np.ndarray = None
) -> np.ndarray:
    """
    Vectorized multi-spectral sugarcane classification across a raster window.
    Returns boolean mask (True = Standing Sugarcane).
    """
    valid_scl = np.isin(scl_arr, list(SCL_VALID_CLASSES))
    
    # Base spectral rules
    cane_mask = (ndvi_arr >= 0.55) & (ndre_arr >= 0.12) & (lswi_arr >= 0.05) & valid_scl
    
    # Water rejection
    if ndwi_arr is not None:
        cane_mask = cane_mask & (ndwi_arr <= 0.08)
        
    # Bare soil rejection
    if bsi_arr is not None:
        cane_mask = cane_mask & (bsi_arr <= 0.10)
        
    return cane_mask