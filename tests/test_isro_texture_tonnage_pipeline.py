"""
tests/test_isro_texture_tonnage_pipeline.py
Unit tests for Production Multi-Sensor Tonnage & Sucrose Engine:
ISRO LISS-4 (5.8m) Texture + Live ISRIC SoilGrids REST API + Agronomic Drivers + GroupKFold XGBoost.
"""

import numpy as np
import pandas as pd
import pytest
from ml.isro_texture_tonnage_pipeline import (
    compute_glcm_texture_features,
    fetch_isric_soilgrids,
    calculate_accumulated_gdd,
    fuse_multisensor_features,
    ISROSugarcaneXGBoostModel
)

def test_glcm_texture_extraction_normal_canopy():
    np.random.seed(42)
    canopy_patch = np.zeros((16, 16), dtype=np.float32)
    canopy_patch[::2, :] = 0.48 + np.random.normal(0, 0.03, (8, 16))
    canopy_patch[1::2, :] = 0.28 + np.random.normal(0, 0.03, (8, 16))

    texture = compute_glcm_texture_features(canopy_patch)

    assert "glcm_homogeneity" in texture
    assert "glcm_contrast" in texture
    assert "glcm_entropy" in texture
    assert "glcm_energy" in texture
    assert "glcm_dissimilarity" in texture
    assert texture["glcm_contrast"] > 0.5
    assert texture["glcm_entropy"] > 1.0

def test_glcm_texture_async_fallback():
    texture = compute_glcm_texture_features(None)
    assert texture["texture_source"] == "ASYNC_SENTINEL_PROXY"
    assert texture["glcm_homogeneity"] == 0.60
    assert texture["glcm_contrast"] == 1.50

def test_live_isric_soilgrids_query():
    soil = fetch_isric_soilgrids(latitude=19.34, longitude=75.31)
    
    assert "clay_fraction_pct" in soil
    assert "sand_fraction_pct" in soil
    assert "cation_exchange_capacity" in soil
    assert 35.0 <= soil["clay_fraction_pct"] <= 65.0
    assert soil["data_source"] in ["ISRIC_SOILGRIDS_V2_LIVE", "REGIONAL_VERTISOL_OFFLINE_FALLBACK"]

def test_agronomic_gdd_and_ratoon_modeling():
    gdd = calculate_accumulated_gdd(crop_age_days=360, base_temp_c=12.0, mean_daily_temp_c=27.5)
    assert gdd == round(360 * (27.5 - 12.0), 1)

    s2_indices = {"ndvi": 0.78, "ndre": 0.20, "lswi": 0.42, "canopy_fraction_pct": 92.0}
    texture = {"glcm_homogeneity": 0.62, "glcm_contrast": 2.10, "glcm_entropy": 3.45, "glcm_energy": 0.12, "glcm_dissimilarity": 1.25}
    soil = {"clay_fraction_pct": 54.0, "cation_exchange_capacity": 50.0, "soil_organic_carbon_pct": 0.82}

    fused_ratoon = fuse_multisensor_features(
        sentinel_indices=s2_indices,
        liss4_texture=texture,
        soil_profile=soil,
        crop_age_days=300,
        cane_variety="CO-265",
        crop_type="KHODWA_RATOON"
    )
    assert fused_ratoon["is_ratoon"] == 1.0
    assert fused_ratoon["variety_vigor_mult"] == 1.06
    assert fused_ratoon["accumulated_gdd"] > 4000.0

def test_xgboost_group_kfold_training_and_inference():
    np.random.seed(42)
    n_samples = 150

    records = []
    y_t = []
    y_c = []
    group_ids = []

    for i in range(n_samples):
        farm_group = f"FARM_{i % 30}"
        group_ids.append(farm_group)

        is_ratoon = 1.0 if (i % 3 == 0) else 0.0
        age = np.random.randint(280, 420)
        ndvi = np.random.uniform(0.40, 0.85)
        ndre = ndvi * 0.25 + np.random.normal(0, 0.02)
        lswi = ndvi * 0.45 + np.random.normal(0, 0.03)
        canopy = ndvi * 100.0
        contrast = np.random.uniform(1.2, 3.2)
        entropy = np.random.uniform(2.2, 3.8)
        homogeneity = 1.0 / (1.0 + contrast)
        clay = np.random.uniform(42.0, 58.0)
        cec = clay * 0.92
        soc = np.random.uniform(0.55, 1.1)
        gdd = (27.5 - 12.0) * age
        var_mult = 1.06 if (i % 2 == 0) else 0.96

        f = {
            "ndvi": ndvi, "ndre": ndre, "lswi": lswi, "canopy_fraction_pct": canopy,
            "glcm_homogeneity": homogeneity, "glcm_contrast": contrast, "glcm_entropy": entropy,
            "glcm_energy": 0.15, "glcm_dissimilarity": 1.1,
            "clay_fraction_pct": clay, "cation_exchange_capacity": cec, "soil_organic_carbon_pct": soc,
            "crop_age_days": age, "is_ratoon": is_ratoon, "accumulated_gdd": gdd, "variety_vigor_mult": var_mult
        }
        records.append(f)

        t = 35.0 + (ndvi * 42.0) + (contrast * 7.5) + (clay * 0.22) + (is_ratoon * -5.0) + np.random.normal(0, 4.0)
        c = 9.2 + (age / 420.0 * 2.3) + (ndvi * 1.2) + (is_ratoon * 0.4) + np.random.normal(0, 0.35)
        y_t.append(t)
        y_c.append(c)

    df_X = pd.DataFrame(records)
    y_tonnage = np.array(y_t)
    y_ccs = np.array(y_c)
    groups = np.array(group_ids)

    model = ISROSugarcaneXGBoostModel()
    metrics = model.train_with_group_kfold(df_X, y_tonnage, y_ccs, group_ids=groups, n_splits=5)

    assert "cross_validation_metrics" in metrics
    cv_mape = metrics["cross_validation_metrics"]["tonnage_cv_mape_pct"]
    assert cv_mape < 16.0
    assert metrics["cross_validation_metrics"]["tonnage_cv_rmse_t_ha"] < 12.0

    test_sample = records[0]
    pred = model.predict_plot(test_sample, area_hectares=1.2)

    assert pred["predicted_tonnage_t_ha"] > 40.0
    assert pred["predicted_total_tonnes"] == round(pred["predicted_tonnage_t_ha"] * 1.2, 1)
    assert 9.0 <= pred["predicted_ccs_pct"] <= 14.5
    assert pred["harvest_priority_score"] > 50.0