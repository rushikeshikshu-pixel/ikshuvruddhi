"""
tests/test_spatio_temporal_engine.py
Unit tests for 3-layer spatio-temporal engine: scene quality ranking, harvest detection,
persistent fallow, emerging recovery, and spatial boundary shift synthesis.
"""

import pytest
from ml.sentinel_timeseries_harvester import rank_scene_quality
from ml.phenology_features import extract_phenological_trajectory_features
from ml.spatio_temporal_engine import evaluate_spatio_temporal_profile

def test_rank_scene_quality_prioritizes_clean_observation():
    """Verifies that an older 100% usable cloud-free scene ranks higher than a newer 40% usable cloudy scene."""
    # Scene 1: Aug 10, 99% parcel usable, 1% cloud
    score_clean = rank_scene_quality(
        parcel_valid_coverage_pct=99.0,
        cloud_cover_pct=1.0,
        acquisition_datetime="2026-08-10",
        target_reference_datetime="2026-08-15"
    )

    # Scene 2: Aug 15, 35% parcel usable, 45% cloud
    score_cloudy = rank_scene_quality(
        parcel_valid_coverage_pct=35.0,
        cloud_cover_pct=45.0,
        acquisition_datetime="2026-08-15",
        target_reference_datetime="2026-08-15"
    )

    assert score_clean > score_cloudy
    assert score_clean >= 90.0

def test_detect_likely_harvested_cane_parcel():
    """Historical 12-month trajectory was high cane (0.75 peak, 240 green days) followed by sharp collapse."""
    dates = [
        "2025-07-01", "2025-09-01", "2025-11-01", "2026-01-01", "2026-02-01", "2026-03-01", "2026-05-01"
    ]
    # Reached peak 0.76 in Jan, collapsed sharply to 0.25 in March
    ndvi = [0.35, 0.65, 0.74, 0.76, 0.72, 0.25, 0.22]
    pheno = extract_phenological_trajectory_features(dates, ndvi)
    
    current_obs = {"ndvi": 0.24, "occupancy_pct": 2.0, "date": "2026-08-10"}
    spatial_ctx = {"spatial_discrepancy_stratum": "ISOLATED_LOW_CANOPY_DISCREPANCY"}

    res = evaluate_spatio_temporal_profile(current_obs, pheno, spatial_ctx)
    assert res["spatio_temporal_status"] == "LIKELY_HARVESTED_CANE_PARCEL"
    assert res["harvest_detected_flag"] == True
    assert res["canopy_trajectory_phase"] == "POST_HARVEST_CLEARING"

def test_detect_persistent_non_plantation_fallow():
    """12-month trajectory remained flat low (<0.30) throughout the year."""
    dates = ["2025-07-01", "2025-10-01", "2026-01-01", "2026-04-01", "2026-08-01"]
    ndvi = [0.22, 0.25, 0.28, 0.24, 0.21]
    pheno = extract_phenological_trajectory_features(dates, ndvi)

    current_obs = {"ndvi": 0.21, "occupancy_pct": 0.0, "date": "2026-08-10"}
    spatial_ctx = {"spatial_discrepancy_stratum": "REGIONAL_FALLOW_OR_DRY_LOCALITY"}

    res = evaluate_spatio_temporal_profile(current_obs, pheno, spatial_ctx)
    assert res["spatio_temporal_status"] == "PERSISTENT_NON_PLANTATION_OR_FALLOW"
    assert res["harvest_detected_flag"] == False
    assert res["operational_mill_recommendation"] == "FLAG_UNPLANTED_REGISTRATION"

def test_detect_emerging_or_recovering_crop():
    """Low in Jan snapshot (0.25), but recent 60-90d delta surged (+0.35) to 0.62 in August."""
    dates = ["2025-07-01", "2025-10-01", "2026-01-23", "2026-05-15", "2026-08-10"]
    ndvi = [0.20, 0.22, 0.24, 0.28, 0.62]
    pheno = extract_phenological_trajectory_features(dates, ndvi)

    current_obs = {"ndvi": 0.62, "occupancy_pct": 74.0, "date": "2026-08-10"}
    recent_delta = {"delta_ndvi_60_90d": 0.34, "days_span": 85}
    spatial_ctx = {"spatial_discrepancy_stratum": "CONGRUENT_STANDING_CANOPY"}

    res = evaluate_spatio_temporal_profile(current_obs, pheno, spatial_ctx, recent_delta_obs=recent_delta)
    assert res["spatio_temporal_status"] in ["CURRENTLY_EMERGING_OR_RATOON_RECOVERING", "CONFIRMED_STANDING_SUGARCANE_MATURE", "ACTIVE_VEGETATIVE_GROWTH_RECENT_CROP"]
    assert res["canopy_trajectory_phase"] in ["ACTIVE_TILLERING_GROWTH", "STANDING_MATURE_CANOPY"]

def test_detect_boundary_shift_synthesis():
    """Low inside parcel, but strong standing canopy in 25-50m ring."""
    current_obs = {"ndvi": 0.25, "occupancy_pct": 2.0, "date": "2026-08-10"}
    pheno = {"green_duration_days": 10, "max_ndvi": 0.28, "senescence_rate_per_day": 0.0}
    spatial_ctx = {
        "spatial_discrepancy_stratum": "BOUNDARY_OR_POLYGON_SHIFT_SUSPECT",
        "ring_25m_canopy_pct": 48.0,
        "ring_50m_canopy_pct": 58.0
    }

    res = evaluate_spatio_temporal_profile(current_obs, pheno, spatial_ctx)
    assert res["spatio_temporal_status"] == "BOUNDARY_OR_REGISTRATION_DISCREPANCY"
    assert res["operational_mill_recommendation"] == "GPS_BOUNDARY_RE_SURVEY"

if __name__ == "__main__":
    pytest.main(["-v", __file__])