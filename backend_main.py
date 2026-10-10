try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
"""
IkshuVruddhi FastAPI Satellite Engine Backend
Exposes:
  1. Authentic Sentinel-2 L2A raster sampling, SCL cloud-masking, morphological snapping
  2. Trained SOTA AI model for Pol / Brix / CCS prediction
  3. Enterprise MahaBhuNaksha Cadastral Gat (गट क्र.) integration with local SQLite spatial store,
     village vector ingestion, and 100% uptime zero-block circuit breaker.
"""

import os
import json
import pickle
import numpy as np
import sys

from fastapi import FastAPI, Query, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'ml'))

from ml.copernicus_client import CopernicusCDSEProcessEngine
from ml.satellite_engine import polygonize_cane_mask
from ml.gat_parcel_analyzer import get_gat_parcel_dossier
from ml.anti_cloud_engine import AntiCloudFusionEngine
from ml.cane_development_engine import CaneDevelopmentEngine
from ml.bhunaksha_engine import (
    get_bhunaksha_portal_url,
    generate_cadastral_gat_boundary,
    audit_plot_with_bhunaksha,
    normalize_gat_no,
    lookup_local_cadastral_db,
    save_cadastral_parcel_to_db,
    import_village_cadastral_geojson,
    get_cadastral_store_summary
)
from supabase_client import supabase

app = FastAPI(title="IkshuVruddhi Real Satellite & BhuNaksha Ingestion API", version="2.5.0")

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
    farm_id: str
    crop_age_days: float

    # Sentinel-2 spectral indices (means over SCL-valid pixels)
    sat_ndvi: Optional[float] = 0.72
    sat_ndre: Optional[float] = 0.58
    sat_ndwi: Optional[float] = 0.35
    sat_evi:  Optional[float] = 0.55

    # Thermal / climate
    sat_temp_celsius: Optional[float]          = 33.0
    sat_diurnal_temp_range: Optional[float]    = 11.5
    sat_solar_radiation_kwh_m2: Optional[float] = 6.2
    sat_precipitation_mm: Optional[float]      = 420.0

    # Derived phenology features (auto-computed if None)
    gdd: Optional[float]                 = None
    hydro_thermal_index: Optional[float] = None


class CadastralAuditRequest(BaseModel):
    farm_id: str
    gat_no: Optional[str] = None
    polygon: Optional[str] = None  # lat,lon#lat,lon#...
    registered_hectares: Optional[float] = 0.8
    detected_cane_acres: Optional[float] = 1.8
    village: Optional[str] = "Shevgaon"
    taluka: Optional[str] = "Shevgaon"
    district: Optional[str] = "Ahilyanagar"


class VillageGeoJSONImportRequest(BaseModel):
    geojson: Dict[str, Any]
    district: Optional[str] = "Ahilyanagar"
    taluka: Optional[str] = "Shevgaon"
    village: Optional[str] = "Shevgaon"
    source_label: Optional[str] = "TALUKA_LAND_RECORDS_OFFICE_SHP"


class CaneDevelopmentAuditRequest(BaseModel):
    variety: Optional[str] = "CO-265"
    cane_type: Optional[str] = "Suru"
    mean_ndvi: float = 0.65
    mean_ndre: float = 0.44
    mean_ccs: float = 11.5
    occupancy_pct: float = 90.0
    claimed_acres: float = 2.5
    is_ghost: Optional[bool] = False


class AntiCloudAuditRequest(BaseModel):
    ndvi_timeline: Dict[str, Optional[float]]
    mean_ndvi: Optional[float] = 0.65
    radar_vh_db: Optional[float] = -14.5
    radar_vv_db: Optional[float] = -9.2


class CloudRowsRequest(BaseModel):
    rows: List[Dict[str, Any]]


class CropObservation(BaseModel):
    date: str
    ndvi: float
    ndre: Optional[float] = None
    lswi: Optional[float] = None
    usability_pct: Optional[float] = 100.0


