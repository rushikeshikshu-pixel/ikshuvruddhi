"""
ml/canopy_classifier.py
Unified Mathematical Engine for Sugarcane Multi-Spectral Remote Sensing
Identical implementation across:
  1. Production Real-Time Copernicus CDSE Client (ml/copernicus_client.py)
  2. Production Snapping & Geometry Engine (ml/satellite_engine.py)
  3. Ground-Truth Validation Suite (validation/sentinel_canopy_validation.py)
"""

import numpy as np
from typing import Dict, Any, Tuple, Union

# Copernicus Sentinel-2 L2A Scene Classification Layer (SCL) Whitelist:
# 4: Vegetation, 5: Bare Soil, 6: Water, 7: Unclassified (low-probability cloud/edges)
SCL_VALID_CLASSES = {4, 5, 6, 7}

def compute_spectral_indices(
    b2: Union[float, np.ndarray],  # Blue (B02, 10m)
    b3: Union[float, np.ndarray],  # Green (B03, 10m)
    b4: Union[float, np.ndarray],  # Red (B04, 10m)
    b5: Union[float, np.ndarray],  # RedEdge-1 (B05, 20m resampled to 10m)
    b8: Union[float, np.ndarray],  # NIR (B08, 10m)
    b11: Union[float, np.ndarray], # SWIR-1 (B11, 20m resampled to 10m)
    eps: float = 1e-7
) -> Dict[str, Union[float, np.ndarray]]:
    """
    Standardized biophysical multi-spectral indices calculation.
    Supports both scalar pixel values and vectorized NumPy arrays.
    """
    with np.errstate(divide="ignore", invalid="ignore"):
        ndvi = (b8 - b4) / (b8 + b4 + eps)
        ndre = (b8 - b5) / (b8 + b5 + eps) # Standardized on B05 RedEdge-1 (705 nm)
        lswi = (b8 - b11) / (b8 + b11 + eps)
        ndwi = (b3 - b8) / (b3 + b8 + eps)
        bsi = ((b11 + b4) - (b8 + b2)) / ((b11 + b4) + (b8 + b2) + eps)

    return {
        "ndvi": ndvi,
        "ndre": ndre,
        "lswi": lswi,
        "ndwi": ndwi,
        "bsi": bsi
    }

def compute_cane_signature_score(
    ndvi: Union[float, np.ndarray],
    ndre: Union[float, np.ndarray],
    lswi: Union[float, np.ndarray]
) -> Union[float, np.ndarray]:
    """Computes continuous sugarcane canopy vigor score (0.01 to 0.98)."""
    score = 0.35 * ((ndvi - 0.40) / 0.40) + 0.35 * ((ndre - 0.10) / 0.20) + 0.30 * ((lswi - 0.05) / 0.25)
    return np.clip(score, 0.01, 0.98)

def classify_sugarcane_pixel(
    ndvi: float,
    ndre: float,
    lswi: float,
    ndwi: float = 0.0,
    bsi: float = 0.0,
    scl: int = 4
) -> Dict[str, Any]:
    """
    Single-pixel multi-spectral sugarcane classification.
    """
    # 1. SCL Scene Classification Masking
    if scl not in SCL_VALID_CLASSES:
        return {
            "is_standing_cane": False,
            "land_class": "CLOUD_SHADOW_OR_NODATA_MASKED",
            "cane_signature_score": 0.0,
            "scl_valid": False
        }

    # 2. Reject Water / Flood Furrows
    if ndwi > 0.08:
        return {
            "is_standing_cane": False,
            "land_class": "WATER_POND",
            "cane_signature_score": 0.01,
            "scl_valid": True
        }

    # 3. Reject Bare Soil, Farm Roads, and Fallow Ground
    if bsi > 0.10 or ndvi < 0.35:
        return {
            "is_standing_cane": False,
            "land_class": "ROAD_OR_BARE_SOIL",
            "cane_signature_score": 0.04,
            "scl_valid": True
        }

    # 4. Continuous Cane Signature Score
    score = float(compute_cane_signature_score(ndvi, ndre, lswi))

    # 5. Standing Sugarcane Classification Criteria
    is_cane = bool((ndvi >= 0.55) and (ndre >= 0.12) and (lswi >= 0.05))
    land_class = "STANDING_SUGARCANE" if is_cane else "OTHER_VEGETATION"

    return {
        "is_standing_cane": is_cane,
        "land_class": land_class,
        "cane_signature_score": round(score, 3),
        "scl_valid": True
    }

def classify_sugarcane_raster(
    ndvi_arr: np.ndarray,
    ndre_arr: np.ndarray,
    lswi_arr: np.ndarray,
    scl_arr: np.ndarray,
    ndwi_arr: np.ndarray,
    bsi_arr: np.ndarray
) -> np.ndarray:
    """
    Vectorized multi-spectral sugarcane classification across a raster window.
    Guarantees exact mathematical equivalence to classify_sugarcane_pixel.
    """
    valid_scl = np.isin(scl_arr, list(SCL_VALID_CLASSES))
    not_water = ndwi_arr <= 0.08
    not_bare_soil = (bsi_arr <= 0.10) & (ndvi_arr >= 0.35)
    spectral_cane = (ndvi_arr >= 0.55) & (ndre_arr >= 0.12) & (lswi_arr >= 0.05)
    
    return valid_scl & not_water & not_bare_soil & spectral_cane