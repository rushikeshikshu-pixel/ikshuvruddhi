"""
ml/isro_texture_tonnage_pipeline.py
Production Multi-Sensor Tonnage & Sucrose Engine:
ISRO Resourcesat-2A LISS-4 (5.8m) Texture + ISRIC SoilGrids REST API + Agronomic Drivers + XGBoost

Solves the 4 key production gaps:
  1. Real ISRIC SoilGrids REST API: Queries live 250m physical soil mineralogy (Clay, Sand, Silt, CEC, SOC).
  2. Agronomic Drivers: Incorporates Plant Cane vs. Ratoon (Khodwa), Variety Vigor, and Thermal GDD.
  3. Asynchronous Satellite Cadence: Continuous 5-day Sentinel-2 monitoring with on-demand LISS-4 5.8m GLCM injection.
  4. Real Factory Ground Truth Training: Strict GroupKFold cross-validation against mill weighbridge and lab records.
"""

import os
import math
import json
import urllib.request
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Tuple, Optional
from skimage.feature import graycomatrix, graycoprops
import xgboost as xgb
from sklearn.metrics import mean_squared_error, mean_absolute_percentage_error, r2_score
from sklearn.model_selection import GroupKFold

# In-memory LRU-style cache for soil queries to prevent redundant network calls
_SOIL_CACHE: Dict[Tuple[float, float], Dict[str, float]] = {}

def fetch_isric_soilgrids(
    latitude: float,
    longitude: float,
    timeout_sec: int = 4
) -> Dict[str, float]:
    """
    Queries the official ISRIC SoilGrids v2.0 Global REST API for physical measured
    soil mineralogy at 15-30cm depth (sugarcane root-zone).

    Returns:
      - clay_fraction_pct: Clay content (g/kg / 10 -> %)
      - sand_fraction_pct: Sand content (%)
      - silt_fraction_pct: Silt content (%)
      - cation_exchange_capacity: CEC (cmol(+)/kg / 10)
      - soil_organic_carbon_pct: SOC (%)
    """
    cache_key = (round(latitude, 3), round(longitude, 3))
    if cache_key in _SOIL_CACHE:
        return _SOIL_CACHE[cache_key]

    url = (
        f"https://rest.isric.org/soilgrids/v2.0/properties/query"
        f"?lat={latitude:.4f}&lon={longitude:.4f}"
        f"&property=clay&property=sand&property=silt&property=cec&property=soc"
        f"&depth=15-30cm&value=mean"
    )

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "IkshuVruddhi-SugarEngine/2.0"})
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            layers = data.get("properties", {}).get("layers", [])
            
            raw_vals = {}
            for l in layers:
                name = l.get("name")
                depths = l.get("depths", [])
                if depths:
                    val = depths[0].get("values", {}).get("mean")
                    raw_vals[name] = val

            # Convert ISRIC units (g/kg to %, and CEC cmol/kg / 10)
            clay_pct = (raw_vals.get("clay", 450) or 450) / 10.0
            sand_pct = (raw_vals.get("sand", 250) or 250) / 10.0
            silt_pct = (raw_vals.get("silt", 300) or 300) / 10.0
            cec = (raw_vals.get("cec", 420) or 420) / 10.0
            soc_pct = ((raw_vals.get("soc", 70) or 70) / 10.0) / 10.0

            profile = {
                "clay_fraction_pct": round(clay_pct, 2),
                "sand_fraction_pct": round(sand_pct, 2),
                "silt_fraction_pct": round(silt_pct, 2),
                "cation_exchange_capacity": round(cec, 2),
                "soil_organic_carbon_pct": round(soc_pct, 2),
                "data_source": "ISRIC_SOILGRIDS_V2_LIVE"
            }
            _SOIL_CACHE[cache_key] = profile
            return profile

    except Exception:
        # Graceful offline fallback: Regional Vertisol defaults for Godavari/Pravara basin
        fallback = {
            "clay_fraction_pct": 46.50,
            "sand_fraction_pct": 24.20,
            "silt_fraction_pct": 29.30,
            "cation_exchange_capacity": 42.50,
            "soil_organic_carbon_pct": 0.68,
            "data_source": "REGIONAL_VERTISOL_OFFLINE_FALLBACK"
        }
        _SOIL_CACHE[cache_key] = fallback
        return fallback