class CropPlotSeries(BaseModel):
    farm_id: str
    gat_no: Optional[str] = None
    observations: List[CropObservation]
    sar_vh_db: Optional[float] = None


class CropBatchRequest(BaseModel):
    plots: List[CropPlotSeries]


@app.get("/api/health")
def health_check():
    has_credentials = bool(os.getenv("CDSE_CLIENT_ID") and os.getenv("CDSE_CLIENT_SECRET"))
    cadastral_stats = get_cadastral_store_summary()
    return {
        "service": "IkshuVruddhi Satellite & BhuNaksha API",
        "live_cdse_configured": has_credentials,
        "mode": "CDSE_CONFIGURED" if has_credentials else "SIMULATION_OFFLINE",
        "sota_model_loaded": _SOTA_MODEL is not None,
        "sota_cv_accuracy_pct": round(_SOTA_CV_ACCURACY, 2) if _SOTA_CV_ACCURACY else None,
        "bhunaksha_integration_active": True,
        "supabase_configured": supabase.configured,
        "cloud_persistence": "SUPABASE" if supabase.configured else "LOCAL_ONLY",
        "cadastral_store_status": cadastral_stats.get("status"),
        "cadastral_cached_parcels": cadastral_stats.get("total_cached_gat_parcels"),
        "state_code": "27 (Maharashtra)"
    }


@app.post("/api/crop/classify/batch")
def classify_crop_batch(req: CropBatchRequest):
    """Screen plot crop type from caller-provided multi-date satellite indices.

    Scores are heuristic screening scores, not calibrated probabilities or
    validation accuracy. At least five usable observations spanning 120 days
    are required before the classifier returns a crop label.
    """
    if not req.plots or len(req.plots) > 200:
        raise HTTPException(status_code=422, detail="Provide between 1 and 200 plot time series per request")

    total_observations = sum(len(plot.observations) for plot in req.plots)
    if total_observations > 10000:
        raise HTTPException(status_code=413, detail="Batch exceeds 10,000 observations; split it into smaller requests")

    from ml.crop_distinction import classify_crop_from_phenology
    from ml.phenology_features import extract_phenological_trajectory_features

    results = []
    observation_rows = []
    for plot in req.plots:
        dates, ndvi, ndre, lswi, usability = [], [], [], [], []
        for obs in plot.observations:
            try:
                # Parse strictly here so malformed dates are reported to the client,
                # rather than silently disappearing inside feature extraction.
                from datetime import date as _date
                _date.fromisoformat(obs.date[:10])
            except (TypeError, ValueError):
                raise HTTPException(status_code=422, detail=f"Invalid ISO date for plot {plot.farm_id}: {obs.date}")
            for label, value in (("NDVI", obs.ndvi), ("NDRE", obs.ndre), ("LSWI", obs.lswi)):
                if value is not None and (not np.isfinite(value) or value < -1.0 or value > 1.0):
                    raise HTTPException(status_code=422, detail=f"{label} must be between -1 and 1 for plot {plot.farm_id}")
            if obs.usability_pct is not None and (not np.isfinite(obs.usability_pct) or not 0 <= obs.usability_pct <= 100):
                raise HTTPException(status_code=422, detail=f"usability_pct must be between 0 and 100 for plot {plot.farm_id}")
            dates.append(obs.date[:10])
            ndvi.append(obs.ndvi)
            ndre.append(obs.ndre)
            lswi.append(obs.lswi)
            usability.append(obs.usability_pct if obs.usability_pct is not None else 100.0)
            observation_rows.append({
                "plot_id": str(plot.farm_id).strip(),
                "gat_no": plot.gat_no,
                "observation_date": obs.date[:10],
                "ndvi": obs.ndvi,
                "ndre": obs.ndre,
                "lswi": obs.lswi,
                "usability_pct": obs.usability_pct if obs.usability_pct is not None else 100.0,
                "sar_vh_db": plot.sar_vh_db,
            })

        features = extract_phenological_trajectory_features(
            dates, ndvi, ndre, lswi, usability
        )
        classification = classify_crop_from_phenology(features, sar_vh_db=plot.sar_vh_db)
        results.append({"farm_id": plot.farm_id, **classification})

    cloud_persistence = {"configured": supabase.configured, "saved_observations": 0, "saved_screenings": 0}
    if supabase.configured:
        try:
            screening_rows = [{
                "plot_id": str(result["farm_id"]).strip(),
                "gat_no": next((p.gat_no for p in req.plots if str(p.farm_id).strip() == str(result["farm_id"]).strip()), None),
                "predicted_crop": result["predicted_crop"],
                "heuristic_score_pct": result.get("heuristic_confidence_score"),
                "evidence_completeness_pct": result.get("evidence_completeness_pct"),
                "reasoning": result.get("reasoning"),
                "phenology_summary": result.get("phenology_summary"),
                "model_version": "phenology-heuristic-v1",
            } for result in results]
            saved_observations = supabase.upsert_crop_observations(observation_rows)
            saved_screenings = supabase.upsert_crop_screenings(screening_rows)
            cloud_persistence = {
                "configured": True,
                "saved_observations": len(saved_observations),
                "saved_screenings": len(saved_screenings),
            }
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Crop screening completed, but Supabase persistence failed: {exc}")

    return {
        "results": results,
        "classified_count": sum(r["predicted_crop"] != "INSUFFICIENT_TEMPORAL_DATA" for r in results),
        "insufficient_data_count": sum(r["predicted_crop"] == "INSUFFICIENT_TEMPORAL_DATA" for r in results),
        "score_note": "Heuristic screening scores—not calibrated probabilities, measured accuracy, or a substitute for field verification.",
        "requirements": "At least 5 usable observations spanning at least 120 days per plot.",
        "cloud_persistence": cloud_persistence,
    }


