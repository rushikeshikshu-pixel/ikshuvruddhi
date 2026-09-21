"""
ml/isro_texture_tonnage_pipeline.py
Production Multi-Sensor Tonnage & Sucrose Engine:
ISRO LISS-4 (5.8m) / Sentinel-2 (10m) Texture + ISRIC SoilGrids + Dynamic Agrometeorological GDD + XGBoost
"""

import os
import math
import json
import urllib.request
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Tuple, Optional
from skimage.feature import graycomatrix, graycoprops
import xgboost as xgb
from sklearn.metrics import mean_squared_error, mean_absolute_percentage_error, r2_score
from sklearn.model_selection import GroupKFold

_SOIL_CACHE: Dict[Tuple[float, float], Dict[str, float]] = {}

def fetch_isric_soilgrids(
    latitude: float,
    longitude: float,
    timeout_sec: int = 15,
    allow_fallback: bool = True
) -> Dict[str, float]:
    """
    Queries the official ISRIC SoilGrids v2.0 Global REST API for physical measured
    soil mineralogy at 15-30cm depth (sugarcane root-zone).
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

            clay_pct = (raw_vals.get("clay") or 450) / 10.0
            sand_pct = (raw_vals.get("sand") or 250) / 10.0
            silt_pct = (raw_vals.get("silt") or 300) / 10.0
            cec = (raw_vals.get("cec") or 420) / 10.0
            soc_pct = ((raw_vals.get("soc") or 70) / 10.0) / 10.0

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

    except Exception as e:
        if not allow_fallback:
            raise ConnectionError(f"ISRIC SoilGrids live query failed: {e}")
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
    source_name: str = "ISRO_LISS4_5.8M",
    num_levels: int = 16,
    distances: Tuple[int, ...] = (1, 2),
    angles: Tuple[float, ...] = (0, np.pi/4, np.pi/2, 3*np.pi/4)
) -> Dict[str, Any]:
    """
    Extracts Haralick / Gray-Level Co-occurrence Matrix (GLCM) spatial texture metrics.
    Works natively on:
      1. ISRO LISS-4 (5.8m high-resolution)
      2. Sentinel-2 B08 (10m) when LISS-4 is unavailable
    """
    if image_band is None or image_band.size < 4:
        return {
            "glcm_homogeneity": np.nan,
            "glcm_contrast": np.nan,
            "glcm_entropy": np.nan,
            "glcm_energy": np.nan,
            "glcm_dissimilarity": np.nan,
            "texture_source": "MISSING_OBSERVATION",
            "texture_valid": False
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
            "texture_source": source_name,
            "texture_valid": True
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
        "texture_source": source_name,
        "texture_valid": True
    }

def calculate_historical_weather_gdd(
    latitude: float,
    longitude: float,
    planting_date_str: str,
    harvest_date_str: Optional[str] = None,
    base_temp_c: float = 12.0
) -> Dict[str, float]:
    """
    Integrates actual daily temperature series to compute dynamic GDD:
      GDD = sum_d max(0, (Tmax,d + Tmin,d)/2 - Tbase)
    Also computes thermal stress days (Tmax > 40 C) and winter slowdown days (Tmean < 18 C).
    """
    try:
        p_dt = datetime.strptime(planting_date_str, "%Y-%m-%d")
    except Exception:
        p_dt = datetime.now() - timedelta(days=365)

    if harvest_date_str:
        try:
            h_dt = datetime.strptime(harvest_date_str, "%Y-%m-%d")
        except Exception:
            h_dt = datetime.now()
    else:
        h_dt = datetime.now()

    days_span = max(1, (h_dt - p_dt).days)

    # Fetch daily historical agrometeorology from Open-Meteo Archive API
    start_str = p_dt.strftime("%Y-%m-%d")
    end_str = min(h_dt, datetime.now()).strftime("%Y-%m-%d")

    url = (
        f"https://archive-api.open-meteo.com/v1/archive"
        f"?latitude={latitude:.4f}&longitude={longitude:.4f}"
        f"&start_date={start_str}&end_date={end_str}"
        f"&daily=temperature_2m_max,temperature_2m_min&timezone=auto"
    )

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "IkshuVruddhi-AgroWeather/2.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            w_data = json.loads(resp.read().decode("utf-8"))
            t_max_list = w_data.get("daily", {}).get("temperature_2m_max", [])
            t_min_list = w_data.get("daily", {}).get("temperature_2m_min", [])

            if t_max_list and t_min_list and len(t_max_list) == len(t_min_list):
                accum_gdd = 0.0
                extreme_heat_days = 0
                winter_slow_days = 0

                for tmax, tmin in zip(t_max_list, t_min_list):
                    if tmax is not None and tmin is not None:
                        tmean = (tmax + tmin) / 2.0
                        accum_gdd += max(0.0, tmean - base_temp_c)
                        if tmax >= 40.0:
                            extreme_heat_days += 1
                        if tmean < 18.0:
                            winter_slow_days += 1

                return {
                    "accumulated_gdd": round(accum_gdd, 1),
                    "extreme_heat_days": extreme_heat_days,
                    "winter_slowdown_days": winter_slow_days,
                    "gdd_source": "OPEN_METEO_HISTORICAL_DAILY"
                }
    except Exception:
        pass

    # Climatological monthly variation for Maharashtra Godavari basin (Shevgaon / Pravara)
    # Seasonal temperatures vary by month (May is hot ~34C, Dec/Jan is cool ~21C)
    accum_gdd = 0.0
    for day_i in range(days_span):
        curr_d = p_dt + timedelta(days=day_i)
        month = curr_d.month
        # Climatological monthly mean for Ahmednagar/Chhatrapati Sambhaji Nagar belt
        monthly_tmean = {
            1: 21.0, 2: 23.5, 3: 28.0, 4: 31.5, 5: 33.0, 6: 29.5,
            7: 26.5, 8: 25.5, 9: 26.5, 10: 26.0, 11: 23.0, 12: 20.5
        }.get(month, 26.0)
        accum_gdd += max(0.0, monthly_tmean - base_temp_c)

    return {
        "accumulated_gdd": round(accum_gdd, 1),
        "extreme_heat_days": 18,
        "winter_slowdown_days": 24,
        "gdd_source": "MAHARASHTRA_CLIMATOLOGICAL_SEASONAL"
    }

def fuse_multisensor_features(
    sentinel_indices: Dict[str, Any],
    texture_features: Dict[str, Any],
    soil_profile: Dict[str, float],
    crop_age_days: int = 360,
    accumulated_gdd: float = 4800.0,
    extreme_heat_days: int = 15,
    cane_variety: str = "CO-265",
    crop_type: str = "ADSALI",
    is_ratoon: bool = False
) -> Dict[str, Any]:
    """
    Fuses Sentinel-2 multi-spectral, spatial texture, physical soil, and dynamic agrometeorology.
    """
    variety_upper = str(cane_variety).upper()
    variety_code = 1.0 if "265" in variety_upper else (2.0 if "86032" in variety_upper else 0.0)
    ratoon_flag = 1.0 if (is_ratoon or "KHODWA" in str(crop_type).upper() or "RATOON" in str(crop_type).upper()) else 0.0

    tex_homogeneity = texture_features.get("glcm_homogeneity")
    tex_contrast = texture_features.get("glcm_contrast")
    tex_entropy = texture_features.get("glcm_entropy")
    tex_energy = texture_features.get("glcm_energy")

    # If texture is completely missing (both satellites obscured), fill with neutral empirical midpoint
    if np.isnan(tex_homogeneity) or tex_homogeneity is None:
        tex_homogeneity = 0.55
        tex_contrast = 1.60
        tex_entropy = 2.90
        tex_energy = 0.16

    fused = {
        # Spectral Indices (Sentinel-2 10m)
        "ndvi": float(sentinel_indices.get("ndvi", 0.70)),
        "ndre": float(sentinel_indices.get("ndre", 0.18)),
        "lswi": float(sentinel_indices.get("lswi", 0.35)),
        "canopy_fraction_pct": float(sentinel_indices.get("canopy_fraction_pct", 85.0)),
        
        # Spatial Texture (LISS-4 5.8m OR Sentinel-2 10m fallback)
        "glcm_homogeneity": float(tex_homogeneity),
        "glcm_contrast": float(tex_contrast),
        "glcm_entropy": float(tex_entropy),
        "glcm_energy": float(tex_energy),
        
        # Physical Soil Mineralogy (ISRIC SoilGrids 250m)
        "clay_fraction_pct": float(soil_profile.get("clay_fraction_pct", 46.5)),
        "cation_exchange_capacity": float(soil_profile.get("cation_exchange_capacity", 42.5)),
        "soil_organic_carbon_pct": float(soil_profile.get("soil_organic_carbon_pct", 0.68)),
        
        # Agronomic & Dynamic Agrometeorological Drivers
        "crop_age_days": float(crop_age_days),
        "is_ratoon": ratoon_flag,
        "accumulated_gdd": float(accumulated_gdd),
        "extreme_heat_days": float(extreme_heat_days),
        "variety_code": float(variety_code)
    }
    return fused

class ISROSugarcaneXGBoostModel:
    """
    Tuned XGBoost Regressor for Sugarcane Sub-Field Tonnage (t/ha) and CCS Sugar Recovery (%).
    """
    def __init__(self):
        self.tonnage_model = None
        self.ccs_model = None
        self.feature_names = [
            "ndvi", "ndre", "lswi", "canopy_fraction_pct",
            "glcm_homogeneity", "glcm_contrast", "glcm_entropy", "glcm_energy",
            "clay_fraction_pct", "cation_exchange_capacity", "soil_organic_carbon_pct",
            "crop_age_days", "is_ratoon", "accumulated_gdd", "extreme_heat_days", "variety_code"
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
        Cross-validates and trains models using GroupKFold on Gat/Farmer IDs.
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