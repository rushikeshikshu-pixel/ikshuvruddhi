"""
tests/test_spatio_temporal_engine.py
Unit tests for:
  - Dual-metric canopy collapse event detection (NDVI + direct canopy fraction + time gap)
  - Boundary discrepancy guard (inside low required)
  - Time-gap constraints
  - Missing observation state handling
  - Multi-dimensional schema decoupling
"""

import pytest
import numpy as np
from ml.sentinel_timeseries_harvester import rank_scene_quality
from ml.phenology_features import extract_phenological_trajectory_features
from ml.spatio_temporal_engine import (
    evaluate_spatio_temporal_profile,
    detect_canopy_collapse_events
)

def test_dual_metric_canopy_collapse_event():
    """Verifies that a drop from (NDVI 0.804, Canopy 94%) to (NDVI 0.204, Canopy 1%) within 58 days triggers collapse."""
    dates = ["2025-08-10", "2025-11-26", "2026-01-23", "2026-05-15"]
    ndvi = [0.45, 0.804, 0.204, 0.220]
    canopy = [25.0, 94.0, 1.0, 0.0]

    res = detect_canopy_collapse_events(dates, ndvi, canopy)
    assert res["collapse_detected"] == True
    assert res["pre_collapse_ndvi"] == 0.804
    assert res["post_collapse_ndvi"] == 0.204
    assert res["drop_magnitude_ndvi"] == pytest.approx(0.600, abs=1e-3)
    assert res["drop_magnitude_canopy_pp"] == pytest.approx(93.0, abs=1e-1)
    assert res["gap_days"] == 58
    assert res["clearing_window"] == "2025-11-26 -> 2026-01-23"

def test_time_gap_constraint_rejects_broad_interval():
    """Verifies that a drop across 150 days is rejected by the step-function collapse detector."""
    dates = ["2025-08-10", "2026-01-23"] # 166 days apart
    ndvi = [0.80, 0.20]
    canopy = [90.0, 0.0]

    res = detect_canopy_collapse_events(dates, ndvi, canopy, max_gap_days=95)
    assert res["collapse_detected"] == False

def test_guarded_boundary_discrepancy_prevents_false_positive():
    """A healthy field (inside canopy 85%) in a healthy neighborhood (ring 80%) must NOT be called boundary discrepancy."""
    dates = ["2025-08-10", "2025-11-26", "2026-01-23", "2026-05-15", "2026-08-10"]
    ndvi = [0.45, 0.72, 0.75, 0.68, 0.65]
    canopy = [20.0, 85.0, 90.0, 80.0, 78.0]
    pheno = extract_phenological_trajectory_features(dates, ndvi)

    current_obs = {"ndvi": 0.65, "canopy_fraction_pct": 78.0, "is_valid": True, "usability_pct": 100.0, "date": "2026-08-10"}
    spatial_ctx = {
        "spatial_discrepancy_stratum": "CONGRUENT_STANDING_CANOPY",
        "ring_25m_canopy_pct": 82.0,
        "ring_50m_canopy_pct": 88.0,
        "nearest_high_canopy_dist_m": 0.0
    }

    diag = evaluate_spatio_temporal_profile(
        current_obs=current_obs,
        pheno_features=pheno,
        spatial_context=spatial_ctx,
        dates_list=dates,
        ndvi_series=ndvi,
        canopy_frac_series=canopy,
        january_canopy_occ=90.0
    )

    assert diag["spatial_neighborhood_flag"] == "CONGRUENT_STANDING_CANOPY"
    assert diag["spatio_temporal_status"] == "SUGARCANE_COMPATIBLE_STANDING_CANOPY"

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
    assert diag["current_vegetative_state"] == "CURRENT_OBSERVATION_UNAVAILABLE"

def test_rank_scene_quality_with_seasonal_target_date():
    """Verifies that rank_scene_quality correctly ranks relative to a season-specific reference target date."""
    score_nov = rank_scene_quality(
        parcel_valid_coverage_pct=99.0,
        cloud_cover_pct=2.0,
        acquisition_datetime="2025-11-24",
        target_reference_datetime="2025-11-15"
    )
    assert score_nov >= 90.0

if __name__ == "__main__":
    pytest.main(["-v", __file__])


def test_invalid_current_observation_rejects_harvest_supply():
    """Ensures an invalid current scene (<50% usability) NEVER produces SCHEDULE_FOR_HARVEST_SUPPLY even with high January canopy."""
    dates = ["2025-08-10", "2025-11-25", "2026-01-23"]
    ndvi = [0.45, 0.65, 0.72]
    from ml.phenology_features import extract_phenological_trajectory_features
    pheno = extract_phenological_trajectory_features(dates, ndvi)

    # Current scene is invalid/cloudy, but January canopy was 85%
    current_obs = {"ndvi": 0.60, "canopy_fraction_pct": 70.0, "is_valid": False, "usability_pct": 20.0, "date": "2026-08-10"}
    spatial_ctx = {"spatial_discrepancy_stratum": "CONGRUENT_STANDING_CANOPY"}

    from ml.spatio_temporal_engine import evaluate_spatio_temporal_profile
    diag = evaluate_spatio_temporal_profile(
        current_obs=current_obs,
        pheno_features=pheno,
        spatial_context=spatial_ctx,
        dates_list=dates,
        ndvi_series=ndvi,
        january_canopy_occ=85.0
    )

    assert diag["current_observation_valid"] is False
    assert diag["operational_mill_action"] == "ACQUIRE_CLOUD_FREE_TELEMETRY"
    assert diag["spatio_temporal_status"] == "CURRENT_OBSERVATION_UNAVAILABLE"


def test_historic_collapse_with_regrowth_detects_ratoon_not_harvest():
    """Ensures an old canopy collapse followed by healthy green regrowth produces RATOON_REGROWTH, not LOG_HARVEST."""
    # Step collapse in Nov-Dec 2025, but current observation in Aug 2026 shows full regrowth
    dates = ["2025-08-10", "2025-11-25", "2025-12-20"]
    ndvi = [0.68, 0.66, 0.28]  # Collapse happened here
    canopy = [80.0, 75.0, 15.0]

    from ml.phenology_features import extract_phenological_trajectory_features
    pheno = extract_phenological_trajectory_features(dates, ndvi)

    # Current observation in August 2026 shows healthy standing regrowth
    current_obs = {"ndvi": 0.65, "canopy_fraction_pct": 70.0, "is_valid": True, "usability_pct": 95.0, "date": "2026-08-16"}
    spatial_ctx = {"spatial_discrepancy_stratum": "CONGRUENT_STANDING_CANOPY"}

    from ml.spatio_temporal_engine import evaluate_spatio_temporal_profile
    diag = evaluate_spatio_temporal_profile(
        current_obs=current_obs,
        pheno_features=pheno,
        spatial_context=spatial_ctx,
        dates_list=dates,
        ndvi_series=ndvi,
        canopy_frac_series=canopy,
        reference_date_str="2026-08-16"
    )

    assert diag["canopy_clearing_event_detected"] is True
    assert diag["operational_mill_action"] == "MONITOR_RATOON_CYCLE_DEVELOPMENT"
    assert diag["spatio_temporal_status"] == "CONFIRMED_STANDING_RATOON_REGROWTH"
