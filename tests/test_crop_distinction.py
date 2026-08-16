"""
tests/test_crop_distinction.py
Comprehensive unit tests for multi-temporal phenology feature extraction and crop distinction classification.
"""

import pytest
import numpy as np
from ml.phenology_features import extract_phenological_trajectory_features
from ml.crop_distinction import classify_crop_from_phenology

def test_exact_directional_green_duration_interpolation():
    """Verifies that upward and downward threshold crossings compute correct fractional durations."""
    dates = ["2025-07-01", "2025-07-11", "2025-07-21"] # 10 days each interval
    thresh = 0.45

    # Interval 1: 0.25 -> 0.65 (Upward crossing, 5 days above)
    # Interval 2: 0.70 -> 0.40 (Downward crossing, 8.33 days above)
    ndvi = [0.25, 0.65, 0.40]
    
    feats = extract_phenological_trajectory_features(dates, ndvi, min_ndvi_green_threshold=thresh)
    assert 13 <= feats["green_duration_days"] <= 14

def test_missing_spectral_indices_neutrality():
    """Verifies that missing NDRE/LSWI (None) is preserved and does not cause false zero penalties."""
    dates = [
        "2025-07-01", "2025-08-01", "2025-09-01", "2025-10-01",
        "2025-11-01", "2025-12-01", "2026-01-01", "2026-02-01",
        "2026-03-01", "2026-04-01", "2026-05-01", "2026-06-01"
    ]
    ndvi = [0.25, 0.45, 0.65, 0.75, 0.78, 0.75, 0.72, 0.68, 0.65, 0.61, 0.58, 0.52]
    # Completely missing NDRE and LSWI
    feats = extract_phenological_trajectory_features(dates, ndvi, ndre_series=None, lswi_series=None)
    assert feats["mean_ripening_lswi"] is None
    assert feats["mean_ripening_ndre"] is None
    assert feats["green_duration_days"] >= 240

    pred = classify_crop_from_phenology(feats)
    assert pred["predicted_crop"] == "SUGARCANE"

def test_sugarcane_15month_perennial_profile():
    """Sugarcane Adsali 15-month profile: gradual emergence, sustained greenness for 270+ days, high LSWI & NDRE."""
    dates = [
        "2025-07-01", "2025-08-01", "2025-09-01", "2025-10-01",
        "2025-11-01", "2025-12-01", "2026-01-01", "2026-02-01",
        "2026-03-01", "2026-04-01", "2026-05-01", "2026-06-01"
    ]
    ndvi = [0.25, 0.42, 0.62, 0.74, 0.78, 0.75, 0.72, 0.68, 0.65, 0.61, 0.58, 0.52]
    ndre = [0.15, 0.22, 0.38, 0.48, 0.50, 0.46, 0.44, 0.40, 0.38, 0.35, 0.33, 0.30]
    lswi = [0.02, 0.08, 0.20, 0.28, 0.30, 0.27, 0.25, 0.22, 0.20, 0.18, 0.16, 0.14]

    feats = extract_phenological_trajectory_features(dates, ndvi, ndre, lswi)
    assert feats["green_duration_days"] >= 240
    assert feats["is_perennial_profile"] == True
    assert feats["mean_ripening_lswi"] >= 0.14

    pred = classify_crop_from_phenology(feats, sar_vh_db=-11.5)
    assert pred["predicted_crop"] == "SUGARCANE"
    assert pred["heuristic_crop_score_pct"]["SUGARCANE"] > 0.70
    assert pred["heuristic_confidence_score"] >= 70.0