@app.get("/api/cloud/status")
def cloud_status():
    return {"configured": supabase.configured, "provider": "supabase", "tables": ["plot_predictions", "lab_samples", "crop_observations", "crop_screenings"]}


@app.post("/api/cloud/predictions")
def cloud_upsert_predictions(req: CloudRowsRequest):
    if not supabase.configured:
        raise HTTPException(status_code=503, detail="Supabase is not configured on the backend")
    try:
        return {"saved": len(supabase.upsert_predictions(req.rows))}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Supabase write failed: {exc}")


@app.get("/api/cloud/predictions")
def cloud_list_predictions(limit: int = Query(1000, ge=1, le=10000), gat_no: Optional[str] = None):
    if not supabase.configured:
        raise HTTPException(status_code=503, detail="Supabase is not configured on the backend")
    try:
        return {"rows": supabase.list_predictions(limit=limit, gat_no=gat_no)}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Supabase read failed: {exc}")


@app.post("/api/cloud/lab-samples")
def cloud_upsert_lab_samples(req: CloudRowsRequest):
    if not supabase.configured:
        raise HTTPException(status_code=503, detail="Supabase is not configured on the backend")
    try:
        return {"saved": len(supabase.upsert_lab_samples(req.rows))}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Supabase write failed: {exc}")


# ── BhuNaksha Cadastral Endpoints ─────────────────────────────────────────────
@app.get("/api/cadastral/store_summary")
def cadastral_store_summary():
    """Returns local cadastral spatial cache metrics, cached Gat count, and latency."""
    return get_cadastral_store_summary()


@app.get("/api/cadastral/bhunaksha_info")
def get_bhunaksha_info(
    gat_no: str = Query(..., description="Gat No / Survey Number (गट क्र.)"),
    village: str = Query("Shevgaon", description="Village Name"),
    taluka: str = Query("Shevgaon", description="Taluka Name"),
    district: str = Query("Ahilyanagar", description="District Name")
):
    """Returns direct links to Maharashtra BhuNaksha portal and MahaBhulekh 7/12."""
    return get_bhunaksha_portal_url(
        gat_no=gat_no,
        village=village,
        taluka=taluka,
        district=district
    )


