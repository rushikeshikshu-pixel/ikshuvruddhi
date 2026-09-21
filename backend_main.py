try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
"""
IkshuVruddhi FastAPI Satellite Engine Backend
Exposes authentic Sentinel-2 L2A raster sampling, SCL cloud-masking, morphological snapping,
and the trained SOTA AI model for Pol / Brix / CCS prediction.
"""

import os
import json
import pickle
import numpy as np
import sys

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'ml'))

from ml.copernicus_client import CopernicusCDSEProcessEngine
from ml.satellite_engine import polygonize_cane_mask

app = FastAPI(title="IkshuVruddhi Real Satellite Ingestion API", version="2.4.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

engine = CopernicusCDSEProcessEngine()

# ── Load trained SOTA AI model once at startup ────────────────────────────────
_MODEL_PATH = os.path.join(os.path.dirname(__file__), "sota_ai_model.pkl")
_SOTA_MODEL = None
_SOTA_FEATURES = None
_SOTA_CV_ACCURACY = None

def _load_model():
    global _SOTA_MODEL, _SOTA_FEATURES, _SOTA_CV_ACCURACY
    try:
        from ml.sota_sugar_ai_engine import SotaAttentionTabularEngine  # noqa – needed for pickle
        with open(_MODEL_PATH, "rb") as f:
            bundle = pickle.load(f)
        _SOTA_MODEL      = bundle["model"]
        _SOTA_FEATURES   = bundle["features"]
        _SOTA_CV_ACCURACY = bundle.get("cv_accuracy", None)
        print(f"[IkshuVruddhi] SOTA model loaded — CV accuracy: {_SOTA_CV_ACCURACY:.2f}%  features: {_SOTA_FEATURES}")
    except Exception as e:
        print(f"[IkshuVruddhi] WARNING: Could not load sota_ai_model.pkl — {e}")

_load_model()
# ──────────────────────────────────────────────────────────────────────────────


class PolygonRequest(BaseModel):
    farm_id: str
    polygon: str  # lat,lon#lat,lon#...
    date: Optional[str] = None
    crop_age_days: Optional[int] = 280


class PredictRequest(BaseModel):
    """
    Feature vector for the trained SOTA Pol/Brix/CCS model.
    All satellite indices come from Sentinel-2 L2A SCL-valid pixels.
    Missing values are filled with sensible regional defaults.
    """
    farm_id: str
    crop_age_days: float

    # Sentinel-2 spectral indices (means over SCL-valid pixels)
    sat_ndvi: Optional[float] = 0.72          # (NIR-Red)/(NIR+Red)
    sat_ndre: Optional[float] = 0.58          # (NIR-RedEdge)/(NIR+RedEdge)
    sat_ndwi: Optional[float] = 0.35          # (Green-NIR)/(Green+NIR)
    sat_evi:  Optional[float] = 0.55          # Enhanced Vegetation Index

    # Thermal / climate
    sat_temp_celsius: Optional[float]          = 33.0
    sat_diurnal_temp_range: Optional[float]    = 11.5
    sat_solar_radiation_kwh_m2: Optional[float] = 6.2
    sat_precipitation_mm: Optional[float]      = 420.0

    # Derived phenology features (auto-computed if None)
    gdd: Optional[float]                 = None
    hydro_thermal_index: Optional[float] = None


@app.get("/api/health")
def health_check():
    has_credentials = bool(os.getenv("CDSE_CLIENT_ID") and os.getenv("CDSE_CLIENT_SECRET"))
    return {
        "service": "IkshuVruddhi Satellite API",
        "live_cdse_configured": has_credentials,
        "mode": "CDSE_CONFIGURED" if has_credentials else "SIMULATION_OFFLINE",
        "sota_model_loaded": _SOTA_MODEL is not None,
        "sota_cv_accuracy_pct": round(_SOTA_CV_ACCURACY, 2) if _SOTA_CV_ACCURACY else None,
    }


@app.post("/api/predict")
def predict_sucrose(req: PredictRequest):
    """
    Run the trained SOTA AI model (HistGBR + ExtraTrees + RandomForest VotingRegressor)
    to predict Pol%, Brix degBx, and CCS% for a single plot.

    Returns median prediction + 95% conformal uncertainty bounds.
    The model was trained on real Gangamai mill lab data with Sentinel-2 L2A features.
    """
    if _SOTA_MODEL is None:
        raise HTTPException(status_code=503, detail="SOTA model not loaded on server.")

    # ── Derive missing features ───────────────────────────────────────────────
    temp   = req.sat_temp_celsius or 33.0
    precip = req.sat_precipitation_mm or 420.0
    dtr    = req.sat_diurnal_temp_range or 11.5
    solar  = req.sat_solar_radiation_kwh_m2 or 6.2
    age    = req.crop_age_days

    # Growing Degree Days (base 10 degC, simplified from daily mean)
    gdd = req.gdd if req.gdd is not None else max(0.0, (temp - 10.0) * age)

    # Hydro-Thermal Index (GDD / cumulative precip — ripening quality metric)
    hydro_thermal = req.hydro_thermal_index if req.hydro_thermal_index is not None else (
        gdd / max(precip, 1.0)
    )

    feature_vector = {
        "crop_age_days":              age,
        "sat_ndvi":                   req.sat_ndvi or 0.72,
        "sat_ndre":                   req.sat_ndre or 0.58,
        "sat_ndwi":                   req.sat_ndwi or 0.35,
        "sat_evi":                    req.sat_evi  or 0.55,
        "sat_temp_celsius":           temp,
        "sat_diurnal_temp_range":     dtr,
        "sat_solar_radiation_kwh_m2": solar,
        "sat_precipitation_mm":       precip,
        "gdd":                        gdd,
        "hydro_thermal_index":        hydro_thermal,
    }

    # Build feature array in exact training order
    X = np.array([[feature_vector[f] for f in _SOTA_FEATURES]], dtype=np.float64)

    # ── Model inference ───────────────────────────────────────────────────────
    try:
        ccs_pred, conformal_margin, ccs_lower, ccs_upper = _SOTA_MODEL.predict_with_conformal_bounds(X, confidence=0.95)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Model inference failed: {e}")

    ccs    = float(ccs_pred[0])
    ccs_lo = float(ccs_lower[0])
    ccs_hi = float(ccs_upper[0])
    margin = float(conformal_margin)

    # Derive Pol and Brix from predicted CCS using inverse of ICAR/VSI formula:
    # CCS = 1.022 * Pol - 0.292 * Brix, with Purity = Pol/Brix*100
    age_months = age / 30.4
    opt_age_months = 16.0
    progress   = min(1.0, age_months / opt_age_months)
    purity_pct = 83.5 + 5.5 * progress          # 83.5 at planting -> 89.0 at peak
    purity_frac = purity_pct / 100.0
    pol  = ccs / (1.022 - 0.292 / purity_frac)
    brix = pol / purity_frac

    pol_lo = pol - (margin * 0.85)
    pol_hi = pol + (margin * 0.85)

    return {
        "farm_id":               req.farm_id,
        "model":                 "SOTA-VotingEnsemble-ConformalBounds",
        "cv_accuracy_pct":       round(_SOTA_CV_ACCURACY, 2) if _SOTA_CV_ACCURACY else None,
        "features_used":         feature_vector,

        # Primary predictions
        "predicted_pol":         round(pol,  2),
        "predicted_brix":        round(brix, 2),
        "predicted_ccs":         round(ccs,  2),
        "predicted_purity":      round(purity_pct, 1),

        # 95% conformal uncertainty bounds
        "conformal_margin_95":   round(margin, 3),
        "pol_lower_95":          round(pol_lo,  2),
        "pol_upper_95":          round(pol_hi,  2),
        "ccs_lower_95":          round(ccs_lo,  2),
        "ccs_upper_95":          round(ccs_hi,  2),

        "source": "SOTA-AI-MODEL (Sentinel-2 L2A + Crop Age + Climate)"
    }


@app.post("/api/satellite/process_plot")
def process_plot_satellite_raster(req: PolygonRequest):
    coords = [list(map(float, p.split(","))) for p in req.polygon.split("#")]
    if len(coords) < 3:
        raise HTTPException(status_code=400, detail="Polygon must contain at least 3 coordinates.")

    raster_result = engine.fetch_real_sentinel2_l2a_raster(coords, req.date)

    if not raster_result.get("live_satellite", False):
        return {
            "live_satellite": False,
            "status": raster_result.get("status", "SIMULATION_MODE_OFFLINE"),
            "message": raster_result.get("message", "CDSE credentials not active. Simulation fallback mode."),
            "farm_id": req.farm_id,
            "valid_pixels": 0,
            "cells": []
        }

    cells = raster_result.get("cells", [])
    snapped = polygonize_cane_mask(cells, coords)

    return {
        "live_satellite":          True,
        "status":                  "LIVE_COPERNICUS_L2A",
        "farm_id":                 req.farm_id,
        "source":                  raster_result["source"],
        "acquisition_date":        raster_result.get("acquisition_date"),
        "product_id":              raster_result.get("product_id"),
        "valid_pixels":            raster_result["valid_cloud_free_pixels"],
        "invalid_pixels":          raster_result.get("invalid_masked_pixels", 0),
        "cloud_pct":               raster_result["cloud_contamination_pct"],
        "geojson":                 snapped.get("geojson"),
        "snapped_polygon":         snapped["snapped_polygon"],
        "detected_cane_acres":     snapped["standing_cane_acres"],
        "raw_classified_acres":    snapped.get("raw_classified_acres", snapped["standing_cane_acres"]),
        "smoothed_canopy_acres":   snapped.get("smoothed_canopy_acres", snapped["standing_cane_acres"]),
        "standing_fraction_pct":   snapped["standing_fraction_pct"],
        "clear_sky_coverage_pct":  snapped.get("clear_sky_coverage_pct", 100.0),
        "observed_cane_fraction_pct": snapped.get("observed_cane_fraction_pct", snapped["standing_fraction_pct"]),
        "cane_signature_score_mean":  snapped.get("cane_signature_score_mean", 0.0),
        "utm_zone":                snapped.get("utm_zone", "Zone 43N (EPSG:32643)"),
        "cells":                   cells
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