def test_banana_perennial_profile():
    """Banana profile: continuous evergreen broadleaf canopy with high baseline minimum NDVI (>= 0.50)."""
    dates = [
        "2025-07-01", "2025-08-01", "2025-09-01", "2025-10-01",
        "2025-11-01", "2025-12-01", "2026-01-01", "2026-02-01",
        "2026-03-01", "2026-04-01", "2026-05-01", "2026-06-01"
    ]
    ndvi = [0.62, 0.68, 0.72, 0.75, 0.74, 0.71, 0.70, 0.69, 0.68, 0.67, 0.66, 0.65]
    ndre = [0.35, 0.38, 0.40, 0.42, 0.40, 0.39, 0.38, 0.37, 0.36, 0.35, 0.34, 0.33]
    lswi = [0.22, 0.25, 0.28, 0.30, 0.28, 0.27, 0.26, 0.25, 0.24, 0.23, 0.22, 0.21]

    feats = extract_phenological_trajectory_features(dates, ndvi, ndre, lswi)
    assert feats["min_ndvi"] >= 0.50
    assert feats["green_duration_days"] >= 300

    pred = classify_crop_from_phenology(feats)
    assert pred["predicted_crop"] == "BANANA_OR_BROADLEAF_PERENNIAL"

def test_maize_90day_short_duration_profile():
    """Maize Kharif profile: rapid surge (30-45d), quick grain-fill dry-down, total duration ~90-100d."""
    dates = [
        "2025-07-01", "2025-07-20", "2025-08-10", "2025-08-30",
        "2025-09-20", "2025-10-10", "2025-10-30", "2025-11-20"
    ]
    ndvi = [0.20, 0.48, 0.75, 0.78, 0.55, 0.30, 0.22, 0.18]
    ndre = [0.12, 0.25, 0.42, 0.40, 0.24, 0.14, 0.10, 0.08]
    lswi = [0.01, 0.12, 0.22, 0.18, 0.04, -0.05, -0.10, -0.12]

    feats = extract_phenological_trajectory_features(dates, ndvi, ndre, lswi)
    assert feats["green_duration_days"] <= 100
    assert feats["senescence_rate_per_day"] >= 0.010

    pred = classify_crop_from_phenology(feats, sar_vh_db=-15.0)
    assert pred["predicted_crop"] == "MAIZE_OR_SEASONAL_GRAIN"
    assert pred["heuristic_crop_score_pct"]["SUGARCANE"] < 0.10

def test_cotton_160day_semi_perennial_profile():
    """Cotton profile: moderate growth, duration ~150-170 days, senescence by December."""
    dates = [
        "2025-06-15", "2025-07-15", "2025-08-15", "2025-09-15",
        "2025-10-15", "2025-11-15", "2025-12-15", "2026-01-15"
    ]
    ndvi = [0.22, 0.38, 0.58, 0.66, 0.62, 0.52, 0.38, 0.25]
    ndre = [0.12, 0.20, 0.32, 0.35, 0.31, 0.24, 0.16, 0.11]
    lswi = [0.01, 0.06, 0.12, 0.14, 0.08, 0.03, -0.02, -0.06]

    feats = extract_phenological_trajectory_features(dates, ndvi, ndre, lswi)
    assert 120 <= feats["green_duration_days"] <= 180

    pred = classify_crop_from_phenology(feats)
    assert pred["predicted_crop"] == "COTTON_OR_SEMI_PERENNIAL"

def test_fallow_bare_soil_profile():
    """Fallow parcel with no significant standing vegetation."""
    dates = ["2025-07-01", "2025-08-15", "2025-10-01", "2025-11-15", "2026-01-01"]
    ndvi = [0.22, 0.28, 0.25, 0.20, 0.18]
    ndre = [0.10, 0.12, 0.11, 0.09, 0.08]
    lswi = [-0.05, -0.02, -0.04, -0.06, -0.08]

    feats = extract_phenological_trajectory_features(dates, ndvi, ndre, lswi)
    pred = classify_crop_from_phenology(feats)
    assert pred["predicted_crop"] == "FALLOW_OR_BARE_SOIL"
    assert pred["heuristic_confidence_score"] >= 80.0

def test_insufficient_temporal_observations():
    """Sparse observation dates fail closed to INSUFFICIENT_TEMPORAL_DATA."""
    dates = ["2026-01-23", "2026-02-15"]
    ndvi = [0.65, 0.62]

    feats = extract_phenological_trajectory_features(dates, ndvi)
    pred = classify_crop_from_phenology(feats)
    assert pred["predicted_crop"] == "INSUFFICIENT_TEMPORAL_DATA"
    assert pred["heuristic_confidence_score"] == 0.0

if __name__ == "__main__":
    pytest.main(["-v", __file__])