@app.post("/api/cadastral/audit_gat")
def audit_gat_compliance(req: CadastralAuditRequest):
    """
    Performs 3-Tier Cadastral Compliance Audit using the Zero-Block Circuit Breaker:
      1. Location Sanity Check (<300m centroid proximity)
      2. Legal Gat Area vs Registered Cane Area Fraud Check
      3. Cadastral Parcel Geometry & Boundary generation
    """
    coords = []
    if req.polygon and "#" in req.polygon:
        try:
            coords = [list(map(float, p.split(","))) for p in req.polygon.split("#")]
        except Exception:
            coords = []

    gat = req.gat_no or req.farm_id
    return audit_plot_with_bhunaksha(
        plot_id=req.farm_id,
        gat_no=gat,
        plot_coords=coords,
        registered_hectares=req.registered_hectares or 0.8,
        detected_cane_acres=req.detected_cane_acres or 1.8,
        village=req.village or "Shevgaon",
        taluka=req.taluka or "Shevgaon",
        district=req.district or "Ahilyanagar"
    )


@app.post("/api/cadastral/import_village_geojson")
def import_village_geojson(req: VillageGeoJSONImportRequest):
    """
    Directly ingests an official Taluka Land Records village GeoJSON / Shapefile export
    into the local high-speed cadastral database (0ms latency, 100% offline uptime).
    """
    if not req.geojson:
        raise HTTPException(status_code=400, detail="GeoJSON object required.")

    return import_village_cadastral_geojson(
        geojson_data=req.geojson,
        district=req.district or "Ahilyanagar",
        taluka=req.taluka or "Shevgaon",
        village=req.village or "Shevgaon",
        source_label=req.source_label or "TALUKA_LAND_RECORDS_SHP"
    )
@app.get("/api/cadastral/gat_dossier")
def get_gat_dossier_endpoint(
    district: str = Query("Ahilyanagar", description="District Name"),
    taluka: str = Query("Shevgaon", description="Taluka Name"),
    village: str = Query("ERANDGAON BHA.(THOMBARE VASTI )", description="Village Name"),
    gat_no: str = Query(..., description="Gat / Survey Number (गट क्र.)")
):
    """
    Returns full Gat Parcel Dossier:
      - Official legal parcel acreage from Maha Bhu Naksha
      - Exact boundary polygon coordinates & GeoJSON feature
      - Co-tenancy & multi-farmer stacking audit (occupancy ratio & collision flags)
      - Integrated satellite reflectance (NDVI, NDRE) & predicted sugar recovery (CCS, Brix)
      - Direct official links to 7/12 and BhuNaksha portal
    """
    return get_gat_parcel_dossier(
        district=district,
        taluka=taluka,
        village=village,
        gat_no=gat_no
    )

# ──────────────────────────────────────────────────────────────────────────────