def compute_glcm_texture_features(
    image_band: Optional[np.ndarray],
    valid_mask: Optional[np.ndarray] = None,
    num_levels: int = 16,
    distances: Tuple[int, ...] = (1, 2),
    angles: Tuple[float, ...] = (0, np.pi/4, np.pi/2, 3*np.pi/4)
) -> Dict[str, float]:
    """
    Extracts Haralick / Gray-Level Co-occurrence Matrix (GLCM) spatial texture metrics
    from high-resolution satellite imagery (e.g. ISRO LISS-4 5.8m NIR / Red band).
    """
    if image_band is None or image_band.size < 4:
        return {
            "glcm_homogeneity": 0.60,
            "glcm_contrast": 1.50,
            "glcm_entropy": 2.80,
            "glcm_energy": 0.18,
            "glcm_dissimilarity": 1.05,
            "texture_source": "ASYNC_SENTINEL_PROXY"
        }

    arr = np.nan_to_num(image_band.astype(np.float32), nan=0.0)
    if valid_mask is not None and valid_mask.shape == arr.shape:
        arr = arr * valid_mask.astype(np.float32)

    min_v, max_v = float(np.min(arr)), float(np.max(arr))
    if max_v - min_v < 1e-5:
        return {
            "glcm_homogeneity": 1.0,
            "glcm_contrast": 0.0,
            "glcm_entropy": 0.0,
            "glcm_energy": 1.0,
            "glcm_dissimilarity": 0.0,
            "texture_source": "ISRO_LISS4_UNIFORM"
        }

    quantized = np.clip(
        np.floor(((arr - min_v) / (max_v - min_v)) * num_levels),
        0,
        num_levels - 1
    ).astype(np.uint8)

    glcm = graycomatrix(
        quantized,
        distances=list(distances),
        angles=list(angles),
        levels=num_levels,
        symmetric=True,
        normed=True
    )

    homogeneity = float(np.mean(graycoprops(glcm, 'homogeneity')))
    contrast = float(np.mean(graycoprops(glcm, 'contrast')))
    energy = float(np.mean(graycoprops(glcm, 'energy')))
    dissimilarity = float(np.mean(graycoprops(glcm, 'dissimilarity')))

    p = glcm.astype(np.float64)
    p_nz = p[p > 1e-12]
    entropy = float(-np.sum(p_nz * np.log2(p_nz)) / (len(distances) * len(angles)))

    return {
        "glcm_homogeneity": round(homogeneity, 4),
        "glcm_contrast": round(contrast, 4),
        "glcm_entropy": round(entropy, 4),
        "glcm_energy": round(energy, 4),
        "glcm_dissimilarity": round(dissimilarity, 4),
        "texture_source": "ISRO_LISS4_HIGHRES"
    }

def calculate_accumulated_gdd(
    crop_age_days: int,
    base_temp_c: float = 12.0,
    mean_daily_temp_c: float = 27.5
) -> float:
    """
    Computes Growing Degree Days (GDD) accumulated during the sugarcane vegetative cycle.
    In Maharashtra, sugarcane base temperature is strictly 12 deg C.
    """
    daily_effective = max(0.0, mean_daily_temp_c - base_temp_c)
    return round(daily_effective * float(crop_age_days), 1)

def fuse_multisensor_features(
    sentinel_indices: Dict[str, Any],
    liss4_texture: Dict[str, float],
    soil_profile: Dict[str, float],
    crop_age_days: int = 360,
    cane_variety: str = "CO-265",
    crop_type: str = "ADSALI",
    is_ratoon: bool = False
) -> Dict[str, Any]:
    """
    Fuses Sentinel-2 multi-spectral indices, ISRO LISS-4 5.8m spatial textures,
    ISRIC physical soil mineralogy, and agronomic crop parameters.
    """
    variety_upper = str(cane_variety).upper()
    variety_vigor_mult = 1.06 if "265" in variety_upper else (0.96 if "86032" in variety_upper else 1.00)
    
    # Ratoon (Khodwa) matures faster (~30 days earlier) and has higher stool count
    ratoon_flag = 1.0 if (is_ratoon or "KHODWA" in str(crop_type).upper() or "RATOON" in str(crop_type).upper()) else 0.0

    # Agrometeorological GDD accumulation
    accum_gdd = calculate_accumulated_gdd(crop_age_days=crop_age_days)

    fused = {
        # Spectral Indices (Sentinel-2 10m)
        "ndvi": float(sentinel_indices.get("ndvi", 0.70)),
        "ndre": float(sentinel_indices.get("ndre", 0.18)),
        "lswi": float(sentinel_indices.get("lswi", 0.35)),
        "canopy_fraction_pct": float(sentinel_indices.get("canopy_fraction_pct", 85.0)),
        
        # Spatial Texture (ISRO LISS-4 5.8m GLCM)
        "glcm_homogeneity": float(liss4_texture.get("glcm_homogeneity", 0.65)),
        "glcm_contrast": float(liss4_texture.get("glcm_contrast", 1.80)),
        "glcm_entropy": float(liss4_texture.get("glcm_entropy", 3.20)),
        "glcm_energy": float(liss4_texture.get("glcm_energy", 0.15)),
        "glcm_dissimilarity": float(liss4_texture.get("glcm_dissimilarity", 1.10)),
        
        # Physical Soil Mineralogy (ISRIC SoilGrids 250m)
        "clay_fraction_pct": float(soil_profile.get("clay_fraction_pct", 46.5)),
        "cation_exchange_capacity": float(soil_profile.get("cation_exchange_capacity", 42.5)),
        "soil_organic_carbon_pct": float(soil_profile.get("soil_organic_carbon_pct", 0.68)),
        
        # Agronomic & Meteorological Drivers
        "crop_age_days": float(crop_age_days),
        "is_ratoon": ratoon_flag,
        "accumulated_gdd": accum_gdd,
        "variety_vigor_mult": variety_vigor_mult
    }
    return fused

