"""
tests/test_isro_texture_tonnage_pipeline.py
Rigorous unit tests for Production Multi-Sensor Pipeline:
- Live ISRIC SoilGrids vs. Mocked Offline Fallback
- True Sentinel-2 10m texture extraction when LISS-4 is unavailable
- Missing observation flagging
- Dynamic historical GDD integration
- GroupKFold XGBoost execution
"""

import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch
import urllib.error

from ml.isro_texture_tonnage_pipeline import (
    compute_glcm_texture_features,
    fetch_isric_soilgrids,
    calculate_historical_weather_gdd,
    fuse_multisensor_features,
    ISROSugarcaneXGBoostModel
)

def test_glcm_texture_extraction_liss4_highres():
    # 16x16 5.8m high-resolution canopy patch with row-crop variation
    np.random.seed(42)
    canopy_patch = np.zeros((16, 16), dtype=np.float32)
    canopy_patch[::2, :] = 0.48 + np.random.normal(0, 0.03, (8, 16))
    canopy_patch[1::2, :] = 0.28 + np.random.normal(0, 0.03, (8, 16))

    texture = compute_glcm_texture_features(canopy_patch, source_name="ISRO_LISS4_5.8M")

    assert texture["texture_source"] == "ISRO_LISS4_5.8M"
    assert texture["texture_valid"] is True
    assert texture["glcm_contrast"] > 0.5
    assert texture["glcm_entropy"] > 1.0

def test_glcm_texture_extraction_sentinel2_fallback():
    # When LISS-4 is absent, compute actual GLCM on Sentinel-2 10m B08 NIR band
    np.random.seed(42)
    s2_nir_patch = np.random.uniform(0.35, 0.55, (10, 10)).astype(np.float32)
    
    texture = compute_glcm_texture_features(s2_nir_patch, source_name="SENTINEL2_B08_10M")
    
    assert texture["texture_source"] == "SENTINEL2_B08_10M"
    assert texture["texture_valid"] is True
    assert not np.isnan(texture["glcm_homogeneity"])
    assert texture["glcm_contrast"] >= 0.0

def test_glcm_texture_missing_observation():
    # When both satellites are clouded / missing
    texture = compute_glcm_texture_features(None)
    assert texture["texture_source"] == "MISSING_OBSERVATION"
    assert texture["texture_valid"] is False
    assert np.isnan(texture["glcm_homogeneity"])

def test_soilgrids_live_integration():
    # Must strictly connect to live ISRIC endpoint without fallback
    soil = fetch_isric_soilgrids(latitude=19.34, longitude=75.31, allow_fallback=False)
    assert soil["data_source"] == "ISRIC_SOILGRIDS_V2_LIVE"
    assert 35.0 <= soil["clay_fraction_pct"] <= 65.0
    assert soil["cation_exchange_capacity"] > 30.0

def test_soilgrids_offline_fallback():
    # Deliberately mock network error to verify fallback triggering
    with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("Network Unreachable")):
        # Clear cache for this test coordinate
        test_coord = (20.999, 76.999)
        soil = fetch_isric_soilgrids(latitude=test_coord[0], longitude=test_coord[1], allow_fallback=True)
        assert soil["data_source"] == "REGIONAL_VERTISOL_OFFLINE_FALLBACK"
        assert soil["clay_fraction_pct"] == 46.50

def test_dynamic_historical_weather_gdd():
    # Planted in July 2025, sampled in May 2026
    gdd_data = calculate_historical_weather_gdd(
        latitude=19.34,
        longitude=75.31,
        planting_date_str="2025-07-15",
        harvest_date_str="2026-05-15",
        base_temp_c=12.0
    )
    assert "accumulated_gdd" in gdd_data
    assert gdd_data["accumulated_gdd"] > 3500.0
    assert "gdd_source" in gdd_data
    assert gdd_data["gdd_source"] in ["OPEN_METEO_HISTORICAL_DAILY", "MAHARASHTRA_CLIMATOLOGICAL_SEASONAL"]

def test_xgboost_group_kfold_pipeline_mechanics():
    np.random.seed(42)
    n_samples = 120

    records = []
    y_t = []
    y_c = []
    group_ids = []

    for i in range(n_samples):
        farm_group = f"FARM_{i % 25}"
        group_ids.append(farm_group)

        f = {
            "ndvi": 0.72, "ndre": 0.18, "lswi": 0.35, "canopy_fraction_pct": 88.0,
            "glcm_homogeneity": 0.62, "glcm_contrast": 1.8, "glcm_entropy": 3.1, "glcm_energy": 0.14,
            "clay_fraction_pct": 46.5, "cation_exchange_capacity": 42.0, "soil_organic_carbon_pct": 0.70,
            "crop_age_days": 350.0, "is_ratoon": 0.0, "accumulated_gdd": 5100.0, "extreme_heat_days": 12.0,
            "variety_code": 1.0
        }
        records.append(f)
        y_t.append(85.0 + np.random.normal(0, 3.0))
        y_c.append(11.8 + np.random.normal(0, 0.3))

    df_X = pd.DataFrame(records)
    y_tonnage = np.array(y_t)
    y_ccs = np.array(y_c)
    groups = np.array(group_ids)

    model = ISROSugarcaneXGBoostModel()
    metrics = model.train_with_group_kfold(df_X, y_tonnage, y_ccs, group_ids=groups, n_splits=5)

    assert "cross_validation_metrics" in metrics
    pred = model.predict_plot(records[0], area_hectares=1.5)
    assert pred["predicted_tonnage_t_ha"] > 40.0
    assert pred["predicted_total_tonnes"] == round(pred["predicted_tonnage_t_ha"] * 1.5, 1)