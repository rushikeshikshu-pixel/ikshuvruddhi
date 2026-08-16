"""
tests/test_spatio_temporal_engine.py
Unit tests for:
  - Step-function canopy collapse event detection
  - Direct pixel-measured canopy fractions
  - Missing observation state handling (no silent fallbacks)
  - Parcel-specific scene quality ranking
  - Spatial boundary shift synthesis
"""

import pytest
import numpy as np
from ml.sentinel_timeseries_harvester import rank_scene_quality
from ml.phenology_features import extract_phenological_trajectory_features
from ml.spatio_temporal_engine import (
    evaluate_spatio_temporal_profile,
    detect_canopy_collapse_events
)

def test_detect_step_function_canopy_collapse_event():
    """Verifies that a drop from 0.797 to 0.198 is detected as a strong canopy clearing / harvest event."""
    dates = ["2025-08-10", "2025-11-25", "2026-01-23", "2026-05-15"]
    ndvi = [0.45, 0.797, 0.198, 0.220]

    res = detect_canopy_collapse_events(dates, ndvi)
    assert res["collapse_detected"] == True
    assert res["pre_collapse_ndvi"] == 0.797
    assert res["post_collapse_ndvi"] == 0.198
    assert res["drop_magnitude"] == pytest.approx(0.599, abs=1e-3)
    assert res["clearing_window"] == "2025-11-25 -> 2026-01-23"

def test_evaluate_profile_with_collapse_event():
    """Checks that evaluate_spatio_temporal_profile outputs STRONG_CANOPY_CLEARING_EVENT_CONSISTENT_WITH_HARVEST."""
    dates = ["2025-08-10", "2025-11-25", "2026-01-23", "2026-05-15"]
    ndvi = [0.45, 0.797, 0.198, 0.220]
    pheno = extract_phenological_trajectory_features(dates, ndvi)

    current_obs = {"ndvi": 0.22, "canopy_fraction_pct": 0.0, "is_valid": True, "usability_pct": 100.0, "date": "2026-08-10"}
    spatial_ctx = {"spatial_discrepancy_stratum": "ISOLATED_LOW_CANOPY_DISCREPANCY"}

    diag = evaluate_spatio_temporal_profile(
        current_obs=current_obs,
        pheno_features=pheno,
        spatial_context=spatial_ctx,
        dates_list=dates,
        ndvi_series=ndvi
    )

    assert diag["spatio_temporal_status"] == "STRONG_CANOPY_CLEARING_EVENT_CONSISTENT_WITH_HARVEST"
    assert diag["harvest_detected_flag"] == True
    assert diag["canopy_trajectory_phase"] == "POST_HARVEST_CLEARING"
    assert "0.797" in diag["diagnostic_rationale"]

def test_missing_current_observation_no_silent_fallback():
    """Checks that invalid current state (<50% usability) does not silently substitute old values."""
    dates = ["2025-08-10", "2025-11-25", "2026-01-23"]
    ndvi = [0.45, 0.65, 0.72]
    pheno = extract_phenological_trajectory_features(dates, ndvi)

    current_obs = {"ndvi": 0.20, "canopy_fraction_pct": 0.0, "is_valid": False, "usability_pct": 30.0, "date": "2026-08-10"}
    spatial_ctx = {"spatial_discrepancy_stratum": "CONGRUENT_STANDING_CANOPY"}

    diag = evaluate_spatio_temporal_profile(
        current_obs=current_obs,
        pheno_features=pheno,
        spatial_context=spatial_ctx,
        dates_list=dates,
        ndvi_series=ndvi
    )

    assert diag["current_observation_valid"] == False

def test_rank_scene_quality_prioritizes_clean_observation():
    """Verifies that an older 99% usable cloud-free scene ranks higher than a newer 35% usable cloudy scene."""
    score_clean = rank_scene_quality(
        parcel_valid_coverage_pct=99.0,
        cloud_cover_pct=1.0,
        acquisition_datetime="2026-08-10",
        target_reference_datetime="2026-08-15"
    )

    score_cloudy = rank_scene_quality(
        parcel_valid_coverage_pct=35.0,
        cloud_cover_pct=45.0,
        acquisition_datetime="2026-08-15",
        target_reference_datetime="2026-08-15"
    )

    assert score_clean > score_cloudy
    assert score_clean >= 90.0

if __name__ == "__main__":
    pytest.main(["-v", __file__])