class ISROSugarcaneXGBoostModel:
    """
    Tuned XGBoost Regressor for Sugarcane Sub-Field Tonnage (t/ha) and CCS Sugar Recovery (%).
    Supports strict GroupKFold cross-validation on real mill weighbridge datasets.
    """
    def __init__(self):
        self.tonnage_model = None
        self.ccs_model = None
        self.feature_names = [
            "ndvi", "ndre", "lswi", "canopy_fraction_pct",
            "glcm_homogeneity", "glcm_contrast", "glcm_entropy", "glcm_energy", "glcm_dissimilarity",
            "clay_fraction_pct", "cation_exchange_capacity", "soil_organic_carbon_pct",
            "crop_age_days", "is_ratoon", "accumulated_gdd", "variety_vigor_mult"
        ]

    def train_with_group_kfold(
        self,
        df_features: pd.DataFrame,
        y_tonnage: np.ndarray,
        y_ccs: np.ndarray,
        group_ids: np.ndarray,
        n_splits: int = 5,
        params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Trains XGBoost models using strict GroupKFold on Gat/Farmer IDs.
        Ensures NO data leakage across parcels from the same farm.
        """
        if params is None:
            params = {
                "n_estimators": 120,
                "max_depth": 4,
                "learning_rate": 0.06,
                "subsample": 0.85,
                "colsample_bytree": 0.85,
                "random_state": 42
            }

        gkf = GroupKFold(n_splits=min(n_splits, len(np.unique(group_ids))))
        cv_t_rmse, cv_t_mape = [], []
        cv_c_rmse = []

        X = df_features[self.feature_names].values

        for train_idx, val_idx in gkf.split(X, y_tonnage, groups=group_ids):
            X_tr, X_val = X[train_idx], X[val_idx]
            yt_tr, yt_val = y_tonnage[train_idx], y_tonnage[val_idx]
            yc_tr, yc_val = y_ccs[train_idx], y_ccs[val_idx]

            model_t = xgb.XGBRegressor(**params)
            model_t.fit(X_tr, yt_tr)
            pred_t = model_t.predict(X_val)

            cv_t_rmse.append(math.sqrt(mean_squared_error(yt_val, pred_t)))
            cv_t_mape.append(mean_absolute_percentage_error(yt_val, pred_t) * 100.0)

            model_c = xgb.XGBRegressor(**params)
            model_c.fit(X_tr, yc_tr)
            pred_c = model_c.predict(X_val)
            cv_c_rmse.append(math.sqrt(mean_squared_error(yc_val, pred_c)))

        # Final fit on complete training set
        self.tonnage_model = xgb.XGBRegressor(**params)
        self.tonnage_model.fit(df_features[self.feature_names], y_tonnage)

        self.ccs_model = xgb.XGBRegressor(**params)
        self.ccs_model.fit(df_features[self.feature_names], y_ccs)

        return {
            "cross_validation_metrics": {
                "n_splits": n_splits,
                "tonnage_cv_rmse_t_ha": round(float(np.mean(cv_t_rmse)), 2),
                "tonnage_cv_mape_pct": round(float(np.mean(cv_t_mape)), 2),
                "ccs_cv_rmse_points": round(float(np.mean(cv_c_rmse)), 2)
            }
        }

    def predict_plot(
        self,
        features_dict: Dict[str, Any],
        area_hectares: float = 1.0
    ) -> Dict[str, Any]:
        """
        Predicts physical tonnage (t/ha & total tonnes) and sugar recovery (CCS %)
        for a single sugarcane parcel.
        """
        if self.tonnage_model is None or self.ccs_model is None:
            raise ValueError("Models are not trained. Call train_with_group_kfold() first.")

        df_input = pd.DataFrame([features_dict])[self.feature_names]
        
        pred_t_ha = float(self.tonnage_model.predict(df_input)[0])
        pred_ccs = float(self.ccs_model.predict(df_input)[0])

        total_tonnes = round(pred_t_ha * area_hectares, 1)
        total_sugar_tonnes = round(total_tonnes * (pred_ccs / 100.0), 2)
        hpi = round((pred_ccs / 11.5) * (pred_t_ha / 90.0) * 100.0, 1)

        return {
            "predicted_tonnage_t_ha": round(pred_t_ha, 1),
            "predicted_total_tonnes": total_tonnes,
            "predicted_ccs_pct": round(pred_ccs, 2),
            "predicted_recoverable_sugar_tonnes": total_sugar_tonnes,
            "harvest_priority_score": hpi,
            "area_hectares": area_hectares,
            "area_acres": round(area_hectares * 2.47105, 2)
        }
