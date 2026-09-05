"""
tests/test_isro_texture_tonnage_pipeline.py
Unit tests for ISRO Resourcesat-2A LISS-4 (5.8m) Texture Fusion, Soil Mineralogy, and XGBoost Engine.
"""

import numpy as np
import pandas as pd
import pytest
from ml.isro_texture_tonnage_pipeline import (
    compute_glcm_texture_features,
    get_soil_mineralogy_profile,
    fuse_multisensor_features,
    ISROSugarcaneXGBoostModel
)

def test_glcm_texture_extraction_normal_canopy():
    # Simulate a 16x16 5.8m high-resolution canopy patch with row-crop variation
    np.random.seed(42)
    canopy_patch = np.zeros((16, 16), dtype=np.float32)
    # Cane rows with higher NIR reflectance
    canopy_patch[::2, :] = 0.48 + np.random.normal(0, 0.03, (8, 16))
    # Furrows with lower reflectance
    canopy_patch[1::2, :] = 0.28 + np.random.normal(0, 0.03, (8, 16))

    texture = compute_glcm_texture_features(canopy_patch)

    assert "glcm_homogeneity" in texture
    assert "glcm_contrast" in texture
    assert "glcm_entropy" in texture
    assert "glcm_energy" in texture
    assert "glcm_dissimilarity" in texture

    # In row crops, contrast and entropy should be strictly positive
    assert texture["glcm_contrast"] > 0.5
    assert texture["glcm_entropy"] > 1.0
    assert 0.0 <= texture["glcm_homogeneity"] <= 1.0

def test_glcm_texture_edge_cases():
    # 1. Constant patch (e.g. water body or pure cloud)
    flat_patch = np.ones((10, 10), dtype=np.float32) * 0.5
    flat_texture = compute_glcm_texture_features(flat_patch)
    assert flat_texture["glcm_homogeneity"] == 1.0
    assert flat_texture["glcm_contrast"] == 0.0

    # 2. Empty / small array
    tiny_patch = np.zeros((1, 1), dtype=np.float32)
    tiny_texture = compute_glcm_texture_features(tiny_patch)
    assert tiny_texture["glcm_homogeneity"] == 0.0

def test_soil_mineralogy_profile():
    # Shevgaon / Gangamai coordinates: 19.34 N, 75.31 E
    soil = get_soil_mineralogy_profile(latitude=19.34, longitude=75.31)
    
    assert 40.0 <= soil["clay_fraction_pct"] <= 65.0
    assert 20.0 <= soil["silt_fraction_pct"] <= 35.0
    assert soil["sand_fraction_pct"] >= 5.0
    assert soil["cation_exchange_capacity"] >= 35.0
    assert round(soil["clay_fraction_pct"] + soil["silt_fraction_pct"] + soil["sand_fraction_pct"], 1) == 100.0

def test_multisensor_fusion():
    s2_indices = {"ndvi": 0.78, "ndre": 0.20, "lswi": 0.42, "canopy_fraction_pct": 92.0}
    texture = {"glcm_homogeneity": 0.62, "glcm_contrast": 2.10, "glcm_entropy": 3.45, "glcm_energy": 0.12, "glcm_dissimilarity": 1.25}
    soil = {"clay_fraction_pct": 54.0, "cation_exchange_capacity": 50.0, "soil_organic_carbon_pct": 0.82}

    fused = fuse_multisensor_features(
        sentinel_indices=s2_indices,
        liss4_texture=texture,
        soil_profile=soil,
        crop_age_days=380,
        cane_variety="CO-265"
    )

    assert fused["ndvi"] == 0.78
    assert fused["glcm_contrast"] == 2.10
    assert fused["clay_fraction_pct"] == 54.0
    assert fused["crop_age_days"] == 380
    assert fused["variety_vigor_mult"] == 1.05

def test_xgboost_training_and_inference():
    np.random.seed(42)
    n_samples = 120

    # Synthetic training set reflecting physical relationships
    records = []
    y_t = []
    y_c = []

    for _ in range(n_samples):
        ndvi = np.random.uniform(0.35, 0.85)
        ndre = ndvi * 0.25 + np.random.normal(0, 0.02)
        lswi = ndvi * 0.50 + np.random.normal(0, 0.03)
        canopy = ndvi * 100.0
        contrast = np.random.uniform(1.0, 3.5)
        entropy = np.random.uniform(2.0, 4.0)
        homogeneity = 1.0 / (1.0 + contrast)
        clay = np.random.uniform(45.0, 60.0)
        cec = clay * 0.90
        soc = np.random.uniform(0.5, 1.2)
        age = np.random.randint(280, 420)
        var_mult = 1.05

        f = {
            "ndvi": ndvi, "ndre": ndre, "lswi": lswi, "canopy_fraction_pct": canopy,
            "glcm_homogeneity": homogeneity, "glcm_contrast": contrast, "glcm_entropy": entropy,
            "glcm_energy": 0.15, "glcm_dissimilarity": 1.1,
            "clay_fraction_pct": clay, "cation_exchange_capacity": cec, "soil_organic_carbon_pct": soc,
            "crop_age_days": age, "variety_vigor_mult": var_mult
        }
        records.append(f)

        # Tonnage correlates strongly with texture entropy, NDVI, and age
        t = 40.0 + (ndvi * 45.0) + (contrast * 8.0) + (clay * 0.25) + np.random.normal(0, 2.0)
        # CCS correlates with age and ripening drying (lower LSWI at late age)
        c = 9.0 + (age / 420.0 * 2.5) + (ndvi * 1.5) + np.random.normal(0, 0.2)
        y_t.append(t)
        y_c.append(c)

    df_X = pd.DataFrame(records)
    y_tonnage = np.array(y_t)
    y_ccs = np.array(y_c)

    model = ISROSugarcaneXGBoostModel()
    metrics = model.train_models(df_X, y_tonnage, y_ccs)

    assert "tonnage_metrics" in metrics
    assert "ccs_metrics" in metrics
    assert metrics["tonnage_metrics"]["mape_pct"] < 8.0
    assert metrics["tonnage_metrics"]["r2_score"] > 0.85

    # Test single parcel inference
    test_sample = records[0]
    pred = model.predict_plot(test_sample, area_hectares=1.5)

    assert pred["predicted_tonnage_t_ha"] > 40.0
    assert pred["predicted_total_tonnes"] == round(pred["predicted_tonnage_t_ha"] * 1.5, 1)
    assert 9.0 <= pred["predicted_ccs_pct"] <= 14.5
    assert pred["predicted_recoverable_sugar_tonnes"] > 0.0
    assert pred["area_acres"] == round(1.5 * 2.47105, 2)