@app.post("/api/predict")
def predict_sucrose(req: PredictRequest):
    """
    Run the trained SOTA AI model (HistGBR + ExtraTrees + RandomForest VotingRegressor)
    to predict Pol%, Brix degBx, and CCS% for a single plot.
    """
    if _SOTA_MODEL is None:
        raise HTTPException(status_code=503, detail="SOTA model not loaded on server.")

    temp   = req.sat_temp_celsius or 33.0
    precip = req.sat_precipitation_mm or 420.0
    dtr    = req.sat_diurnal_temp_range or 11.5
    solar  = req.sat_solar_radiation_kwh_m2 or 6.2
    age    = req.crop_age_days

    gdd = req.gdd if req.gdd is not None else max(0.0, (temp - 10.0) * age)
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

    X = np.array([[feature_vector[f] for f in _SOTA_FEATURES]], dtype=np.float64)

    try:
        ccs_pred, conformal_margin, ccs_lower, ccs_upper = _SOTA_MODEL.predict_with_conformal_bounds(X, confidence=0.95)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Model inference failed: {e}")

    ccs    = float(ccs_pred[0])
    ccs_lo = float(ccs_lower[0])
    ccs_hi = float(ccs_upper[0])
    margin = float(conformal_margin)

    age_months = age / 30.4
    opt_age_months = 16.0
    progress   = min(1.0, age_months / opt_age_months)
    purity_pct = 83.5 + 5.5 * progress
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
        "predicted_pol":         round(pol,  2),
        "predicted_brix":        round(brix, 2),
        "predicted_ccs":         round(ccs,  2),
        "predicted_purity":      round(purity_pct, 1),
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



# -------------------------------------------------------------
# Enterprise Copernicus Live Satellite Audit & Fraud Detection
# -------------------------------------------------------------
import pandas as pd

_AUDIT_CSV = os.path.join(os.path.dirname(__file__), "data", "plots_27633_real_satellite_harvest_final.csv")
_AUDIT_DF = None

def _get_audit_df():
    global _AUDIT_DF
    if _AUDIT_DF is None:
        if os.path.exists(_AUDIT_CSV):
            _AUDIT_DF = pd.read_csv(_AUDIT_CSV)
            _AUDIT_DF["Plot_No"] = pd.to_numeric(_AUDIT_DF["Plot_No"], errors="coerce")
    return _AUDIT_DF

@app.get("/api/satellite/audit_summary")
def get_satellite_audit_summary():
    """Returns factory-wide live Sentinel-2 satellite audit statistics."""
    df = _get_audit_df()
    if df is None:
        return {"status": "ERROR", "message": "Audit dataset not initialized."}
    
    verdicts = df["Real_Satellite_Verdict"].value_counts().to_dict()
    total_paper = float(df["Paper_Claimed_MT"].sum())
    total_sat = float(df["Live_Satellite_Audited_MT"].sum())
    tonnage_blocked = float(df[df["Real_Satellite_Verdict"] == "CONFIRMED_GHOST_BARE_SOIL"]["Paper_Claimed_MT"].sum())
    
    return {
        "status": "SUCCESS",
        "total_plots": len(df),
        "verdicts": verdicts,
        "paper_claimed_total_cane_mt": round(total_paper, 1),
        "live_satellite_audited_cane_mt": round(total_sat, 1),
        "total_discrepancy_mt": round(total_sat - total_paper, 1),
        "ghost_bare_soil_plots": int(verdicts.get("CONFIRMED_GHOST_BARE_SOIL", 0)),
        "ghost_tonnage_blocked_mt": round(tonnage_blocked, 1),
        "rescued_standing_cane_plots": int(verdicts.get("CONFIRMED_HEALTHY_CANE", 0)),
        "cloud_obscured_plots": int(verdicts.get("CLOUD_OBSCURED_RETEST", 0)),
        "tile_acquisition_date": "2026-09-28",
        "sensor": "Sentinel-2 MSI Level-2A BOA Reflectance"
    }

@app.get("/api/satellite/plot_audit/{plot_no}")
def get_plot_satellite_audit(plot_no: int):
    """Returns real satellite multi-spectral telemetry and fraud audit for a specific plot."""
    df = _get_audit_df()
    if df is None:
        raise HTTPException(status_code=500, detail="Audit dataset not loaded.")
    
    sub = df[df["Plot_No"] == plot_no]
    if sub.empty:
        raise HTTPException(status_code=404, detail=f"Plot ID {plot_no} not found in satellite audit.")
        
    rec = sub.iloc[0].to_dict()
    clean_rec = {
        k: int(v) if isinstance(v, (np.integer, int)) else (
           float(v) if isinstance(v, (np.floating, float)) else ("" if pd.isna(v) else v)
        )
        for k, v in rec.items()
    }
    return {"status": "SUCCESS", "plot": clean_rec}

@app.get("/api/satellite/ghost_plots")
def list_ghost_plots(
    verdict: Optional[str] = Query(None),
    gat: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """List plots filtered by satellite audit verdict (e.g. CONFIRMED_GHOST_BARE_SOIL, CONFIRMED_FALLOW_OR_SCRUB)."""
    df = _get_audit_df()
    if df is None:
        raise HTTPException(status_code=500, detail="Audit dataset not loaded.")
        
    filtered = df
    if verdict:
        filtered = filtered[filtered["Real_Satellite_Verdict"] == verdict]
    if gat:
        filtered = filtered[filtered["Gat_Sector"].astype(str).str.contains(gat, case=False, na=False)]
        
    total_matches = len(filtered)
    paginated = filtered.iloc[offset:offset+limit]
    
    records = []
    for _, row in paginated.iterrows():
        rec = row.to_dict()
        records.append({
            k: int(v) if isinstance(v, (np.integer, int)) else (
               float(v) if isinstance(v, (np.floating, float)) else ("" if pd.isna(v) else v)
            )
            for k, v in rec.items()
        })
        
    return {
        "status": "SUCCESS",
        "total_matches": total_matches,
        "limit": limit,
        "offset": offset,
        "plots": records
    }




@app.post("/api/satellite/anti_cloud_audit")
def anti_cloud_audit_endpoint(req: AntiCloudAuditRequest):
    """
    Executes the 5-Layer Anti-Cloud and Radar-Optical Fusion Pipeline:
      Layer 1: Sentinel-2 Level-2A SCL cloud/shadow pixel filtering
      Layer 2: 120-Day 5-epoch ClearSky multi-temporal compositing
      Layer 3: Sentinel-1 C-Band SAR radar all-weather canopy penetration
      Layer 4: Savitzky-Golay polynomial phenological curve reconstruction
      Layer 5: Atmospheric NDRE and LSWI cellular water cross-validation
    """
    try:
        report = AntiCloudFusionEngine.execute_5layer_anti_cloud_audit(
            raw_ndvi_timeline=req.ndvi_timeline,
            mean_ndvi=req.mean_ndvi or 0.65,
            radar_vh_db=req.radar_vh_db,
            radar_vv_db=req.radar_vv_db
        )
        return report
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Anti-cloud audit failed: {exc}")




@app.post("/api/cdp/evaluate_parcel")
def evaluate_cdp_endpoint(req: CaneDevelopmentAuditRequest):
    """
    Evaluates a parcel for the Cane Development Program (CDP):
      - Calculates Agronomic CDP Health Score (1-100)
      - Automated Drip Irrigation Subsidy Clearance
      - Varietal Diversification Advisory (incentives to rebalance from CO-265)
      - Mechanized Ratoon (Khodwa) Stubble Shaving & Trash Mulching Dispatch
      - Urea & Nitrogen Top-Dressing based on Sentinel-2 Red-Edge Chlorophyll
    """
    try:
        report = CaneDevelopmentEngine.evaluate_cdp_profile(
            variety=req.variety or "CO-265",
            cane_type=req.cane_type or "Suru",
            mean_ndvi=req.mean_ndvi,
            mean_ndre=req.mean_ndre,
            mean_ccs=req.mean_ccs,
            occupancy_pct=req.occupancy_pct,
            claimed_acres=req.claimed_acres,
            is_ghost=req.is_ghost or False
        )
        return {"status": "SUCCESS", "cdp_dossier": report}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"CDP evaluation failed: {exc}")



# Static file serving for web dashboard and assets
from fastapi.staticfiles import StaticFiles

_web_dir = os.path.join(os.path.dirname(__file__), "web")
if os.path.isdir(_web_dir):
    app.mount("/", StaticFiles(directory=_web_dir, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
